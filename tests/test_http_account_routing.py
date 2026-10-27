"""Authenticated HTTP cognition must use one account's existing Mind and stores."""

import asyncio
import base64
import hashlib
import json
from contextlib import AsyncExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx

from aicognitive_mind import api
from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.codex_body_receiver import BodyReceiver, DeliveryState, ReceiverConfig, ReceiverError
from aicognitive_mind.config import Settings
from aicognitive_mind.domain import DiagnosticObservation, ReasoningProposal
from aicognitive_mind.core_skills import REQUIRED_SKILLS, load_required_skill
from aicognitive_mind.host_runtime import HostRuntime, RuntimeRecords
from aicognitive_mind.persistence import scope_storage
from aicognitive_mind.standalone import StandaloneRuntime


PASSWORD = "synthetic-http-account-password"
ADMIN_PIN = "synthetic-http-admin-pin"


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                  dotenv_settings, file_secret_settings):
        return (init_settings,)


class SyntheticRuntime:
    """Exercise the real cognitive write path without contacting a model provider."""

    def __init__(self, settings, records=None):
        self.settings = settings
        self.records = records
        self.provider = "echo"
        self.model = "synthetic-routing-engine"

    async def propose(self, request, tools=()):
        steward = next(tool for tool in tools if tool.name == "memory_steward")
        await steward.invoke({"action": "recall", "focus": request.input_text})
        await steward.invoke({
            "action": "propose_memory", "memory_class": "semantic",
            "content": request.input_text, "associations": ["synthetic-routing"],
            "grounding": ["current-user-statement"],
        })
        return ReasoningProposal(
            response_text="Recorded: " + request.input_text,
            diagnostic=DiagnosticObservation(
                component="synthetic-http-test", operation="propose_response",
                implementation={"model": self.model},
            ),
        )


class HttpAccountRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stack = AsyncExitStack()
        self.directory = tempfile.TemporaryDirectory(
            prefix="axiom_http_routing_", ignore_cleanup_errors=True,
        )
        path = Path(self.directory.name).resolve()
        self.assertTrue(path.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.settings = LocalSettings(
            _env_file=None, storage_provider="surreal",
            surrealdb_uri="surrealkv://" + (path / "store").as_posix(),
            surrealdb_namespace="synthetic_http", surrealdb_database="routing",
            axiom_mind_id="http-registry-root", surrealdb_username=None,
            surrealdb_password=None, standalone_reasoning_provider="echo",
            body_allow_standalone_fallback=True,
            app_access_username="synthetic-admin", app_access_password="synthetic-admin-password",
            admin_pin=ADMIN_PIN,
        )
        self.stack.enter_context(patch.dict("os.environ", {"RENDER": "false"}))
        self.stack.enter_context(patch("aicognitive_mind.api.get_settings", return_value=self.settings))
        self.stack.enter_context(patch("aicognitive_mind.config.get_settings", return_value=self.settings))
        self.stack.enter_context(patch("aicognitive_mind.config._body_allow_standalone_fallback_override", None))
        self.stack.enter_context(patch("aicognitive_mind.api.StandaloneRuntime", SyntheticRuntime))
        self.lifespan = api.lifespan(api.app)
        await self.lifespan.__aenter__()
        self.alpha = await api.app.state.accounts.create("routing-alpha", PASSWORD)
        self.beta = await api.app.state.accounts.create("routing-beta", PASSWORD)
        self.alpha_client = await self.client()
        self.beta_client = await self.client()
        for client, account in ((self.alpha_client, self.alpha), (self.beta_client, self.beta)):
            response = await client.post("/v1/portal/login", json={
                "username": account.username, "password": PASSWORD,
            })
            self.assertEqual(response.status_code, 200, response.text)
        self.admin_client = await self.client(auth=httpx.BasicAuth(
            self.settings.app_access_username, self.settings.app_access_password,
        ))

    async def asyncTearDown(self):
        await self.stack.aclose()
        await self.lifespan.__aexit__(None, None, None)
        self.directory.cleanup()

    async def client(self, **kwargs):
        return await self.stack.enter_async_context(httpx.AsyncClient(
            transport=httpx.ASGITransport(api.app), base_url="https://routing.example",
            headers={"X-Admin-Pin": ADMIN_PIN}, **kwargs,
        ))

    async def get_json(self, client, path, **kwargs):
        response = await client.get(path, **kwargs)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    async def test_account_mind_matches_portal_while_root_stays_uninitialized(self):
        observed = []
        for client in (self.alpha_client, self.beta_client):
            mind = await self.get_json(client, "/v1/mind")
            portal = await self.get_json(client, "/v1/portal/status")
            self.assertEqual(mind, portal["mind"])
            self.assertEqual(mind["developmental_state"], "genesis")
            self.assertIsNone(mind["identity"]["self_name"])
            self.assertEqual(portal["durable_memory_count"], 0)
            self.assertEqual(portal["journal_experience_count"], 0)
            observed.append(mind)
        self.assertNotEqual(observed[0]["created_at"], observed[1]["created_at"])
        self.assertEqual((await self.admin_client.get("/v1/mind")).status_code, 404)
        self.assertIsNone(await api.app.state.mind_store.load())
        response = await self.alpha_client.post("/v1/mind/initialize", json={"self_name": "Wrong second mind"})
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(await api.app.state.mind_store.load())

    async def test_http_interactions_commit_only_the_authenticated_accounts_stores(self):
        for client, note in (
            (self.alpha_client, "Synthetic alpha continuity note."),
            (self.beta_client, "Synthetic beta continuity note."),
        ):
            response = await client.post("/v1/mind/interactions", json={"message": note})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["response_text"], "Recorded: " + note)
        for client, own, other in (
            (self.alpha_client, "alpha", "beta"), (self.beta_client, "beta", "alpha"),
        ):
            memory = await self.get_json(client, "/v1/mind/memory")
            journal = await self.get_json(client, "/v1/mind/journal")
            self.assertEqual(len(memory), 1)
            self.assertIn(own, memory[0]["content"])
            self.assertNotIn(other, str(memory))
            self.assertEqual(len(journal), 1)
            self.assertIn(own, journal[0]["experience"]["input"]["content"])
            self.assertNotIn(other, str(journal))
        self.assertIsNone(await api.app.state.mind_store.load())
        self.assertEqual(await api.app.state.memory_store.read(), [])
        self.assertEqual(await api.app.state.journal_store.read(), [])

    async def test_portal_body_settings_capability_matches_authenticated_scope(self):
        initialized = await self.admin_client.post("/v1/mind/initialize", json={"self_name": "Synthetic root"})
        self.assertEqual(initialized.status_code, 201, initialized.text)
        await api.app.state.voice_settings.update(
            expected_revision=0, fish_audio_api_key="synthetic-deployment-voice-key", rate=1.2,
        )
        root_status = await self.get_json(self.admin_client, "/v1/portal/status")
        self.assertIs(root_status["administration"]["body_settings_available"], True)
        self.assertIs(root_status["administration"]["body_fallback_settings_available"], True)
        root_voice = await self.get_json(self.admin_client, "/v1/admin/body/voice/settings")
        self.assertEqual(root_voice["fishAudioApiKey"], "synthetic-deployment-voice-key")
        self.assertEqual(root_voice["rate"], 1.2)

        for client in (self.alpha_client, self.beta_client):
            portal = await self.get_json(client, "/v1/portal/status")
            self.assertIs(portal["administration"]["body_settings_available"], True)
            self.assertIs(portal["administration"]["body_fallback_settings_available"], False)
            own_voice = await self.get_json(client, "/v1/admin/body/voice/settings")
            self.assertEqual(own_voice["fishAudioApiKey"], "")
            self.assertEqual(own_voice["rate"], 1)
            self.assertIsNone(own_voice["fishAudioReferenceId"])
            for method, path in (
                ("GET", "/v1/admin/body/fallback"), ("PUT", "/v1/admin/body/fallback"),
                ("GET", "/v1/admin/backup"),
            ):
                with self.subTest(method=method, path=path):
                    kwargs = {"json": {"enabled": False}} if method == "PUT" else {}
                    response = await client.request(method, path, **kwargs)
                    self.assertEqual(response.status_code, 403, response.text)
                    self.assertNotIn("synthetic-deployment-voice-key", response.text)
            self.assertEqual((await self.get_json(client, "/v1/admin/provider-endpoints"))["items"], [])
            self.assertEqual((await self.get_json(client, "/v1/portal/memory"))["total"], 0)

        basic = base64.b64encode(b"synthetic-admin:synthetic-admin-password").decode()
        still_scoped = await self.get_json(self.alpha_client, "/v1/portal/status", headers={
            "Authorization": "Basic " + basic,
        })
        self.assertIs(still_scoped["administration"]["body_fallback_settings_available"], False)
        anonymous = await self.client()
        self.assertEqual((await anonymous.get("/v1/portal/status")).status_code, 401)
        self.assertEqual((await anonymous.get("/body/live")).status_code, 401)
        self.assertEqual((await anonymous.get("/v1/admin/body/voice/settings")).status_code, 401)
        self.assertEqual((await api.app.state.voice_settings.read())["rate"], 1.2)

    async def test_cookie_scope_prevails_over_basic_and_untrusted_tenant_selectors(self):
        original = await self.get_json(self.alpha_client, "/v1/mind")
        basic = base64.b64encode(b"synthetic-admin:synthetic-admin-password").decode()
        selected = await self.get_json(
            self.alpha_client, "/v1/mind?mind_id=" + self.beta.mind_id + "&tenant_id=" + self.beta.mind_id,
            headers={"Authorization": "Basic " + basic, "X-Mind-ID": self.beta.mind_id,
                     "X-Tenant-ID": self.beta.mind_id},
        )
        self.assertEqual(selected, original)
        self.assertIsNone(await api.app.state.mind_store.load())

    async def test_invalid_supplied_session_never_falls_back_to_root_or_basic(self):
        missing = await self.client()
        self.assertEqual((await missing.get("/v1/mind")).status_code, 401)
        for token in ("synthetic-tampered-cookie", "synthetic-expired-cookie"):
            if "expired" in token:
                await api.store_portal_session(api.app, token, self.alpha.mind_id, time.time() - 1)
            invalid = await self.client(auth=httpx.BasicAuth(
                self.settings.app_access_username, self.settings.app_access_password,
            ), cookies={"axiom_portal_session": token})
            self.assertEqual((await invalid.get("/v1/mind")).status_code, 401)
        for expiry in (float("nan"), float("inf")):
            stored = {"account_mind_id": self.alpha.mind_id, "expires_at": expiry}
            with patch.object(api.app.state.runtime_records, "get", AsyncMock(return_value=stored)), patch.object(
                api.app.state.accounts, "resolve_subject", new_callable=AsyncMock,
            ) as resolver:
                self.assertIsNone(await api.read_portal_session(api.app, "nonfinite-expiry"))
                invalid = await self.client(cookies={"axiom_portal_session": "nonfinite-expiry"})
                self.assertEqual((await invalid.get("/v1/mind")).status_code, 401)
                resolver.assert_not_awaited()

    async def test_valid_cookie_is_scoped_even_with_local_no_password_configuration(self):
        local = self.settings.model_copy(update={"app_access_password": None})
        with patch("aicognitive_mind.api.get_settings", return_value=local), patch(
            "aicognitive_mind.config.get_settings", return_value=local,
        ):
            response = await self.alpha_client.get("/v1/mind")
            self.assertEqual(response.status_code, 200, response.text)
            bare = await self.client()
            self.assertEqual((await bare.get("/v1/mind")).status_code, 404)
            invalid = await self.client(cookies={"axiom_portal_session": "invalid-local-cookie"})
            self.assertEqual((await invalid.get("/v1/mind")).status_code, 401)

    async def test_unknown_or_ambiguous_account_subject_is_rejected_before_core_access(self):
        for outcome in (None, CommitConflict("Ambiguous synthetic account")):
            resolver = AsyncMock(return_value=outcome) if outcome is None else AsyncMock(side_effect=outcome)
            with patch.object(api.app.state.accounts, "resolve_subject", resolver):
                response = await self.alpha_client.get("/v1/mind")
                self.assertEqual(response.status_code, 401)
            resolver.assert_awaited_once_with(self.alpha.mind_id)
        self.assertIsNone(await api.app.state.mind_store.load())

    async def test_provider_task_and_behavior_registries_are_account_scoped(self):
        response = await self.alpha_client.put("/v1/admin/provider-endpoints", json={"items": [{
            "id": "alpha-only", "name": "Synthetic alpha provider", "provider_name": "synthetic",
            "base_url": "https://synthetic.invalid/v1", "model": "alpha-model",
        }]})
        self.assertEqual(response.status_code, 200, response.text)
        assignments = (await self.get_json(self.alpha_client, "/v1/admin/task-model-assignments"))["items"]
        recall = next(item for item in assignments if item["task"] == "memory_recall")
        recall.update(provider="alpha-only", model="alpha-model")
        response = await self.alpha_client.put("/v1/admin/task-model-assignments", json={"items": assignments})
        self.assertEqual(response.status_code, 200, response.text)
        behaviors = (await self.get_json(self.alpha_client, "/v1/admin/task-behaviors"))["items"]
        next(item for item in behaviors if item["task"] == "memory_recall")["instructions"] = "Synthetic alpha instructions"
        response = await self.alpha_client.put("/v1/admin/task-behaviors", json={"items": behaviors})
        self.assertEqual(response.status_code, 200, response.text)
        for client in (self.beta_client, self.admin_client):
            self.assertEqual((await self.get_json(client, "/v1/admin/provider-endpoints"))["items"], [])
            assignments = (await self.get_json(client, "/v1/admin/task-model-assignments"))["items"]
            recall = next(item for item in assignments if item["task"] == "memory_recall")
            self.assertEqual(recall["provider"], "")
            self.assertEqual(recall["model"], "")
            behaviors = (await self.get_json(client, "/v1/admin/task-behaviors"))["items"]
            self.assertEqual(next(item for item in behaviors if item["task"] == "memory_recall")["instructions"], "")
        without_pin = await self.client()
        without_pin.headers.pop("X-Admin-Pin")
        without_pin.cookies.update(self.alpha_client.cookies)
        self.assertEqual((await without_pin.get("/v1/admin/provider-endpoints")).status_code, 401)

    async def test_account_admin_can_save_own_skills_without_access_to_root_custom_drafts(self):
        with patch("aicognitive_mind.api._skill_github_call", side_effect=AssertionError("No shared GitHub access")) as github:
            listing = await self.get_json(self.alpha_client, "/v1/admin/skills")
            self.assertFalse(listing["drafts_available"])
            self.assertEqual({item["slug"] for item in listing["items"]}, {*REQUIRED_SKILLS, "memory-steward"})
            for slug in (*REQUIRED_SKILLS, "memory-steward"):
                item = await self.get_json(self.alpha_client, "/v1/admin/skills/" + slug)
                if slug in REQUIRED_SKILLS:
                    self.assertEqual(item["content"], load_required_skill(slug))
                else:
                    self.assertTrue(item["content"])
                self.assertFalse(item["read_only"])
                prepared = await self.alpha_client.post(f"/v1/admin/skills/{slug}/prepare")
                self.assertEqual(prepared.status_code, 200, prepared.text)
                self.assertEqual(prepared.text, item["content"])
                missing_revision = await self.alpha_client.put(f"/v1/admin/skills/{slug}", json={
                    "slug": slug, "content": "An unversioned edit",
                })
                self.assertEqual(missing_revision.status_code, 409)
                changed = {
                    "slug": slug, "content": "Synthetic alpha-specific instructions: " + slug,
                    "revision": item["revision"], "enabled": False, "required": False,
                    "protected": False,
                }
                saved = await self.alpha_client.put(f"/v1/admin/skills/{slug}", json=changed)
                self.assertEqual(saved.status_code, 200, saved.text)
                self.assertEqual(saved.json()["revision"], item["revision"] + 1)
                reread = await self.get_json(self.alpha_client, f"/v1/admin/skills/{slug}")
                self.assertEqual(reread["content"], changed["content"])
                self.assertFalse(reread["enabled"])
                self.assertFalse(reread["required"])
                self.assertFalse(reread["protected"])
                stale = await self.alpha_client.put(f"/v1/admin/skills/{slug}", json=changed)
                self.assertEqual(stale.status_code, 409)
                for other_client in (self.beta_client, self.admin_client):
                    unaffected = await self.get_json(other_client, f"/v1/admin/skills/{slug}")
                    self.assertEqual(unaffected["content"], item["content"])
                    self.assertEqual(unaffected["revision"], item["revision"])
                    self.assertEqual(unaffected["enabled"], item["enabled"])
                    self.assertEqual(unaffected["required"], item["required"])
            for method, path in (
                ("GET", "/v1/admin/skills/custom"), ("PUT", "/v1/admin/skills/custom"),
                ("POST", "/v1/admin/skills/custom/prepare"),
                ("GET", f"/v1/admin/skills/{REQUIRED_SKILLS[0]}?source=github_draft"),
            ):
                kwargs = {"json": {"slug": "custom", "content": "Draft text"}} if method == "PUT" else {}
                self.assertEqual((await self.alpha_client.request(method, path, **kwargs)).status_code, 403)
            github.assert_not_called()
        without_pin = await self.client()
        without_pin.cookies.update(self.alpha_client.cookies)
        without_pin.headers.pop("X-Admin-Pin")
        self.assertEqual((await without_pin.get("/v1/admin/skills")).status_code, 401)

    async def test_sessions_and_tenant_cognition_survive_runtime_restart(self):
        before = await self.get_json(self.alpha_client, "/v1/mind")
        await self.lifespan.__aexit__(None, None, None)
        self.lifespan = api.lifespan(api.app)
        await self.lifespan.__aenter__()
        after = await self.get_json(self.alpha_client, "/v1/mind")
        self.assertEqual(after, before)
        self.assertEqual((await self.beta_client.get("/v1/mind")).status_code, 200)
        self.assertIsNone(await api.app.state.mind_store.load())

    async def test_tenant_requests_reuse_the_owned_connection_without_closing_it(self):
        with patch("aicognitive_mind.api.create_storage", side_effect=AssertionError(
            "A tenant request must not reopen the embedded database"
        )) as create, patch.object(api.app.state.runtime, "close", new_callable=AsyncMock) as close:
            for client in (self.alpha_client, self.beta_client):
                self.assertEqual((await client.get("/v1/mind")).status_code, 200)
                self.assertEqual((await client.get("/v1/portal/status")).status_code, 200)
            create.assert_not_called()
            close.assert_not_awaited()
        await api.app.state.runtime.ping()

    async def test_configured_voice_mime_matches_the_provider_audio(self):
        class WavAudio(bytes):
            media_type = "audio/wav"

        dispatcher = SimpleNamespace(
            is_configured=AsyncMock(return_value=True),
            execute=AsyncMock(return_value=WavAudio(b"RIFFsynthetic-wave-audio")),
        )
        with patch("aicognitive_mind.api.TaskModelDispatcher", return_value=dispatcher), patch(
            "aicognitive_mind.api.FishAudioRenderer",
        ) as fish:
            response = await self.alpha_client.post(
                "/v1/body/speech/fish-audio", json={"text": "Synthetic configured voice"},
            )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.headers["content-type"], "audio/wav")
        self.assertEqual(response.content, b"RIFFsynthetic-wave-audio")
        self.assertEqual(response.headers["cache-control"], "no-store")
        dispatcher.execute.assert_awaited_once()
        fish.assert_not_called()

    async def test_account_body_pages_voice_preferences_and_output_receipts_are_isolated(self):
        for client in (self.alpha_client, self.beta_client, self.admin_client):
            for path in ("/body/live", "/body/eyes", "/body/ears", "/body/face", "/body/mouth"):
                response = await client.get(path)
                self.assertEqual(response.status_code, 200, response.text)
        saved = await self.alpha_client.post("/v1/admin/body/voice/settings", json={
            "expected_revision": 0, "voice_name": "Alpha voice", "rate": 1.3,
            "fish_audio_api_key": "synthetic-alpha-fish-key", "fish_audio_reference_id": "alpha-reference",
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        alpha_voice = await self.get_json(self.alpha_client, "/v1/body/voice/settings")
        self.assertEqual(alpha_voice["voiceName"], "Alpha voice")
        self.assertEqual(alpha_voice["fishAudioReferenceId"], "alpha-reference")
        self.assertNotIn("fishAudioApiKey", alpha_voice)
        for client in (self.beta_client, self.admin_client):
            other_voice = await self.get_json(client, "/v1/body/voice/settings")
            self.assertEqual(other_voice["voiceName"], "")
            self.assertNotEqual(other_voice["fishAudioReferenceId"], "alpha-reference")

        with patch("aicognitive_mind.api.FishAudioRenderer") as renderer:
            renderer.return_value.synthesize = AsyncMock(return_value=b"synthetic-alpha-audio")
            speech = await self.alpha_client.post("/v1/body/speech/fish-audio", json={"text": "Alpha voice"})
            self.assertEqual(speech.status_code, 200, speech.text)
            self.assertEqual(speech.content, b"synthetic-alpha-audio")
            renderer.assert_called_once_with(
                api_key="synthetic-alpha-fish-key", model="s2.1-pro-free", reference_id="alpha-reference",
            )

        headers = {"X-Body-Session": "same-session"}
        spoken = await self.alpha_client.post("/v1/body/mouth/speak", headers=headers, json={"text": "Alpha output"})
        self.assertEqual(spoken.status_code, 200, spoken.text)
        expression = await self.alpha_client.post("/v1/body/face/expression", headers=headers, json={
            "text": "Alpha expression", "expression": "happy", "weight": 0.5,
        })
        self.assertEqual(expression.status_code, 200, expression.text)
        for client in (self.beta_client, self.admin_client):
            for modality in ("mouth", "face"):
                self.assertIsNone(await self.get_json(client, f"/v1/body/{modality}/next", headers=headers))
        for modality in ("mouth", "face"):
            output = await self.alpha_client.get(f"/v1/body/{modality}/next", headers=headers)
            self.assertEqual(output.status_code, 200, output.text)
            receipt = output.headers["X-Body-Delivery"]
            self.assertIn("Alpha", output.json()["text"])
            other_ack = await self.beta_client.post(f"/v1/body/{modality}/ack?delivery_id={receipt}", headers=headers)
            self.assertEqual(other_ack.status_code, 200)
            still_pending = await self.alpha_client.get(f"/v1/body/{modality}/next", headers=headers)
            self.assertEqual(still_pending.headers["X-Body-Delivery"], receipt)
            own_ack = await self.alpha_client.post(f"/v1/body/{modality}/ack?delivery_id={receipt}", headers=headers)
            self.assertEqual(own_ack.status_code, 200)
            self.assertIsNone(await self.get_json(self.alpha_client, f"/v1/body/{modality}/next", headers=headers))

    async def test_body_interactions_and_sensory_evidence_use_only_the_authenticated_mind(self):
        headers = {"X-Body-Session": "same-session"}
        with patch.object(api.app.state.mind_body, "interact", new_callable=AsyncMock) as root_interact:
            for client, word in ((self.alpha_client, "alpha"), (self.beta_client, "beta")):
                response = await client.post("/v1/mind/body/interact", headers=headers, json={
                    "message": "Synthetic " + word + " Body note",
                })
                self.assertEqual(response.status_code, 200, response.text)
                self.assertIn(word, response.json()["response_text"])
            root_interact.assert_not_awaited()
        with patch("aicognitive_mind.api.HostAwareInterpreter.interpret_automatically", new_callable=AsyncMock,
                   return_value="A person is speaking nearby"):
            for path, payload in (
                ("/v1/body/eyes/observe", {"image_data_url": "data:image/jpeg;base64,c3ludGhldGljLWltYWdl", "width": 10, "height": 10}),
                ("/v1/body/ears/observe", {"audio_data_url": "data:audio/webm;base64,c3ludGhldGljLWF1ZGlv", "duration_ms": 1000}),
            ):
                response = await self.alpha_client.post(path, headers=headers, json=payload)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["interpretation"], "A person is speaking nearby")
        for client, own, other in ((self.alpha_client, "alpha", "beta"), (self.beta_client, "beta", "alpha")):
            memories = await self.get_json(client, "/v1/mind/memory")
            self.assertIn(own + " Body note", str(memories))
            self.assertNotIn(other + " Body note", str(memories))
        alpha_evidence = await self.get_json(self.alpha_client, "/v1/portal/evidence")
        self.assertEqual(alpha_evidence["total"], 2)
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 0)
        self.assertTrue(api.app.state.presence.active(scope=(self.alpha.mind_id, "same-session")))
        self.assertFalse(api.app.state.presence.active(scope=(self.beta.mind_id, "same-session")))
        self.assertEqual(await api.app.state.memory_store.read(), [])
        self.assertEqual(await api.app.state.journal_store.read(), [])
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def test_automatic_senses_default_to_account_host_with_preserved_evidence(self):
        storage = scope_storage(api.app.state.storage, self.alpha.mind_id)
        service = SimpleNamespace(begin_interaction=AsyncMock(), complete_interaction=AsyncMock())
        host = HostRuntime(storage.mind, service)
        attached = await host.attach("Synthetic parallel host", "synthetic-multimodal")
        token = attached["lease_token"]
        headers = {"X-Body-Session": "parallel-senses"}
        # Force the host handoff to rely on the preserved artifact rather than a
        # large inline media prompt. The original bytes remain retrievable.
        image = b"synthetic-alpha-image-" * 10_000
        audio = b"synthetic-alpha-audio"
        requests = [
            ("vision", "/v1/body/eyes/observe", image, {
                "image_data_url": "data:image/jpeg;base64," + base64.b64encode(image).decode(),
                "width": 640, "height": 480,
            }),
            ("audio", "/v1/body/ears/observe", audio, {
                "audio_data_url": "data:audio/webm;base64," + base64.b64encode(audio).decode(),
                "duration_ms": 1_000,
            }),
        ]
        waiting = [asyncio.create_task(self.alpha_client.post(path, headers=headers, json=payload))
                   for _modality, path, _media, payload in requests]
        try:
            async def wait_for_both():
                while True:
                    pending = await host.records.pending()
                    if len(pending) == 2:
                        return pending
                    await asyncio.sleep(0.01)

            pending = await asyncio.wait_for(wait_for_both(), timeout=5)
            self.assertTrue(all(not task.done() for task in waiting))
            self.assertEqual({item["task"] for item in pending}, {"sensory_interpretation"})
            self.assertEqual({item["priority"] for item in pending}, {10})
            self.assertEqual({item["body_session"] for item in pending}, {"parallel-senses"})
            self.assertEqual(await RuntimeRecords(
                scope_storage(api.app.state.storage, self.beta.mind_id).mind,
            ).pending(), [])
            self.assertEqual(await api.app.state.runtime_records.pending(), [])

            claimed = [await asyncio.wait_for(host.next_request(token), timeout=3) for _ in requests]
            self.assertEqual(len({item["request_id"] for item in claimed}), 2)
            for item in claimed:
                context = item["context"]
                self.assertEqual(context["status"], "sensory_interpretation")
                self.assertEqual(context["task"], "sensory_interpretation")
                evidence = context["input_context"]["evidence"]
                self.assertIn(evidence["sha256"], item["user_message"])
                self.assertIn(evidence["captured_at"], item["user_message"])
            self.assertNotIn(base64.b64encode(image).decode(), str(claimed))
            service.begin_interaction.assert_not_awaited()

            observations = {
                "vision": "Visual perception: A red mug is visible.",
                "audio": "Auditory perception: A person says hello.",
            }
            # The independent worker may complete the two requests in either
            # order without blocking the browser caller or mixing the results.
            for item in reversed(claimed):
                modality = item["context"]["input_context"]["modality"]
                await host.complete(token, item["request_id"], observations[modality])
            results = await asyncio.wait_for(asyncio.gather(*waiting), timeout=5)
            for (modality, _path, media, _payload), result in zip(requests, results, strict=True):
                self.assertEqual(result.status_code, 200, result.text)
                body = result.json()
                self.assertEqual(body["interpretation"], observations[modality])
                self.assertEqual(body["response_text"], "")
                self.assertEqual(body["evidence"]["sha256"], hashlib.sha256(media).hexdigest())
                evidence_path = "/v1/evidence/" + body["evidence"]["sha256"]
                params = {"captured_at": body["evidence"]["captured_at"]}
                original = await self.alpha_client.get(evidence_path, params=params)
                self.assertEqual(original.status_code, 200, original.text)
                self.assertEqual(original.content, media)
                self.assertEqual((await self.beta_client.get(evidence_path, params=params)).status_code, 404)
            service.complete_interaction.assert_not_awaited()
            self.assertEqual(await host.records.pending(), [])
        finally:
            for task in waiting:
                task.cancel()
            await asyncio.gather(*waiting, return_exceptions=True)

        journal = await self.get_json(self.alpha_client, "/v1/mind/journal")
        self.assertEqual([entry["kind"] for entry in journal], ["sensory_evidence"] * 4)
        self.assertEqual(sorted(entry["experience"]["status"] for entry in journal),
                         ["admitted", "admitted", "interpreted", "interpreted"])
        self.assertNotIn("data:image", str(journal))
        self.assertEqual((await self.get_json(self.alpha_client, "/v1/portal/evidence"))["total"], 2)
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 0)
        for modality in ("mouth", "face"):
            self.assertIsNone(await self.get_json(self.alpha_client, f"/v1/body/{modality}/next", headers=headers))
        self.assertEqual(await api.app.state.journal_store.read(), [])
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def test_explicit_passive_failure_returns_without_false_interpretation(self):
        storage = scope_storage(api.app.state.storage, self.alpha.mind_id)
        service = SimpleNamespace(begin_interaction=AsyncMock(), complete_interaction=AsyncMock())
        host = HostRuntime(storage.mind, service)
        lease = (await host.attach("Synthetic unsupported-media host", "test-model"))["lease_token"]
        headers = {"X-Body-Session": "explicit-sensory-failure"}
        waiting = []
        expected = {}
        try:
            for modality, path, media_type, payload in (
                ("vision", "/v1/body/eyes/observe", "image/jpeg", {"width": 10, "height": 10}),
                ("audio", "/v1/body/ears/observe", "audio/webm", {"duration_ms": 1000}),
            ):
                media = ("preserved synthetic " + modality).encode()
                expected[hashlib.sha256(media).hexdigest()] = media
                payload["image_data_url" if modality == "vision" else "audio_data_url"] = (
                    "data:" + media_type + ";base64," + base64.b64encode(media).decode()
                )
                waiting.append(asyncio.create_task(self.alpha_client.post(path, headers=headers, json=payload)))
            for _ in range(200):
                if len(await host.records.pending()) == 2:
                    break
                await asyncio.sleep(0.01)
            else:
                self.fail("Both preserved sensory inputs must reach the host")
            for _ in waiting:
                claim = await asyncio.wait_for(host.next_request(lease), timeout=3)
                result = await host.fail(
                    lease, claim["request_id"], "The current host cannot interpret this media.",
                )
                self.assertEqual(result["status"], "failed")
            for response in await asyncio.wait_for(asyncio.gather(*waiting), timeout=3):
                self.assertEqual(response.status_code, 503, response.text)
                self.assertIn("Sensory evidence was saved", response.json()["detail"])
                self.assertIn("cannot interpret", response.json()["detail"])
        finally:
            for task in waiting:
                task.cancel()
            await asyncio.gather(*waiting, return_exceptions=True)

        evidence = await self.get_json(self.alpha_client, "/v1/portal/evidence")
        self.assertEqual(evidence["total"], 2)
        for item in evidence["items"]:
            endpoint = "/v1/evidence/" + item["sha256"]
            params = {"captured_at": item["captured_at"]}
            original = await self.alpha_client.get(endpoint, params=params)
            self.assertEqual(original.status_code, 200, original.text)
            self.assertEqual(original.content, expected[item["sha256"]])
            self.assertEqual((await self.beta_client.get(endpoint, params=params)).status_code, 404)
        journal = await self.get_json(self.alpha_client, "/v1/mind/journal")
        self.assertEqual([entry["kind"] for entry in journal], ["sensory_evidence"] * 2)
        self.assertEqual([entry["experience"]["status"] for entry in journal], ["admitted"] * 2)
        self.assertEqual(await host.records.pending(), [])
        service.begin_interaction.assert_not_awaited()
        service.complete_interaction.assert_not_awaited()
        for modality in ("mouth", "face"):
            self.assertIsNone(await self.get_json(self.alpha_client, f"/v1/body/{modality}/next", headers=headers))
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 0)
        self.assertEqual(await api.app.state.journal_store.read(), [])
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def _queued_host_audio(self, session, *, conversation=False):
        storage = scope_storage(api.app.state.storage, self.alpha.mind_id)
        host = HostRuntime(storage.mind, SimpleNamespace())
        lease = (await host.attach("Synthetic private ASR receiver", "synthetic-asr-model"))["lease_token"]
        media = b"synthetic preserved audio for private preprocessing"
        task = asyncio.create_task(self.alpha_client.post(
            "/v1/body/ears/observe", headers={"X-Body-Session": session}, json={
                "audio_data_url": "data:audio/webm;base64," + base64.b64encode(media).decode(),
                "duration_ms": 1000,
                "conversation": conversation,
            },
        ))

        async def cancel_waiter():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        self.stack.push_async_callback(cancel_waiter)
        for _ in range(200):
            pending = await host.records.pending()
            if pending:
                capability = {
                    "mind_id": self.alpha.mind_id, "lease_token": lease,
                    "request_id": pending[0]["request_id"],
                }
                return host, task, media, capability, pending[0]
            await asyncio.sleep(0.01)
        self.fail("Preserved audio did not reach the private host queue")

    async def test_intentional_audio_crosses_normal_host_lifecycle_and_returns_scoped_voice(self):
        session = "intentional-spoken-conversation"
        host, waiting, media, capability, original = await self._queued_host_audio(session, conversation=True)
        host.service = SimpleNamespace(
            begin_interaction=AsyncMock(return_value={"status": "ready_to_reason"}),
            complete_interaction=AsyncMock(return_value={
                "status": "interaction_committed", "occurred_at": "2026-10-27T05:00:00Z",
            }),
        )
        anonymous = await self.client()
        evidence = original["input_context"]["evidence"]
        transcript = {
            **capability, "sha256": evidence["sha256"], "captured_at": evidence["captured_at"],
            "transcript": "Can you hear me?", "model": "synthetic-asr",
            "segments": [{"text": "Can you hear me?", "avg_logprob": -0.2, "no_speech_probability": 0.01}],
        }
        self.assertEqual((await anonymous.post("/v1/host-events/input", json=capability)).status_code, 200)
        attached = await anonymous.post("/v1/host-events/transcript", json=transcript)
        self.assertEqual(attached.status_code, 200, attached.text)
        sensory = await host.next_request(capability["lease_token"])
        self.assertEqual(sensory["context"]["status"], "sensory_interpretation")
        observed = await host.complete(capability["lease_token"], sensory["request_id"], "Speech observed.")
        self.assertEqual(observed["derived_audio"], attached.json()["derived_audio"])
        host.service.begin_interaction.assert_not_awaited()
        for _ in range(200):
            pending = await host.records.pending()
            if pending:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(pending, "Intentional speech did not reach the conversation queue")
        conversation = await host.next_request(capability["lease_token"])
        self.assertEqual(conversation["user_message"], "Can you hear me?")
        context = conversation["context"]["input_context"]
        self.assertEqual(context["evidence"], evidence)
        self.assertEqual(context["derived_audio"], attached.json()["derived_audio"])
        self.assertEqual(context["speaker_identity"], "unresolved")
        host.service.begin_interaction.assert_awaited_once()
        await host.complete(capability["lease_token"], conversation["request_id"], "Yes, your recording reached me.")
        response = await asyncio.wait_for(waiting, timeout=3)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["response_text"], "Yes, your recording reached me.")
        host.service.complete_interaction.assert_awaited_once()
        self.assertEqual(host.service.complete_interaction.await_args.kwargs["source"], "body:audio")
        for modality in ("mouth", "face"):
            intent = await self.get_json(self.alpha_client, f"/v1/body/{modality}/next", headers={"X-Body-Session": session})
            self.assertEqual(intent["text"], "Yes, your recording reached me.")
            self.assertIsNone(await self.get_json(self.beta_client, f"/v1/body/{modality}/next", headers={"X-Body-Session": session}))
        self.assertEqual(await api.app.state.evidence_store.read(), [])


    async def test_private_audio_preprocessing_binds_capability_and_original_evidence(self):
        host, waiting, media, capability, original = await self._queued_host_audio("private-asr-boundary")
        anonymous = await self.client()
        route = "/v1/host-events/"
        evidence = original["input_context"]["evidence"]
        transcript = {
            **capability, "sha256": evidence["sha256"], "captured_at": evidence["captured_at"],
            "transcript": "Synthetic transcript only", "model": "synthetic-asr-model",
            "segments": [{"start": 0.0, "end": 0.5, "text": "Synthetic transcript only"}],
        }
        for suffix, payload in (("input", capability), ("transcript", transcript),
                                ("fail", {**capability, "reason": "Unavailable"})):
            for invalid in ({"mind_id": self.beta.mind_id}, {"lease_token": "synthetic-wrong-capability"}):
                rejected = await anonymous.post(route + suffix, json={**payload, **invalid})
                self.assertEqual(rejected.status_code, 401, rejected.text)
            self.assertEqual((await anonymous.post(route + suffix + "/other", json=payload)).status_code, 401)
        self.assertEqual(await host.records.get(capability["request_id"]), original)

        prepared = await anonymous.post(route + "input", json=capability)
        self.assertEqual(prepared.status_code, 200, prepared.text)
        self.assertEqual(base64.b64decode(prepared.json()["audio_base64"]), media)
        self.assertEqual(prepared.json()["evidence"], evidence)
        self.assertNotIn(capability["lease_token"], prepared.text)
        owned = await host.records.get(capability["request_id"])
        self.assertTrue(owned["preparing_audio"])
        self.assertEqual(owned["claim"], (await host.require(capability["lease_token"]))["token_hash"])
        for invalid in ({"sha256": "0" * 64}, {"captured_at": "2020-01-01T00:00:00Z"}):
            rejected = await anonymous.post(route + "transcript", json={**transcript, **invalid})
            self.assertEqual(rejected.status_code, 400, rejected.text)
            self.assertEqual(await host.records.get(capability["request_id"]), owned)

        attached = await anonymous.post(route + "transcript", json=transcript)
        self.assertEqual(attached.status_code, 200, attached.text)
        derived = attached.json()["derived_audio"]
        self.assertEqual(derived["source"], "local_asr")
        self.assertEqual(derived["model"], transcript["model"])
        self.assertEqual(derived["sha256"], hashlib.sha256(media).hexdigest())
        self.assertEqual(derived["captured_at"], evidence["captured_at"])
        after = await host.records.get(capability["request_id"])
        self.assertEqual(after["state"], "pending")
        self.assertEqual(after["claim"], "")
        self.assertFalse(after["preparing_audio"])
        self.assertEqual(after["input_context"], {**original["input_context"], "derived_audio": derived})
        self.assertFalse(waiting.done())
        retry = await anonymous.post(route + "transcript", json=transcript)
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertEqual(retry.json(), attached.json())
        changed = await anonymous.post(route + "transcript", json={**transcript, "transcript": "Replacement"})
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(await host.records.get(capability["request_id"]), after)

        claim = await host.next_request(capability["lease_token"])
        self.assertEqual(claim["context"]["input_context"]["derived_audio"], derived)
        failed_payload = {**capability, "reason": "Synthetic boundary test cannot interpret the input."}
        failed = await anonymous.post(route + "fail", json=failed_payload)
        self.assertEqual(failed.status_code, 200, failed.text)
        repeated = await anonymous.post(route + "fail", json=failed_payload)
        self.assertEqual(repeated.json(), failed.json())
        response = await asyncio.wait_for(waiting, timeout=3)
        self.assertEqual(response.status_code, 503, response.text)
        self.assertIn("evidence was saved", response.json()["detail"])
        preserved = await self.alpha_client.get("/v1/evidence/" + evidence["sha256"], params={
            "captured_at": evidence["captured_at"],
        })
        self.assertEqual(preserved.content, media)
        journal = await self.get_json(self.alpha_client, "/v1/mind/journal")
        self.assertEqual([item["experience"]["status"] for item in journal], ["admitted"])
        for modality in ("mouth", "face"):
            self.assertIsNone(await self.get_json(
                self.alpha_client, f"/v1/body/{modality}/next", headers={"X-Body-Session": "private-asr-boundary"},
            ))
        self.assertEqual(await api.app.state.journal_store.read(), [])
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def test_private_transcript_cannot_overwrite_a_claim_or_completion_that_wins_a_race(self):
        host, _waiting, _media, capability, original = await self._queued_host_audio("private-asr-race")
        anonymous = await self.client()
        evidence = original["input_context"]["evidence"]
        payload = {
            **capability, "sha256": evidence["sha256"], "captured_at": evidence["captured_at"],
            "transcript": "Stale transcript", "model": "synthetic-asr-model", "segments": [],
        }
        # A normal perception claim must never be silently replaced by preprocessing.
        await host.next_request(capability["lease_token"])
        before = await host.records.get(capability["request_id"])
        for suffix, body in (("input", capability), ("transcript", payload)):
            rejected = await anonymous.post("/v1/host-events/" + suffix, json=body)
            self.assertEqual(rejected.status_code, 409, rejected.text)
            self.assertEqual(await host.records.get(capability["request_id"]), before)
        unclaimed = {**before, "claim": "", "claim_until": 0.0}
        self.assertTrue(await host.records.replace(capability["request_id"], before, unclaimed))
        prepared = await anonymous.post("/v1/host-events/input", json=capability)
        self.assertEqual(prepared.status_code, 200, prepared.text)
        before = await host.records.get(capability["request_id"])
        stale = {**before, "claim_until": time.time() - 1}
        self.assertTrue(await host.records.replace(capability["request_id"], before, stale))
        expired = await anonymous.post("/v1/host-events/transcript", json=payload)
        self.assertEqual(expired.status_code, 409, expired.text)
        self.assertEqual(await host.records.get(capability["request_id"]), stale)
        renewed = await anonymous.post("/v1/host-events/input", json=capability)
        self.assertEqual(renewed.status_code, 200, renewed.text)
        replace = RuntimeRecords.replace
        winner = {}

        async def complete_first(records, key, expected, replacement):
            if key == capability["request_id"] and "derived_audio" in replacement.get("input_context", {}):
                winner.update({**expected, "state": "complete", "result": {"synthetic": "race winner"}})
                self.assertTrue(await replace(records, key, expected, winner))
                return False
            return await replace(records, key, expected, replacement)

        with patch.object(RuntimeRecords, "replace", complete_first):
            rejected = await anonymous.post("/v1/host-events/transcript", json=payload)
        self.assertEqual(rejected.status_code, 409, rejected.text)
        stored = await host.records.get(capability["request_id"])
        self.assertEqual(stored, winner)
        self.assertNotIn("derived_audio", stored["input_context"])
        self.assertEqual(stored["input_context"], original["input_context"])

    async def test_private_preparation_recovers_after_transcript_transport_failure(self):
        host, waiting, _media, capability, original = await self._queued_host_audio("private-asr-retry")
        attempts = []
        config = ReceiverConfig(
            ready_url="http://testserver/v1/host-events/ready",
            mind_id=capability["mind_id"], lease_token=capability["lease_token"],
            thread_id="01a15495-861f-7602-ba9a-b63b3f4aeb10", app_tools_server=Path("fixture.mjs"),
            node_executable="node", pipe_path="synthetic-private-pipe", state_path=Path("unused"),
        )
        transcriber = SimpleNamespace(transcribe=Mock(return_value={
            "text": "Synthetic retry transcript",
            "transcription": {"engine": "synthetic-asr", "model": "test", "segments": []},
        }))
        sender = SimpleNamespace(send=AsyncMock())
        async with httpx.ASGITransport(app=api.app) as real_transport:
            async def respond(request):
                if request.url.path.endswith("/transcript"):
                    attempts.append(request.url.path)
                    if len(attempts) == 1:
                        return httpx.Response(503, json={"detail": "Synthetic transient upload failure"})
                return await real_transport.handle_async_request(request)

            with tempfile.TemporaryDirectory() as directory, patch.object(HostRuntime, "REQUEST_WAIT_SECONDS", 0):
                state = DeliveryState(Path(directory) / "delivery.json")
                async with httpx.AsyncClient(
                    transport=httpx.MockTransport(respond), base_url="http://testserver",
                ) as client:
                    receiver = BodyReceiver(config, client, sender, state, transcriber)
                    with self.assertRaisesRegex(ReceiverError, "transcript could not be attached"):
                        await receiver.once()
                    stranded = await host.records.get(capability["request_id"])
                    self.assertTrue(stranded["preparing_audio"])
                    self.assertEqual(stranded["state"], "pending")
                    sender.send.assert_not_awaited()
                    self.assertEqual(await receiver.once(), 1)
                    sender.send.assert_awaited_once()
                    self.assertEqual(len(attempts), 2)
                    after = await host.records.get(capability["request_id"])
                    self.assertEqual(after["input_context"]["derived_audio"]["transcript"],
                                     "Synthetic retry transcript")
                    self.assertEqual(after["input_context"]["evidence"], original["input_context"]["evidence"])
                    self.assertEqual(after["state"], "pending")
                    self.assertEqual(after["claim"], "")
                    self.assertFalse(waiting.done())
        # Preprocessing still leaves interpretation and its result to the actual host.
        claim = await host.next_request(capability["lease_token"])
        self.assertEqual(claim["context"]["input_context"]["derived_audio"]["transcript"],
                         "Synthetic retry transcript")
        await host.fail(capability["lease_token"], capability["request_id"], "Synthetic observer unavailable.")
        self.assertEqual((await asyncio.wait_for(waiting, timeout=3)).status_code, 503)

    async def test_automatic_sensory_timeout_preserves_original_evidence_without_interpreting(self):
        storage = scope_storage(api.app.state.storage, self.alpha.mind_id)
        host = HostRuntime(storage.mind, SimpleNamespace())
        await host.attach("Synthetic idle host", "synthetic-multimodal")
        beta_records = RuntimeRecords(scope_storage(api.app.state.storage, self.beta.mind_id).mind)
        beta_request = {
            "kind": "body_request", "request_id": "beta-human-unaffected", "state": "pending",
            "message": "Synthetic other-account message", "priority": 0, "created": time.time(),
            "deadline": None, "claim": "", "claim_until": 0.0, "result": {},
        }
        await beta_records.create(beta_request["request_id"], beta_request)
        beta_before = await beta_records.get(beta_request["request_id"])
        headers = {"X-Body-Session": "sensory-timeout"}
        media_by_hash = {}

        def short_lived_host(mind, service, timeout):
            return HostRuntime(mind, service, timeout=0.02)

        # Use the real authenticated routes, preservation, admission, queue and
        # deadline logic. Only shorten the host wait; no interpreter is mocked.
        with patch("aicognitive_mind.api.HostRuntime", side_effect=short_lived_host):
            for modality, path, media, payload in (
                ("vision", "/v1/body/eyes/observe", b"synthetic-timeout-image", {
                    "width": 10, "height": 10,
                }),
                ("audio", "/v1/body/ears/observe", b"synthetic-timeout-audio", {
                    "duration_ms": 1_000,
                }),
            ):
                media_type = "image/jpeg" if modality == "vision" else "audio/webm"
                payload["image_data_url" if modality == "vision" else "audio_data_url"] = (
                    "data:" + media_type + ";base64," + base64.b64encode(media).decode()
                )
                media_by_hash[hashlib.sha256(media).hexdigest()] = media
                response = await asyncio.wait_for(
                    self.alpha_client.post(path, headers=headers, json=payload), timeout=5,
                )
                self.assertEqual(response.status_code, 503, response.text)
                self.assertIn("Sensory evidence was saved", response.json()["detail"])
                self.assertIn("within 0.02 seconds", response.json()["detail"])

        evidence = await self.get_json(self.alpha_client, "/v1/portal/evidence")
        self.assertEqual(evidence["total"], 2)
        for item in evidence["items"]:
            evidence_path = "/v1/evidence/" + item["sha256"]
            params = {"captured_at": item["captured_at"]}
            original = await self.alpha_client.get(evidence_path, params=params)
            self.assertEqual(original.status_code, 200, original.text)
            self.assertEqual(original.content, media_by_hash[item["sha256"]])
            self.assertEqual((await self.beta_client.get(evidence_path, params=params)).status_code, 404)
        journal = await self.get_json(self.alpha_client, "/v1/mind/journal")
        self.assertEqual([entry["kind"] for entry in journal], ["sensory_evidence"] * 2)
        self.assertEqual([entry["experience"]["status"] for entry in journal], ["admitted"] * 2)
        self.assertEqual(await host.records.pending(), [])
        self.assertEqual((await host.status())["requests"]["in_progress"], 0)
        self.assertEqual(await beta_records.get(beta_request["request_id"]), beta_before)
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 0)
        for modality in ("mouth", "face"):
            self.assertIsNone(await self.get_json(self.alpha_client, f"/v1/body/{modality}/next", headers=headers))
        self.assertEqual(await api.app.state.journal_store.read(), [])
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def test_sensory_ready_callback_processes_account_media_without_live_host_or_chat_poll(self):
        """Only network transport and observations are synthetic; event routing is real."""
        import hmac
        from contextvars import ContextVar
        from urllib.parse import parse_qs, urlparse

        from fastapi import FastAPI, Request
        from mcp.server.auth.provider import AuthorizationParams
        from mcp.shared.auth import OAuthClientInformationFull
        from pydantic import AnyUrl
        from starlette.responses import JSONResponse

        from aicognitive_mind import account_mcp, mcp_events
        from aicognitive_mind.chatgpt_mcp import build_chatgpt_mcp
        from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
        from aicognitive_mind.mcp_server import AppState

        provider = AxiomAuthorizationServerProvider(
            "https://routing.example", username="synthetic-admin", password=PASSWORD,
            resource_path="/axiom-mcp",
        )
        provider._records = api.app.state.runtime_records
        provider.accounts = api.app.state.accounts
        oauth_client = OAuthClientInformationFull.model_validate({
            "client_id": "synthetic-sensory-events",
            "redirect_uris": ["https://callback.example/oauth"],
        })
        await provider.register_client(oauth_client)
        tokens = {}
        for account in (self.alpha, self.beta):
            subject = await provider.authenticate(account.username, PASSWORD)
            auth = AuthorizationParams(
                state="sensory-test", scopes=[provider.required_scope], code_challenge="test",
                redirect_uri=AnyUrl("https://callback.example/oauth"),
                redirect_uri_provided_explicitly=True, resource=provider.resource_url,
            )
            login = await provider.authorize(oauth_client, auth)
            request_id = parse_qs(urlparse(login).query)["request"][0]
            callback = await provider.approve(request_id, subject=subject)
            code_value = parse_qs(urlparse(callback).query)["code"][0]
            code = await provider.load_authorization_code(oauth_client, code_value)
            issued = await provider.exchange_authorization_code(oauth_client, code)
            tokens[account.mind_id] = await provider.load_access_token(issued.access_token)

        server = build_chatgpt_mcp("https://routing.example", provider)
        root_state = AppState(
            runtime=api.app.state.runtime, storage=api.app.state.storage,
            mind_service=api.app.state.mcp_service, hosts=api.app.state.hosts,
        )
        tool_context = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=root_state))
        event_context = SimpleNamespace(lifespan_context=root_state)
        current_access = ContextVar("sensory_ready_test_access", default=None)

        async def tool(name, account, **arguments):
            handle = current_access.set(tokens[account.mind_id])
            try:
                return await server._tool_manager.get_tool(name).fn(ctx=tool_context, **arguments)
            finally:
                current_access.reset(handle)

        async def event(method, account, arguments=None):
            entry = server._lowlevel_server._request_handlers[method]
            handle = current_access.set(tokens[account.mind_id])
            try:
                return await entry.handler(
                    event_context, entry.params_type.model_validate(arguments or {}),
                )
            finally:
                current_access.reset(handle)

        signing_key = bytes(range(32))
        secret = "whsec_" + base64.b64encode(signing_key).decode()
        received = []
        ready = asyncio.Queue()
        receiver = FastAPI()

        @receiver.post("/ready")
        async def callback(request: Request):
            wire = await request.body()
            signed = (
                request.headers["webhook-id"].encode() + b"."
                + request.headers["webhook-timestamp"].encode() + b"." + wire
            )
            expected = "v1," + base64.b64encode(hmac.digest(signing_key, signed, "sha256")).decode()
            self.assertTrue(hmac.compare_digest(request.headers["webhook-signature"], expected))
            payload = json.loads(wire)
            if payload.get("type") == "verification":
                return JSONResponse({"challenge": payload["challenge"]})
            self.assertEqual(request.headers["webhook-id"], payload["eventId"])
            received.append(payload)
            ready.put_nowait(payload)
            return JSONResponse({"received": True})

        # Preserve post_webhook's actual serialization and signature. Replace
        # only public-network delivery with the in-process callback application.
        async with AsyncExitStack() as stack:
            callback_client = await stack.enter_async_context(httpx.AsyncClient(
                transport=httpx.ASGITransport(receiver), base_url="https://callback.example",
            ))

            class ForwardedWebhook:
                def __init__(self, method, url, **kwargs):
                    self.method, self.url, self.kwargs = method, url, kwargs

                async def __aenter__(self):
                    self.reply = await callback_client.request(
                        self.method, "/ready", headers=self.kwargs["headers"],
                        content=self.kwargs["content"],
                    )
                    return self.reply

                async def __aexit__(self, *args):
                    await self.reply.aclose()

            class CallbackTransport:
                def __init__(self, **kwargs):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                def stream(self, method, url, **kwargs):
                    return ForwardedWebhook(method, url, **kwargs)

            stack.enter_context(patch.object(account_mcp, "get_access_token", current_access.get))
            stack.enter_context(patch.object(mcp_events, "get_access_token", current_access.get))
            stack.enter_context(patch.object(mcp_events, "_callback_target", AsyncMock(return_value=(
                "https://93.184.216.34/ready", "callback.example", "callback.example",
            ))))
            stack.enter_context(patch.object(mcp_events.httpx, "AsyncClient", CallbackTransport))

            catalog = await event("events/list", self.alpha)
            self.assertIn("sensory.ready", {item["name"] for item in catalog["events"]})
            await event("events/subscribe", self.alpha, {
                "name": "sensory.ready", "arguments": {"session_id": "callback-senses"},
                "delivery": {"mode": "webhook", "url": "https://callback.example/ready", "secret": secret},
            })
            alpha_storage = scope_storage(api.app.state.storage, self.alpha.mind_id)
            records = RuntimeRecords(alpha_storage.mind)
            beta_records = RuntimeRecords(scope_storage(api.app.state.storage, self.beta.mind_id).mind)
            await stack.enter_async_context(mcp_events.EventDeliveryWorker(
                api.app.state.storage, provider,
            ).running())
            observations = {"vision": "Synthetic visual observation", "audio": "Synthetic heard observation"}
            media = {"vision": b"synthetic-ready-image", "audio": b"synthetic-ready-audio"}

            async def consume_callbacks():
                for _ in range(2):
                    delivered = await asyncio.wait_for(ready.get(), timeout=5)
                    self.assertEqual(delivered["name"], "sensory.ready")
                    data = delivered["data"]
                    self.assertEqual(data["mind_id"], self.alpha.mind_id)
                    self.assertEqual(data["session_id"], "callback-senses")
                    request_id = data["request_id"]
                    with self.assertRaises(ValueError):
                        await tool("read_incoming_sensory", self.beta, request_id=request_id)
                    with self.assertRaises(ValueError):
                        await tool("claim_incoming_sensory", self.beta, request_id=request_id)
                    with self.assertRaises(ValueError):
                        await tool("claim_incoming_message", self.alpha, request_id=request_id)
                    claim = await tool("claim_incoming_sensory", self.alpha, request_id=request_id)
                    self.assertEqual(claim["status"], "claimed")
                    self.assertEqual((await tool(
                        "claim_incoming_sensory", self.alpha, request_id=request_id,
                    ))["status"], "in_progress")
                    self.assertEqual(claim["context"]["status"], "sensory_interpretation")
                    percept = claim["context"]["input_context"]
                    modality = percept["modality"]
                    evidence = percept["evidence"]
                    self.assertEqual(evidence["sha256"], hashlib.sha256(media[modality]).hexdigest())
                    self.assertNotIn("data:", json.dumps(delivered))
                    path = "/v1/evidence/" + evidence["sha256"]
                    params = {"captured_at": evidence["captured_at"]}
                    original = await self.alpha_client.get(path, params=params)
                    self.assertEqual(original.status_code, 200, original.text)
                    self.assertEqual(original.content, media[modality])
                    self.assertEqual((await self.beta_client.get(path, params=params)).status_code, 404)
                    arguments = {
                        "claim_token": claim["claim_token"], "request_id": request_id,
                        "response_text": observations[modality],
                    }
                    result = await tool("complete_incoming_sensory", self.alpha, **arguments)
                    self.assertEqual(await tool("complete_incoming_sensory", self.alpha, **arguments), result)
                    self.assertEqual((await tool(
                        "claim_incoming_sensory", self.alpha, request_id=request_id,
                    ))["status"], "already_complete")

            consumer = asyncio.create_task(consume_callbacks())
            waiting = []
            try:
                for modality, path, field, media_type, metadata in (
                    ("vision", "/v1/body/eyes/observe", "image_data_url", "image/jpeg", {"width": 10, "height": 10}),
                    ("audio", "/v1/body/ears/observe", "audio_data_url", "audio/webm", {"duration_ms": 1_000}),
                ):
                    payload = {**metadata, field: "data:" + media_type + ";base64," + base64.b64encode(media[modality]).decode()}
                    waiting.append(asyncio.create_task(self.alpha_client.post(
                        path, headers={"X-Body-Session": "callback-senses"}, json=payload,
                    )))
                    # The second observation arrives after the first completed.
                    # Its callback must wake the same consumer without a chat turn.
                    await asyncio.wait_for(waiting[-1], timeout=5)
                await asyncio.wait_for(consumer, timeout=10)
                replies = await asyncio.wait_for(asyncio.gather(*waiting), timeout=5)
                self.assertEqual({reply.json()["interpretation"] for reply in replies}, set(observations.values()))
                self.assertTrue(all(reply.status_code == 200 for reply in replies))
                self.assertTrue(all(reply.json()["response_text"] == "" for reply in replies))
            finally:
                consumer.cancel()
                for task in waiting:
                    task.cancel()
                await asyncio.gather(consumer, *waiting, return_exceptions=True)

            self.assertEqual(len(received), 2)
            self.assertTrue(ready.empty())
            self.assertEqual(await records.pending(), [])
            self.assertEqual(await beta_records.pending(), [])
            self.assertIsNone(await records.get("active_host"))
            self.assertIsNone(await beta_records.get(mcp_events.STATE_KEY))
            self.assertIsNone(await api.app.state.runtime_records.get(mcp_events.STATE_KEY))
            self.assertEqual((await records.get(mcp_events.STATE_KEY))["deliveries"], {})

        journal = await self.get_json(self.alpha_client, "/v1/mind/journal")
        self.assertEqual([item["kind"] for item in journal], ["sensory_evidence"] * 4)
        self.assertEqual(sorted(item["experience"]["status"] for item in journal),
                         ["admitted", "admitted", "interpreted", "interpreted"])
        for modality in ("mouth", "face"):
            self.assertIsNone(await self.get_json(
                self.alpha_client, f"/v1/body/{modality}/next", headers={"X-Body-Session": "callback-senses"},
            ))
        self.assertEqual(await api.app.state.journal_store.read(), [])
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def test_host_ready_endpoint_requires_exact_mind_capability_and_never_claims_work(self):
        storage = scope_storage(api.app.state.storage, self.alpha.mind_id)
        host = HostRuntime(storage.mind, SimpleNamespace())
        lease = (await host.attach("Synthetic local receiver", "synthetic-multimodal"))["lease_token"]
        beta = HostRuntime(scope_storage(api.app.state.storage, self.beta.mind_id).mind, SimpleNamespace())
        await beta.attach("Synthetic other receiver", "synthetic-other")
        now = time.time()
        sensory = {
            "kind": "body_request", "request_id": "ready-sensory", "state": "pending",
            "message": "data:image/jpeg;base64,synthetic-private-media", "priority": 10,
            "task": "sensory_interpretation", "input_context": {"evidence": {"synthetic": "private"}},
            "created": now - 1, "deadline": now + 120, "claim": "", "claim_until": 0.0,
            "result": {},
        }
        human = {
            "kind": "body_request", "request_id": "ready-human", "state": "pending",
            "message": "Synthetic private human text", "priority": 0, "created": now,
            "deadline": None, "claim": "", "claim_until": 0.0, "result": {},
        }
        await host.records.create(sensory["request_id"], sensory)
        await host.records.create(human["request_id"], human)
        before = {item["request_id"]: item for item in await host.records.pending()}
        anonymous = await self.client()
        payload = {"mind_id": self.alpha.mind_id, "lease_token": lease, "after_request_ids": []}
        with patch.object(HostRuntime, "REQUEST_WAIT_SECONDS", 0):
            response = await anonymous.post("/v1/host-events/ready", json=payload)
            self.assertEqual(response.status_code, 200, response.text)
            ready = response.json()["requests"]
            self.assertEqual([item["request_id"] for item in ready], ["ready-human", "ready-sensory"])
            self.assertEqual([item["kind"] for item in ready], ["human", "sensory"])
            for item in ready:
                self.assertEqual(set(item), {"request_id", "kind", "created", "deadline"})
            for private in (lease, human["message"], sensory["message"], "input_context", "evidence", "claim"):
                self.assertNotIn(private, response.text)
            self.assertEqual({item["request_id"]: item for item in await host.records.pending()}, before)
            excluded = await anonymous.post("/v1/host-events/ready", json={
                **payload, "after_request_ids": ["ready-human", "ready-sensory"],
            })
            self.assertEqual(excluded.status_code, 200, excluded.text)
            self.assertEqual(excluded.json(), {"requests": [], "finished_request_ids": []})
            partial = await anonymous.post("/v1/host-events/ready", json={
                **payload, "after_request_ids": ["ready-human"],
            })
            self.assertEqual([item["request_id"] for item in partial.json()["requests"]], ["ready-sensory"])
            for invalid in (
                {**payload, "lease_token": "synthetic-wrong-capability"},
                {**payload, "mind_id": self.beta.mind_id},
                {**payload, "mind_id": "synthetic-unknown-mind"},
            ):
                failed = await anonymous.post("/v1/host-events/ready", json=invalid)
                self.assertEqual(failed.status_code, 401, failed.text)
                self.assertEqual(failed.json()["detail"], "Invalid host capability")
            self.assertEqual((await anonymous.get("/v1/mind")).status_code, 401)
            self.assertEqual((await anonymous.get("/v1/body/hosts/status")).status_code, 401)
            self.assertEqual((await anonymous.post("/v1/body/eyes/observe", json={
                "image_data_url": "data:image/jpeg;base64,c3ludGhldGlj", "width": 10, "height": 10,
            })).status_code, 401)
            self.assertEqual((await anonymous.post("/v1/host-events/ready/other", json=payload)).status_code, 401)
            await host.renew(lease, detach=True)
            detached = await anonymous.post("/v1/host-events/ready", json=payload)
            self.assertEqual(detached.status_code, 401, detached.text)
        self.assertEqual(await beta.records.pending(), [])
        self.assertEqual(await api.app.state.runtime_records.pending(), [])

    async def test_automatic_senses_without_own_host_do_not_use_another_account(self):
        alpha_host = HostRuntime(
            scope_storage(api.app.state.storage, self.alpha.mind_id).mind,
            SimpleNamespace(begin_interaction=AsyncMock(), complete_interaction=AsyncMock()),
        )
        await alpha_host.attach("Alpha host only", "synthetic-multimodal")
        for path, payload in (
            ("/v1/body/eyes/observe", {
                "image_data_url": "data:image/jpeg;base64,c3ludGhldGljLWltYWdl", "width": 10, "height": 10,
            }),
            ("/v1/body/ears/observe", {
                "audio_data_url": "data:audio/webm;base64,c3ludGhldGljLWF1ZGlv", "duration_ms": 1_000,
            }),
        ):
            result = await asyncio.wait_for(self.beta_client.post(path, json=payload), timeout=3)
            self.assertEqual(result.status_code, 503, result.text)
            self.assertIn("host", result.json()["detail"].lower())
        self.assertEqual(await alpha_host.records.pending(), [])
        self.assertEqual(await RuntimeRecords(
            scope_storage(api.app.state.storage, self.beta.mind_id).mind,
        ).pending(), [])
        journal = await self.get_json(self.beta_client, "/v1/mind/journal")
        self.assertEqual([item["experience"]["status"] for item in journal], ["admitted", "admitted"])
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 2)
        self.assertEqual((await self.get_json(self.alpha_client, "/v1/portal/evidence"))["total"], 0)

    async def test_configured_automatic_sensory_specialists_do_not_enqueue_host_work(self):
        saved = await self.alpha_client.put("/v1/admin/provider-endpoints", json={"items": [{
            "id": "alpha-sensory", "name": "Alpha sensory", "provider_name": "synthetic",
            "base_url": "https://synthetic.invalid/v1", "api_key": "synthetic-alpha-key", "model": "sensory-model",
        }]})
        self.assertEqual(saved.status_code, 200, saved.text)
        assignments = (await self.get_json(self.alpha_client, "/v1/admin/task-model-assignments"))["items"]
        for item in assignments:
            if item["task"] in {"vision", "audio"}:
                item.update(provider="alpha-sensory", model="sensory-model")
        saved = await self.alpha_client.put("/v1/admin/task-model-assignments", json={"items": assignments})
        self.assertEqual(saved.status_code, 200, saved.text)
        seen = []

        async def interpret(dispatcher, percept, *, focus=None):
            seen.append((dispatcher.assignments.records.mind_id, percept))
            return "Specialist " + percept.modality.value + " observation"

        with patch("aicognitive_mind.task_dispatcher.TaskModelDispatcher.interpret_percept", new=interpret):
            for modality, path, payload in (
                ("vision", "/v1/body/eyes/observe", {
                    "image_data_url": "data:image/jpeg;base64,c3ludGhldGljLWltYWdl", "width": 10, "height": 10,
                }),
                ("audio", "/v1/body/ears/observe", {
                    "audio_data_url": "data:audio/webm;base64,c3ludGhldGljLWF1ZGlv", "duration_ms": 1_000,
                }),
            ):
                response = await asyncio.wait_for(self.alpha_client.post(path, json=payload), timeout=3)
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["interpretation"], "Specialist " + modality + " observation")
                self.assertEqual(seen[-1][1].metadata["evidence"], response.json()["evidence"])
        self.assertEqual({mind_id for mind_id, _percept in seen}, {self.alpha.mind_id})
        self.assertEqual(await RuntimeRecords(
            scope_storage(api.app.state.storage, self.alpha.mind_id).mind,
        ).pending(), [])
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 0)

    async def test_body_see_and_hear_cannot_consume_another_accounts_queued_observations(self):
        headers = {"X-Body-Session": "same-session"}
        records = RuntimeRecords(scope_storage(api.app.state.storage, self.alpha.mind_id).mind)
        queues = [
            ("eyes", "see", api.BrowserVisionIngress(), {
                "image_data_url": "data:image/jpeg;base64,c3ludGhldGljLWltYWdl", "width": 10, "height": 10,
            }),
            ("ears", "hear", api.BrowserAudioIngress(), {
                "audio_data_url": "data:audio/webm;base64,c3ludGhldGljLWF1ZGlv", "duration_ms": 1000,
            }),
        ]
        token = api.body_session.set("same-session")
        try:
            for modality, action, adapter, payload in queues:
                await api.BodyQueue(records, modality, adapter).accept(**payload)
        finally:
            api.body_session.reset(token)
        with patch("aicognitive_mind.api.HostAwareInterpreter.interpret", new_callable=AsyncMock,
                   return_value="A person is speaking nearby"):
            for modality, action, _adapter, _payload in queues:
                for client in (self.beta_client, self.admin_client):
                    direct = await client.get(f"/v1/body/{modality}/{action}", headers=headers)
                    self.assertEqual(direct.status_code, 409, direct.text)
                    cognitive = await client.post(f"/v1/mind/body/{action}?express=false", headers=headers)
                    self.assertEqual(cognitive.status_code, 409, cognitive.text)
                own = await self.alpha_client.post(f"/v1/mind/body/{action}?express=false", headers=headers)
                self.assertEqual(own.status_code, 200, own.text)
                self.assertEqual(own.json()["interpretation"], "A person is speaking nearby")
        self.assertEqual((await self.get_json(self.alpha_client, "/v1/portal/evidence"))["total"], 2)
        self.assertEqual((await self.get_json(self.beta_client, "/v1/portal/evidence"))["total"], 0)
        self.assertEqual(await api.app.state.evidence_store.read(), [])

    async def test_body_sessions_hosts_and_camera_requests_are_account_scoped(self):
        headers = {"X-Body-Session": "same-session"}
        records = {}
        for client, account, label in ((self.alpha_client, self.alpha, "alpha"), (self.beta_client, self.beta, "beta")):
            records[label] = RuntimeRecords(scope_storage(api.app.state.storage, account.mind_id).mind)
            await records[label].create("camera_request", {
                "kind": "camera_request", "request_id": label + "-camera", "state": "pending",
                "seconds": 3, "deadline": time.time() + 60, "created": time.time(), "result": {},
            })
            registration = await client.post("/v1/body/session/active", headers=headers)
            self.assertEqual(registration.status_code, 200, registration.text)
            self.assertEqual((await records[label].get("active_body_session"))["session_id"], "same-session")
            camera = await self.get_json(client, "/v1/body/camera/request", headers=headers)
            self.assertEqual(camera["request_id"], label + "-camera")
        self.assertIsNone(await api.app.state.runtime_records.get("active_body_session"))
        self.assertIsNone(await self.get_json(self.admin_client, "/v1/body/camera/request", headers=headers))
        result = {"request_id": "alpha-camera", "image_data_url": "data:image/jpeg;base64,c3ludGhldGljLWltYWdl", "width": 10, "height": 10}
        denied = await self.beta_client.post("/v1/body/camera/complete", headers=headers, json=result)
        self.assertEqual(denied.status_code, 409)
        completed = await self.alpha_client.post("/v1/body/camera/complete", headers=headers, json=result)
        self.assertEqual(completed.status_code, 200, completed.text)
        self.assertEqual((await records["alpha"].get("camera_request"))["state"], "complete")
        self.assertEqual((await records["beta"].get("camera_request"))["state"], "pending")
        with patch.object(api.app.state.hosts, "status", new_callable=AsyncMock) as root_status:
            for client in (self.alpha_client, self.beta_client):
                status = await self.get_json(client, "/v1/body/hosts/status")
                self.assertFalse(status["connected"])
                self.assertFalse(status["realtime"]["available"])
                self.assertEqual(status["realtime"]["reason"], "Realtime voice is not configured.")
            root_status.assert_not_awaited()

    async def test_realtime_capability_uses_server_broker_without_exposing_its_key(self):
        for key in (None, "synthetic-server-realtime-key"):
            configured = self.settings.model_copy(update={"openai_api_key": key})
            with patch("aicognitive_mind.api.get_settings", return_value=configured):
                markers = []
                for client in (self.alpha_client, self.beta_client):
                    status = await self.get_json(client, "/v1/body/hosts/status")
                    self.assertEqual(status["realtime"]["available"], bool(key))
                    self.assertEqual(status["realtime"]["reason"], "" if key else "Realtime voice is not configured.")
                    marker = status["realtime"]["scope"]
                    self.assertEqual(marker, api.realtime_session_scope(client.cookies["axiom_portal_session"]))
                    self.assertNotIn(client.cookies["axiom_portal_session"], json.dumps(status))
                    markers.append(marker)
                    self.assertNotIn("synthetic-server-realtime-key", json.dumps(status))
                self.assertNotEqual(*markers)
                root = (await self.get_json(self.admin_client, "/v1/body/hosts/status"))["realtime"]
                self.assertFalse(root["available"])
                self.assertIsNone(root["scope"])
                self.assertEqual(root["reason"], "Sign in to Axiom before starting voice.")

    async def test_account_body_never_inherits_deployment_provider_credentials(self):
        global_settings = self.settings.model_copy(update={
            "standalone_reasoning_provider": "openai", "openai_api_key": "synthetic-root-openai-key",
            "gemini_api_key": "synthetic-root-gemini-key", "fish_audio_api_key": "synthetic-root-fish-key",
            "fish_audio_reference_id": "root-voice-reference",
        })
        with patch("aicognitive_mind.api.get_settings", return_value=global_settings), patch(
            "aicognitive_mind.config.get_settings", return_value=global_settings,
        ), patch("aicognitive_mind.api.StandaloneRuntime", wraps=StandaloneRuntime) as runtime, patch(
            "aicognitive_mind.engines.OpenAIReasoningEngine",
        ) as openai, patch("aicognitive_mind.engines.GeminiReasoningEngine") as gemini, patch(
            "aicognitive_mind.api.FishAudioRenderer",
        ) as fish:
            response = await self.alpha_client.post("/v1/mind/body/interact", json={"message": "No shared providers"})
            self.assertEqual(response.status_code, 502, response.text)
            voice = await self.get_json(self.alpha_client, "/v1/admin/body/voice/settings")
            self.assertEqual(voice["fishAudioApiKey"], "")
            self.assertIsNone(voice["fishAudioReferenceId"])
            speech = await self.alpha_client.post("/v1/body/speech/fish-audio", json={"text": "No shared voice key"})
            self.assertEqual(speech.status_code, 503, speech.text)
            for call in runtime.call_args_list:
                scoped_settings = call.args[0]
                self.assertEqual(scoped_settings.effective_standalone_reasoning_provider, "disabled")
                self.assertIsNone(scoped_settings.openai_api_key)
                self.assertIsNone(scoped_settings.gemini_api_key)
                self.assertIsNone(scoped_settings.fish_audio_api_key)
            openai.assert_not_called()
            gemini.assert_not_called()
            fish.assert_not_called()

    async def test_configured_account_reasoning_works_without_deployment_fallback(self):
        saved = await self.alpha_client.put("/v1/admin/provider-endpoints", json={"items": [{
            "id": "alpha-only", "name": "Alpha reasoning", "provider_name": "synthetic",
            "base_url": "https://synthetic.invalid/v1", "api_key": "synthetic-alpha-key", "model": "alpha-model",
        }]})
        self.assertEqual(saved.status_code, 200, saved.text)
        assignments = (await self.get_json(self.alpha_client, "/v1/admin/task-model-assignments"))["items"]
        for item in assignments:
            if item["task"] in {"reasoning", "memory_recall"}:
                item.update(provider="alpha-only", model="alpha-model")
        saved = await self.alpha_client.put("/v1/admin/task-model-assignments", json={"items": assignments})
        self.assertEqual(saved.status_code, 200, saved.text)
        scopes = []
        async def complete(dispatcher, task, messages, **kwargs):
            scopes.append((dispatcher.assignments.records.mind_id, task))
            if task == "memory_recall":
                action = {"action": "finish", "reason": "No stable learning from this synthetic request."}
                if kwargs.get("steward_action_phase") == "recall":
                    action["outcome"] = "no_recall_needed"
                return json.dumps(action)
            self.assertEqual(task, "reasoning")
            return "Synthetic account reasoning result"
        local = self.settings.model_copy(update={"body_allow_standalone_fallback": False})
        with patch("aicognitive_mind.api.get_settings", return_value=local), patch(
            "aicognitive_mind.config.get_settings", return_value=local,
        ), patch("aicognitive_mind.task_dispatcher.TaskModelDispatcher._complete_chat_with_assignment", new=complete):
            response = await self.alpha_client.post("/v1/mind/body/interact", json={"message": "Use my configured task"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["response_text"], "Synthetic account reasoning result")
        self.assertTrue(scopes)
        self.assertEqual({scope for scope, _task in scopes}, {self.alpha.mind_id})
        self.assertEqual({task for _scope, task in scopes}, {"reasoning", "memory_recall"})
        self.assertEqual(await api.app.state.journal_store.read(), [])


if __name__ == "__main__":
    unittest.main()
