"""Exercise the existing signup/login HTTP routes with disposable local storage."""

import importlib
import tempfile
import unittest
from contextlib import AsyncExitStack
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx

from aicognitive_mind.accounts import AccountService
from aicognitive_mind.config import Settings
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.surreal_storage import SurrealMindStore


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                  dotenv_settings, file_secret_settings):
        return (init_settings,)


class PortalAccountTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.stack = AsyncExitStack()
        self.directory = tempfile.TemporaryDirectory(
            prefix="axiom_portal_signup_", ignore_cleanup_errors=True
        )
        self.assertTrue(Path(self.directory.name).resolve().is_relative_to(
            Path(tempfile.gettempdir()).resolve()
        ))
        self.base = "https://portal-test.example"
        self.settings = LocalSettings(
            _env_file=None,
            storage_provider="surreal",
            surrealdb_uri="surrealkv://" + (Path(self.directory.name) / "store").as_posix(),
            surrealdb_namespace="local_signup",
            surrealdb_database="portal",
            surrealdb_username=None,
            surrealdb_password=None,
            axiom_mind_id="portal_registry",
            app_access_password="synthetic-portal-admin",
        )
        self.stack.enter_context(patch.dict("os.environ", {
            "AXIOM_PUBLIC_URL": self.base, "RENDER": "false",
        }))
        self.stack.enter_context(patch("aicognitive_mind.config.get_settings", return_value=self.settings))
        self.stack.enter_context(patch("aicognitive_mind.api.get_settings", return_value=self.settings))
        self.deployment = importlib.reload(importlib.import_module("aicognitive_mind.deployment"))
        self.storage = await create_storage(self.settings)
        self.records = RuntimeRecords(self.storage.mind)
        self.accounts = AccountService(self.settings, self.records)
        self.stack.enter_context(patch.object(self.deployment.oauth_provider, "accounts", self.accounts))
        self.stack.enter_context(patch.object(
            self.deployment.portal_app.state, "runtime_records", self.records, create=True
        ))
        # ASGITransport runs the real routes without starting MCP/Body lifespans.
        self.client = await self.stack.enter_async_context(httpx.AsyncClient(
            transport=httpx.ASGITransport(self.deployment.app), base_url=self.base
        ))

    async def asyncTearDown(self):
        await self.stack.aclose()
        await self.storage.runtime.close()
        self.directory.cleanup()

    async def signup(self, username="portal-alpha", password="synthetic-password-alpha"):
        return await self.client.post("/v1/portal/signup", json={
            "username": username, "password": password,
        })

    async def login(self, username="portal-alpha", password="synthetic-password-alpha"):
        return await self.client.post("/v1/portal/login", json={
            "username": username, "password": password,
        })

    async def test_existing_create_account_link_and_html_form_initialize_genesis(self):
        entry = await self.client.get("/")
        self.assertEqual(entry.status_code, 200)
        self.assertIn('href="/signup"', entry.text)
        self.assertIn("Create new account", entry.text)
        form = await self.client.get("/signup")
        self.assertIn('action="/signup"', form.text)
        created = await self.client.post("/signup", data={
            "username": "  Portal-User  ", "password": "synthetic-html-password",
        })
        self.assertEqual(created.status_code, 200)
        self.assertIn("Account created", created.text)
        account = await self.accounts.authenticate("portal-user", "synthetic-html-password")
        self.assertIsNotNone(account)
        mind = await SurrealMindStore(self.records.db, account.mind_id).load()
        self.assertEqual(mind.developmental_state, "genesis")
        self.assertIsNone(mind.identity.self_name)
        self.assertIsNone(await self.storage.mind.load())

    async def test_json_signup_login_and_duplicate_preserve_original_account(self):
        created = await self.signup()
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json(), {"ok": True, "username": "portal-alpha"})
        original = await self.accounts.authenticate("portal-alpha", "synthetic-password-alpha")
        duplicate = await self.signup(password="different-synthetic-password")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["detail"], "Account already exists")
        self.assertEqual(await self.accounts.authenticate(
            "portal-alpha", "synthetic-password-alpha"
        ), original)
        self.assertIsNone(await self.accounts.authenticate(
            "portal-alpha", "different-synthetic-password"
        ))
        logged_in = await self.login()
        self.assertEqual(logged_in.status_code, 200)
        self.assertEqual(logged_in.json(), {"ok": True})
        cookie = logged_in.headers["set-cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("Secure", cookie)
        session = await self.deployment.read_portal_session(
            self.deployment.portal_app, self.client.cookies["axiom_portal_session"]
        )
        self.assertEqual(session["mind_id"], original.mind_id)
        rejected = await self.login(password="incorrect-synthetic-password")
        self.assertEqual(rejected.status_code, 401)
        self.assertNotIn("set-cookie", rejected.headers)

    async def test_realtime_requires_server_configuration_and_live_account_before_minting(self):
        self.assertEqual((await self.signup()).status_code, 201)
        self.assertEqual((await self.login()).status_code, 200)
        mint = AsyncMock()
        with patch.object(self.deployment.oauth_provider, "mint_service_access_token", mint):
            denied = await self.client.post(
                "/v1/body/realtime/session", content="synthetic-sdp",
                headers={"content-type": "application/sdp"},
            )
            self.assertEqual(denied.status_code, 503, denied.text)
            with patch.object(self.accounts, "resolve_subject", return_value=None):
                unavailable = await self.client.post(
                    "/v1/body/realtime/session", content="synthetic-sdp",
                    headers={"content-type": "application/sdp"},
                )
                self.assertEqual(unavailable.status_code, 401, unavailable.text)
        mint.assert_not_awaited()

    async def test_two_accounts_and_sessions_remain_distinct_after_restart(self):
        self.assertEqual((await self.signup()).status_code, 201)
        self.assertEqual((await self.signup("portal-beta", "synthetic-password-beta")).status_code, 201)
        alpha = await self.accounts.authenticate("portal-alpha", "synthetic-password-alpha")
        beta = await self.accounts.authenticate("portal-beta", "synthetic-password-beta")
        self.assertNotEqual(alpha.mind_id, beta.mind_id)
        self.assertEqual((await self.login()).status_code, 200)
        alpha_cookie = self.client.cookies["axiom_portal_session"]
        self.assertEqual((await self.login("portal-beta", "synthetic-password-beta")).status_code, 200)
        beta_cookie = self.client.cookies["axiom_portal_session"]
        await self.storage.runtime.close()
        self.storage = await create_storage(self.settings)
        self.records = RuntimeRecords(self.storage.mind)
        self.accounts = AccountService(self.settings, self.records)
        self.deployment.oauth_provider.accounts = self.accounts
        self.deployment.portal_app.state.runtime_records = self.records
        for cookie, account, password in (
            (alpha_cookie, alpha, "synthetic-password-alpha"),
            (beta_cookie, beta, "synthetic-password-beta"),
        ):
            session = await self.deployment.read_portal_session(self.deployment.portal_app, cookie)
            self.assertEqual(session["mind_id"], account.mind_id)
            self.assertEqual(await self.accounts.authenticate(account.username, password), account)
            mind = await SurrealMindStore(self.records.db, account.mind_id).load()
            self.assertIsNotNone(mind)
            self.assertIsNone(mind.identity.self_name)


if __name__ == "__main__":
    unittest.main()
