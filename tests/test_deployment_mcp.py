import base64
import hashlib
import importlib
import json
import time
import unittest
from contextlib import AsyncExitStack, asynccontextmanager
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
from mcp.server.auth.provider import AccessToken
from mcp.shared.auth import OAuthClientInformationFull

from aicognitive_mind.config import Settings


def deployment_running(test):
    @wraps(test)
    async def run(self):
        async with self.deployment._combined_lifespan(self.deployment.app):
            await test(self)
    return run


class DeploymentMcpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.base = "https://axiom.example"
        self.stack = AsyncExitStack()
        self.settings = Settings(_env_file=None, app_access_password="test-password")
        self.stack.enter_context(patch.dict("os.environ", {"AXIOM_PUBLIC_URL": self.base}))
        self.stack.enter_context(
            patch("aicognitive_mind.config.get_settings", return_value=self.settings)
        )

        @asynccontextmanager
        async def test_lifespan(_server):
            yield SimpleNamespace(tenancy_probe={})

        self.stack.enter_context(patch("aicognitive_mind.chatgpt_mcp.lifespan", test_lifespan))
        deployment = importlib.import_module("aicognitive_mind.deployment")
        self.deployment = importlib.reload(deployment)
        self.provider = self.deployment.oauth_provider
        self.stack.enter_context(patch.object(self.provider, "start", AsyncMock()))
        self.stack.enter_context(patch.object(self.provider, "close", AsyncMock()))
        self.stack.enter_context(
            patch.object(self.deployment.portal_app.router, "lifespan_context", test_lifespan)
        )
        self.client = await self.stack.enter_async_context(
            httpx.AsyncClient(
                transport=httpx.ASGITransport(self.deployment.app), base_url=self.base
            )
        )
        self.oauth_client = OAuthClientInformationFull.model_validate(
            {
                "client_id": "deployment-test",
                "redirect_uris": ["https://client.example/callback"],
                "token_endpoint_auth_method": "none",
                "scope": "axiom:mind",
            }
        )
        await self.provider.register_client(self.oauth_client)

    async def asyncTearDown(self):
        await self.stack.aclose()

    def token(self, **updates):
        access = AccessToken(
            token="test-access",
            client_id=self.oauth_client.client_id,
            scopes=["axiom:mind"],
            expires_at=int(time.time()) + 3600,
            resource=self.provider.resource_url,
            subject="test-mind",
        ).model_copy(update=updates)
        self.provider.access_tokens[access.token] = access
        return access.token

    async def rpc(self, token, method="tools/list", params=None):
        return await self.client.post(
            self.deployment.MCP_PATH,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/json, text/event-stream",
                "MCP-Protocol-Version": "2025-03-26",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
        )

    @deployment_running
    async def test_transport_oauth_and_packaged_url_use_one_exact_endpoint(self):
        manifest = json.loads(Path("plugins/axiom-mind/mcp.json").read_text())
        self.assertEqual(self.deployment.MCP_PATH, "/axiom-mcp")
        self.assertEqual(self.provider.resource_url, self.base + "/axiom-mcp")
        self.assertEqual(
            urlparse(manifest["mcpServers"]["axiom"]["url"]).path,
            self.deployment.MCP_PATH,
        )
        response = await self.client.get(self.deployment.MCP_PATH)
        self.assertEqual(response.status_code, 401)
        metadata_path = "/.well-known/oauth-protected-resource/axiom-mcp"
        self.assertIn(self.base + metadata_path, response.headers["WWW-Authenticate"])
        metadata = await self.client.get(metadata_path)
        self.assertEqual(metadata.status_code, 200)
        self.assertEqual(metadata.json()["resource"], self.provider.resource_url)
        self.assertEqual(metadata.json()["scopes_supported"], ["axiom:mind"])

    @deployment_running
    async def test_initialize_and_tool_list_use_exact_endpoint_without_redirect(self):
        token = self.token()
        initialized = await self.rpc(token, "initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "regression-test", "version": "1"},
        })
        self.assertEqual(initialized.status_code, 200, initialized.text)
        self.assertNotIn("location", initialized.headers)
        self.assertEqual(initialized.json()["result"]["serverInfo"]["name"], "Axiom")
        listed = await self.rpc(token)
        self.assertEqual(listed.status_code, 200, listed.text)
        names = {item["name"] for item in listed.json()["result"]["tools"]}
        self.assertTrue({"begin_interaction", "complete_interaction"}.issubset(names))

    @deployment_running
    async def test_invalid_expired_and_wrong_resource_tokens_remain_rejected(self):
        for updates in (
            {"expires_at": int(time.time()) - 1},
            {"resource": None},
            {"resource": self.base + "/mcp"},
            {"resource": "https://other.example/axiom-mcp"},
        ):
            with self.subTest(updates=updates):
                response = await self.rpc(self.token(**updates))
                self.assertEqual(response.status_code, 401, response.text)
                self.assertEqual(response.json()["error"], "invalid_token")
        self.assertEqual((await self.rpc("unknown-token")).status_code, 401)

    @deployment_running
    async def test_valid_token_without_required_scope_is_forbidden(self):
        response = await self.rpc(self.token(scopes=[]))
        self.assertEqual(response.status_code, 403, response.text)
        self.assertEqual(response.json()["error"], "insufficient_scope")

    @deployment_running
    async def test_authorization_code_pkce_and_refresh_preserve_exact_resource(self):
        verifier = "v" * 64
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        response = await self.client.get("/authorize", params={
            "response_type": "code",
            "client_id": self.oauth_client.client_id,
            "redirect_uri": "https://client.example/callback",
            "code_challenge": challenge.decode().rstrip("="),
            "code_challenge_method": "S256",
            "scope": "axiom:mind",
            "state": "deployment-test",
            "resource": self.provider.resource_url,
        })
        self.assertEqual(response.status_code, 302, response.text)
        request_id = parse_qs(urlparse(response.headers["location"]).query)["request"][0]
        approved = await self.client.post("/oauth/login", data={
            "request": request_id,
            "username": self.settings.app_access_username,
            "password": "test-password",
            "decision": "approve",
        })
        self.assertEqual(approved.status_code, 302, approved.text)
        code = parse_qs(urlparse(approved.headers["location"]).query)["code"][0]
        token_response = await self.client.post("/token", data={
            "grant_type": "authorization_code",
            "client_id": self.oauth_client.client_id,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": "https://client.example/callback",
        })
        self.assertEqual(token_response.status_code, 200, token_response.text)
        tokens = token_response.json()
        self.assertEqual((await self.rpc(tokens["access_token"])).status_code, 200)
        refreshed = await self.client.post("/token", data={
            "grant_type": "refresh_token",
            "client_id": self.oauth_client.client_id,
            "refresh_token": tokens["refresh_token"],
        })
        self.assertEqual(refreshed.status_code, 200, refreshed.text)
        access = await self.provider.load_access_token(refreshed.json()["access_token"])
        self.assertEqual(access.resource, self.provider.resource_url)
        self.assertEqual(access.subject, self.settings.app_access_username)
        self.assertEqual((await self.rpc(refreshed.json()["access_token"])).status_code, 200)

    @deployment_running
    async def test_removed_endpoint_has_no_mcp_route_or_redirect(self):
        response = await self.client.post("/mcp", auth=httpx.BasicAuth(
            self.settings.app_access_username, "test-password"
        ))
        self.assertEqual(response.status_code, 404, response.text)
        self.assertNotIn("location", response.headers)
        self.assertNotIn("WWW-Authenticate", response.headers)


if __name__ == "__main__":
    unittest.main()
