import unittest
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from aicognitive_mind.chatgpt_mcp import (
    HOST_INSTRUCTIONS,
    _summarize_body_work,
    build_chatgpt_mcp,
)
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

        self.assertTrue(await self.provider.authenticate("mind", "secret"))
        self.assertFalse(await self.provider.authenticate("mind", "wrong"))

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

    async def test_trusted_realtime_token_is_scoped_to_mind(self):
        token = await self.provider.mint_service_access_token(
            subject="mind-realtime-test",
            client_id="axiom-realtime",
        )
        access = await self.provider.load_access_token(token)

        self.assertIsNotNone(access)
        self.assertEqual(access.subject, "mind-realtime-test")
        self.assertEqual(access.resource, self.provider.resource_url)
        self.assertIn(self.provider.required_scope, access.scopes)

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
    def test_begin_interaction_surfaces_queue_and_preserves_human_priority(self):
        summary = _summarize_body_work(
            [
                {"priority": 10, "message": "Interpret this vision percept."},
                {"priority": 0, "message": "Please tell me what happened."},
                {"message": "Interpret this audio percept."},
                {"claim": "host-token-hash", "claim_until": None, "priority": 10,
                 "message": "Interpret this already-claimed percept."},
            ]
        )
        self.assertEqual(summary["pending_requests"], 3)
        self.assertEqual(summary["in_progress_requests"], 1)
        self.assertEqual(summary["pending_human_messages"], 1)
        self.assertEqual(summary["pending_sensory_interpretations"], 2)
        self.assertEqual(summary["pending_other_requests"], 0)
        self.assertIn("body_work snapshot", HOST_INSTRUCTIONS)
        self.assertIn("commit the current direct", HOST_INSTRUCTIONS)
        self.assertIn("human response with complete_interaction", HOST_INSTRUCTIONS)
        self.assertIn("claim at most one queued", HOST_INSTRUCTIONS)
        self.assertIn("Do not mark work complete", HOST_INSTRUCTIONS)
        self.assertIn("Never self-dispatch a sensory prompt", HOST_INSTRUCTIONS)

    def test_server_identifies_host_boundary(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        self.assertEqual(server.name, "Axiom")
        self.assertIn("current reasoning faculty", HOST_INSTRUCTIONS)
        self.assertIn("begin_interaction", HOST_INSTRUCTIONS)
        self.assertIn("complete_interaction", HOST_INSTRUCTIONS)
        self.assertIn("open_live_body", HOST_INSTRUCTIONS)
        self.assertIn("Every begin_interaction result includes a body_work snapshot", HOST_INSTRUCTIONS)
        self.assertIn("queue server selects human text requests ahead", HOST_INSTRUCTIONS)

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

    async def test_deployed_surface_registers_execute_task(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        tools = {tool.name: tool for tool in await server.list_tools()}
        self.assertIn("execute_task", tools)
        schema = tools["execute_task"].input_schema
        self.assertIn("task", schema["properties"])
        self.assertIn("operation", schema["properties"])
        self.assertIn("messages", schema["properties"])
        self.assertIn("audio_base64", schema["properties"])
        self.assertIn("speak_body_text", tools)
        self.assertIn("text", tools["speak_body_text"].input_schema["properties"])
        self.assertIn("task", schema["required"])
        self.assertIn("operation", schema["required"])

    async def test_deployed_surface_registers_external_mcp_tools(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        tools = {tool.name: tool for tool in await server.list_tools()}
        self.assertIn("list_mcp_tools", tools)
        self.assertIn("call_mcp_tool", tools)
        self.assertIn("server_id", tools["call_mcp_tool"].input_schema["properties"])
        self.assertIn("tool_name", tools["call_mcp_tool"].input_schema["properties"])
        self.assertIn("arguments", tools["call_mcp_tool"].input_schema["properties"])

    async def test_deployed_surface_registers_interaction_trace_tool(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        names = {tool.name for tool in await server.list_tools()}
        self.assertIn("interaction_trace", names)
        self.assertIn("open_live_body", names)

    async def test_deployed_surface_registers_camera_tool(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        names = {tool.name for tool in await server.list_tools()}
        self.assertIn("request_camera_observation", names)

    async def test_turn_tools_require_structured_host_working_context(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        tools = {tool.name: tool for tool in await server.list_tools()}

        for name in ("begin_interaction", "complete_interaction"):
            schema = tools[name].input_schema
            self.assertIn("host_working_context", schema["properties"])
            if name == "complete_interaction":
                self.assertIn("host_working_context", schema["required"])
            else:
                self.assertNotIn("host_working_context", schema["required"])
        completion_schema = tools["complete_interaction"].input_schema
        self.assertIn("idempotency_key", completion_schema["required"])
        self.assertIn("proposed_memories", completion_schema["required"])

    async def test_deployed_surface_registers_body_host_handoff_tools(self):
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example",
            username="mind",
            password="secret",
        )
        server = build_chatgpt_mcp("https://axiom.example", provider)
        names = {tool.name for tool in await server.list_tools()}

        self.assertTrue(
            {
                "attach_reasoning_host",
                "renew_reasoning_host",
                "next_body_interaction",
                "complete_body_interaction",
            }.issubset(names)
        )
        self.assertIn("speak_body_text", names)
        self.assertIn("speak_body_text", HOST_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
