"""Authenticated HTTP cognition must use one account's existing Mind and stores."""

import base64
import json
from contextlib import AsyncExitStack
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from aicognitive_mind import api
from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.config import Settings
from aicognitive_mind.domain import DiagnosticObservation, ReasoningProposal
from aicognitive_mind.core_skills import REQUIRED_SKILLS, load_required_skill
from aicognitive_mind.host_runtime import RuntimeRecords
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
