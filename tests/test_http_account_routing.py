"""Authenticated HTTP cognition must use one account's existing Mind and stores."""

import base64
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

    async def test_unscoped_body_cognition_and_global_backup_fail_closed_for_accounts(self):
        with patch.object(api.app.state.browser_mouth, "consume", new_callable=AsyncMock) as consume, patch.object(
            api.app.state.mind_body, "interact", new_callable=AsyncMock,
        ) as interact:
            response = await self.alpha_client.get("/v1/body/mouth/next")
            self.assertEqual(response.status_code, 403)
            response = await self.alpha_client.post(
                "/v1/mind/body/interact", json={"message": "Do not route this to the root"},
            )
            self.assertEqual(response.status_code, 403)
            response = await self.alpha_client.get("/v1/admin/backup")
            self.assertEqual(response.status_code, 403)
            consume.assert_not_awaited()
            interact.assert_not_awaited()
        # Explicit deployment administration retains its existing Body access.
        response = await self.admin_client.get("/v1/body/mouth/next")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json())


if __name__ == "__main__":
    unittest.main()
