import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from aicognitive_mind.chatgpt_mcp import (
    HOST_INSTRUCTIONS,
    _live_body_status,
    _summarize_body_work,
    build_chatgpt_mcp,
)
from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.body_sessions import BodyQueue, body_session
from aicognitive_mind.body import BrowserVoiceOutput


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
    async def asyncSetUp(self):
        self.base = "https://axiom.example"
        self.provider = AxiomAuthorizationServerProvider(
            self.base, username="mind", password="secret",
        )

    def test_live_body_readiness_distinguishes_missing_invalid_and_stale_sessions(self):
        self.assertEqual(_live_body_status(None)["status"], "missing")
        for registration in ({"session_id": "private"},
                             {"session_id": None, "updated_at": 1000},
                             {"session_id": "private", "updated_at": float("nan")}):
            self.assertEqual(_live_body_status(registration)["status"], "invalid")
        with patch("aicognitive_mind.chatgpt_mcp.time.time", return_value=1000):
            for updated_at, expected in ((880, "active"), (879, "stale")):
                result = _live_body_status({"session_id": "private", "updated_at": updated_at})
                self.assertEqual(result["status"], expected)
                self.assertEqual(result["speech_available"], expected == "active")
                self.assertNotIn("private", str(result))

    async def test_speech_reports_recoverable_error_without_queueing_to_stale_body(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        mind = SimpleNamespace(mind_id="speech-test")
        records = RuntimeRecords(mind)
        await records.create("active_body_session", {"session_id": "private", "updated_at": 1})
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(storage=SimpleNamespace(mind=mind))
        ))
        result = await server._tool_manager.get_tool("speak_body_text").fn(text="Test", ctx=ctx)
        self.assertTrue(result.is_error)
        self.assertTrue(result.model_dump(by_alias=True)["isError"])
        self.assertEqual(result.structured_content["status"], "stale")
        self.assertIn("foreground", result.content[0].text)
        self.assertEqual(set(mind._runtime_records), {"active_body_session"})

    async def test_speech_queues_only_to_registered_body_and_preserves_caller_session(self):
        import time

        server = build_chatgpt_mcp(self.base, self.provider)
        mind = SimpleNamespace(mind_id="speech-test")
        records = RuntimeRecords(mind)
        await records.create("active_body_session", {
            "session_id": "phone", "updated_at": time.time(),
        })
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(storage=SimpleNamespace(mind=mind))
        ))
        caller = body_session.set("caller")
        try:
            result = await server._tool_manager.get_tool("speak_body_text").fn(text="Test", ctx=ctx)
            self.assertFalse(result.is_error)
            self.assertEqual(result.structured_content["status"], "queued")
            self.assertFalse(result.structured_content["playback_confirmed"])
            self.assertEqual(body_session.get(), "caller")
            queue = BodyQueue(records, "mouth", BrowserVoiceOutput())
            self.assertEqual(await queue.deliver(), (None, None))
            phone = body_session.set("phone")
            try:
                intent, receipt = await queue.deliver()
                self.assertEqual(intent.text, "Test")
                self.assertTrue(receipt)
            finally:
                body_session.reset(phone)
        finally:
            body_session.reset(caller)

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
        self.assertIn("A later begin_interaction will service more queued", HOST_INSTRUCTIONS)
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
        self.assertIn("synthesize_voice", schema["properties"]["operation"]["enum"])
        self.assertIn("text", schema["properties"])
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

    async def test_deployed_surface_registers_current_state_tools(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        tools = {tool.name: tool for tool in await server.list_tools()}
        self.assertIn("read_current_state", tools)
        update = tools["update_current_state"]
        self.assertIn("event", update.input_schema["required"])
        self.assertIn("scene_changed", update.input_schema["properties"]["event"]["enum"])
        self.assertTrue(tools["read_current_state"].annotations.read_only_hint)
        self.assertFalse(update.annotations.read_only_hint)
        self.assertFalse(tools["begin_interaction"].annotations.read_only_hint)

    async def test_deployed_begin_passes_validated_context_to_state_ledger(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        service = SimpleNamespace(begin_interaction=AsyncMock(return_value={
            "status": "ready_to_reason", "idempotency_key": "context-turn",
        }))
        storage = SimpleNamespace(mind=object(), diagnostics=SimpleNamespace(record=AsyncMock()))
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(mind_service=service, storage=storage)
        ))
        working = HostWorkingContext(summary="Restore ledger", unresolved_references=("Validate",))
        hosts = SimpleNamespace(
            records=SimpleNamespace(pending=AsyncMock(return_value=[])),
            active=AsyncMock(return_value=None),
        )
        with patch("aicognitive_mind.chatgpt_mcp.HostRuntime", return_value=hosts):
            result = await server._tool_manager.get_tool("begin_interaction").fn(
                user_message="Continue.", ctx=ctx, host_working_context=working,
            )
        service.begin_interaction.assert_awaited_once_with(
            "Continue.", working.model_dump(mode="json")
        )
        self.assertEqual(result["host_working_context"], working.model_dump(mode="json"))

    async def test_deployed_state_tools_delegate_events_and_reads(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        expected = {"revision": 4, "fields": {"locality": {"value": "Lab A"}}}
        service = SimpleNamespace(
            read_current_state=AsyncMock(return_value=expected),
            update_current_state=AsyncMock(return_value=expected),
        )
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(mind_service=service)
        ))
        read = server._tool_manager.get_tool("read_current_state").fn
        update = server._tool_manager.get_tool("update_current_state").fn
        self.assertEqual(await read(ctx=ctx), expected)
        values = {"values": {"locality": "Lab A"}}
        self.assertEqual(await update(
            event="location_changed", ctx=ctx, updates=values, source="direct user statement",
        ), expected)
        service.update_current_state.assert_awaited_once_with(
            event="location_changed", updates=values, source="direct user statement",
        )

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
