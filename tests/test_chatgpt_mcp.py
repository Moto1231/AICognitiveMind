import unittest
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from urllib.parse import parse_qs, urlparse

from pydantic import AnyUrl

from mcp.server.auth.provider import AccessToken, AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull

from aicognitive_mind.chatgpt_mcp import (
    HOST_INSTRUCTIONS,
    _summarize_body_work,
    build_chatgpt_mcp,
)
from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.host_runtime import RuntimeRecords


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
        self.provider._records = RuntimeRecords(SimpleNamespace(mind_id="synthetic-root"))
        session_key = "portal_session_synthetic"
        session = {"account_mind_id": "mind-realtime-test", "expires_at": time.time() + 120}
        await self.provider._records.create(session_key, session)
        token = await self.provider.mint_service_access_token(
            subject="mind-realtime-test",
            client_id="axiom-realtime",
            portal_session_key=session_key, expires_at=session["expires_at"],
        )
        access = await self.provider.load_access_token(token)

        self.assertIsNotNone(access)
        self.assertEqual(access.subject, "mind-realtime-test")
        self.assertEqual(access.resource, self.provider.resource_url)
        self.assertIn(self.provider.required_scope, access.scopes)
        self.assertLessEqual(access.expires_at, session["expires_at"])
        # A transport may retain an AccessToken object after HTTP authentication;
        # the per-tool guard must also see a revoked portal session immediately.
        self.assertTrue(await self.provider.access_token_session_active(access))
        self.assertFalse(await self.provider.access_token_session_active(
            access.model_copy(update={"expires_at": int(time.time()) - 1}),
        ))
        await self.provider._records.replace(session_key, session, {**session, "expires_at": 0})
        self.assertFalse(await self.provider.access_token_session_active(access))
        self.assertIsNone(await self.provider.load_access_token(token))
        self.provider.access_tokens.clear()
        self.assertIsNone(await self.provider.load_access_token(token))

    async def test_realtime_token_requires_matching_unexpired_portal_session(self):
        self.provider._records = RuntimeRecords(SimpleNamespace(mind_id="synthetic-root"))
        token = await self.provider.mint_service_access_token(subject="mind-realtime-test", client_id="axiom-realtime")
        self.assertIsNone(await self.provider.load_access_token(token))
        for index, (expiry, subject) in enumerate((
            (time.time() + 60, "other-mind"), (float("nan"), "mind-realtime-test"),
            (time.time() - 1, "mind-realtime-test"),
        )):
            session_key = "portal_session_synthetic_" + str(index)
            await self.provider._records.create(session_key, {"account_mind_id": subject, "expires_at": expiry})
            token = await self.provider.mint_service_access_token(
                subject="mind-realtime-test", client_id="axiom-realtime", portal_session_key=session_key,
            )
            self.assertIsNone(await self.provider.load_access_token(token))

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
        # Direct function fixtures still represent an authenticated request.
        # The independent routing regressions exercise missing/invalid tokens.
        access = AccessToken(
            token="synthetic-surface-access", client_id="surface-client",
            subject="mind", scopes=[self.provider.required_scope],
            resource=self.provider.resource_url,
        )
        token_patch = patch("aicognitive_mind.account_mcp.get_access_token", return_value=access)
        token_patch.start()
        self.addCleanup(token_patch.stop)

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
        self.assertIn("Prioritize the current direct human input", HOST_INSTRUCTIONS)
        self.assertIn("preserve its begin/complete lifecycle", HOST_INSTRUCTIONS)
        self.assertIn("parallel perception worker under the existing private lease", HOST_INSTRUCTIONS)
        self.assertIn("passive work need not wait for an unrelated task or journal commit", HOST_INSTRUCTIONS)
        self.assertIn("bounded batch of at most four", HOST_INSTRUCTIONS)
        self.assertIn("registered receiver signals remaining/new work", HOST_INSTRUCTIONS)
        self.assertNotIn("A later begin_interaction will service more queued", HOST_INSTRUCTIONS)
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
        self.assertIn("The Breaker", HOST_INSTRUCTIONS)
        self.assertIn("presentation.report_persistence_error", HOST_INSTRUCTIONS)
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

    async def test_realtime_status_reports_server_configuration_without_credentials(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        status = server._tool_manager.get_tool("get_body_reasoning_status").fn
        ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=SimpleNamespace(
            storage=SimpleNamespace(mind=object()), mind_service=object(),
        )))
        for key in ("", "synthetic-private-server-key"):
            configured = SimpleNamespace(
                effective_standalone_reasoning_provider="none", openai_api_key=key,
                openai_realtime_model="configured-realtime-model",
            )
            with patch("aicognitive_mind.chatgpt_mcp.get_settings", return_value=configured), patch(
                "aicognitive_mind.chatgpt_mcp.HostRuntime",
            ) as hosts:
                hosts.return_value.active = AsyncMock(return_value=None)
                hosts.return_value.records.mind_id = "synthetic-account-mind"
                hosts.return_value.records.get = AsyncMock(return_value=None)
                result = await status(ctx=ctx)
            self.assertEqual(result["realtime"], {
                "configured": bool(key), "model": "configured-realtime-model",
            })
            self.assertNotIn("synthetic-private-server-key", str(result))
            self.assertEqual(result["wakeup"], {
                "mind_id": "synthetic-account-mind",
                "ready_url": self.base + "/v1/host-events/ready",
                "authentication": "existing-private-host-lease",
            })
            self.assertNotIn("lease_token", str(result))
            self.assertIsNone(result["active_body"])

    async def test_reasoning_status_exposes_only_fresh_client_reported_body_state(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        status = server._tool_manager.get_tool("get_body_reasoning_status").fn
        mind = object()
        ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=SimpleNamespace(
            storage=SimpleNamespace(mind=mind), mind_service=object(),
        )))
        configured = SimpleNamespace(
            effective_standalone_reasoning_provider="none", openai_api_key="private-server-key",
            openai_realtime_model="configured-realtime-model",
        )
        client_state = {
            "client_revision": "synthetic-client", "hearing": True, "voice": False,
            "microphone_live": True, "voice_mode": "connected_host", "last_playback": "failed",
        }
        with patch("aicognitive_mind.chatgpt_mcp.get_settings", return_value=configured), patch(
            "aicognitive_mind.chatgpt_mcp.HostRuntime",
        ) as hosts:
            hosts.return_value.active = AsyncMock(return_value=None)
            hosts.return_value.records.mind_id = "synthetic-current-mind"
            hosts.return_value.records.get = AsyncMock(return_value={
                "session_id": "private-session-identifier", "updated_at": time.time(),
                "client_state": client_state,
            })
            result = await status(ctx=ctx)
            self.assertEqual(result["active_body"]["client_state"], client_state)
            self.assertTrue(result["active_body"]["fresh"])
            self.assertEqual(result["active_body"]["client_state_source"], "client_reported")
            self.assertNotIn("private-session-identifier", str(result))
            self.assertNotIn("private-server-key", str(result))
            self.assertIs(hosts.call_args.args[0], mind)
            hosts.return_value.records.get.return_value["updated_at"] = time.time() - 121
            stale = await status(ctx=ctx)
            self.assertFalse(stale["active_body"]["fresh"])
            self.assertIsNone(stale["active_body"]["client_state"])
            self.assertNotIn("token_hash", str(result))

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
        self.assertNotIn("proposed_memories", completion_schema["required"])

    async def test_deployed_complete_reviews_without_host_memory_suggestions(self):
        server = build_chatgpt_mcp(self.base, self.provider)
        service = SimpleNamespace(complete_interaction=AsyncMock(return_value={
            "status": "interaction_committed", "memory_decisions": [],
        }))
        record = AsyncMock()
        storage = SimpleNamespace(diagnostics=SimpleNamespace(record=record))
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(mind_service=service, storage=storage)
        ))
        working = HostWorkingContext(summary="Steward owns memory decisions")
        complete = server._tool_manager.get_tool("complete_interaction").fn

        result = await complete(
            user_message="Remember the result.", response_text="The result is recorded.",
            host_working_context=working, idempotency_key="steward-turn", ctx=ctx,
        )

        service.complete_interaction.assert_awaited_once_with(
            user_message="Remember the result.", response_text="The result is recorded.",
            proposed_memories=(), current_evidence=(), idempotency_key="steward-turn",
            host_working_context=working.model_dump(mode="json"),
        )
        self.assertEqual(result["status"], "interaction_committed")
        self.assertEqual(result["host_working_context"], working.model_dump(mode="json"))
        request = record.await_args_list[0].args[0].implementation
        self.assertEqual(request["phase"], "complete_request")
        self.assertEqual(request["payload"]["proposed_memories"], [])
        self.assertEqual(request["payload"]["current_evidence"], [])

    async def test_administrative_completion_accepts_omitted_memory_suggestions(self):
        from aicognitive_mind.mcp_server import mcp

        tools = {tool.name: tool for tool in await mcp.list_tools()}
        for name in ("complete_interaction", "complete_body_interaction"):
            self.assertNotIn("proposed_memories", tools[name].input_schema["required"])
        complete = mcp._tool_manager.get_tool("complete_interaction").fn
        service = SimpleNamespace(complete_interaction=AsyncMock(return_value={
            "status": "interaction_committed", "memory_decisions": [],
        }))
        hosts = SimpleNamespace(complete=AsyncMock(return_value={"status": "complete"}))
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(mind_service=service, hosts=hosts)
        ))
        working = HostWorkingContext(summary="Independent Steward review")

        await complete(
            user_message="Continue.", response_text="Continuing.",
            host_working_context=working, idempotency_key="admin-turn", ctx=ctx,
        )
        self.assertEqual(service.complete_interaction.await_args.kwargs["proposed_memories"], ())
        self.assertEqual(
            service.complete_interaction.await_args.kwargs["idempotency_key"], "admin-turn"
        )
        complete_body = mcp._tool_manager.get_tool("complete_body_interaction").fn
        await complete_body(
            lease_token="test-lease", request_id="test-request", response_text="Ready.", ctx=ctx,
        )
        hosts.complete.assert_awaited_once_with("test-lease", "test-request", "Ready.", ())

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
                "fail_body_interaction",
                "fail_incoming_sensory",
            }.issubset(names)
        )
        self.assertIn("speak_body_text", names)
        self.assertIn("speak_body_text", HOST_INSTRUCTIONS)


if __name__ == "__main__":
    unittest.main()
