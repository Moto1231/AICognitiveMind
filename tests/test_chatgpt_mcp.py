import unittest
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from aicognitive_mind.chatgpt_mcp import HOST_INSTRUCTIONS, build_chatgpt_mcp
from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider


class ChatGptOAuthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.base = "https://axiom.example"
        self.provider = AxiomAuthorizationServerProvider(
            self.base,
            username="mind",
            password="secret",
            resource_path="/axiom-mcp",
        )
        self.client = OAuthClientInformationFull.model_validate(
            {
                "client_id": "chatgpt-test",
                "redirect_uris": ["https://chatgpt.example/callback"],
            }
        )
        await self.provider.register_client(self.client)

    async def test_authorization_code_and_refresh_flow(self):
        params = AuthorizationParams(
            state="state-1",
            scopes=["axiom:mind"],
            code_challenge="challenge",
            redirect_uri=AnyUrl("https://chatgpt.example/callback"),
            redirect_uri_provided_explicitly=True,
            resource=self.base + "/axiom-mcp",
        )
        login_url = await self.provider.authorize(self.client, params)
        request_id = parse_qs(urlparse(login_url).query)["request"][0]

        self.assertTrue(self.provider.authenticate("mind", "secret"))
        self.assertFalse(self.provider.authenticate("mind", "wrong"))

        callback = await self.provider.approve(request_id)
        callback_params = parse_qs(urlparse(callback).query)
        self.assertEqual(callback_params["state"], ["state-1"])
        code_value = callback_params["code"][0]

        code = await self.provider.load_authorization_code(self.client, code_value)
        self.assertIsNotNone(code)
        token = await self.provider.exchange_authorization_code(self.client, code)
        self.assertTrue(token.access_token)
        self.assertTrue(token.refresh_token)

        access = await self.provider.load_access_token(token.access_token)
        self.assertIsNotNone(access)
        self.assertEqual(access.resource, self.base + "/axiom-mcp")
        self.assertEqual(access.subject, "mind")

        refresh = await self.provider.load_refresh_token(
            self.client,
            token.refresh_token,
        )
        self.assertIsNotNone(refresh)
        rotated = await self.provider.exchange_refresh_token(
            self.client,
            refresh,
            ["axiom:mind"],
        )
        self.assertNotEqual(rotated.access_token, token.access_token)
        self.assertNotEqual(rotated.refresh_token, token.refresh_token)
        self.assertIsNone(
            await self.provider.load_refresh_token(self.client, token.refresh_token)
        )

    async def test_denial_returns_to_registered_callback(self):
        params = AuthorizationParams(
            state="deny-state",
            scopes=["axiom:mind"],
            code_challenge="challenge",
            redirect_uri=AnyUrl("https://chatgpt.example/callback"),
            redirect_uri_provided_explicitly=True,
            resource=self.base + "/axiom-mcp",
        )
        login_url = await self.provider.authorize(self.client, params)
        request_id = parse_qs(urlparse(login_url).query)["request"][0]
        callback = await self.provider.deny(request_id)
        values = parse_qs(urlparse(callback).query)
        self.assertEqual(values["error"], ["access_denied"])
        self.assertEqual(values["state"], ["deny-state"])


class ChatGptMcpSurfaceTests(unittest.IsolatedAsyncioTestCase):
    def test_server_identifies_host_boundary(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        self.assertEqual(server.name, "Axiom")
        self.assertIn("replaceable reasoning host", HOST_INSTRUCTIONS)
        self.assertIn("begin_interaction", HOST_INSTRUCTIONS)
        self.assertIn("complete_interaction", HOST_INSTRUCTIONS)

    async def test_deployed_surface_registers_github_tools(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        names = {tool.name for tool in await server.list_tools()}

        self.assertTrue(
            {
                "github_status",
                "github_list_path",
                "github_read_file",
                "github_create_branch",
                "github_create_pull_request",
                "github_write_file",
            }.issubset(names)
        )


if __name__ == "__main__":
    unittest.main()
