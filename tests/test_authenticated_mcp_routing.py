"""Account-authenticated MCP lifecycle checks; isolated synthetic Surreal data only."""

import asyncio
import base64
import hashlib
import time
from contextvars import ContextVar
from functools import wraps
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse
import unittest
from unittest.mock import AsyncMock, patch

from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull
from mcp.shared.exceptions import MCPError
from pydantic import AnyUrl

from aicognitive_mind import account_mcp, mcp_events
from aicognitive_mind.accounts import AccountService
from aicognitive_mind.chatgpt_mcp import build_chatgpt_mcp
from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
from aicognitive_mind.config import Settings
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.host_runtime import HostRuntime, RuntimeRecords
from aicognitive_mind.mcp_server import AppState
from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.persistence import create_storage, scope_storage
from aicognitive_mind.provider_endpoints import ProviderEndpoint, ProviderEndpointRegistry
from aicognitive_mind.task_dispatcher import TaskModelDispatcher
from aicognitive_mind.task_model_assignments import TaskModelAssignment, TaskModelAssignmentRegistry


PASSWORD = "synthetic-mcp-routing-password"


def account_key(username):
    return "account_" + hashlib.sha256(username.strip().lower().encode()).hexdigest()


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                  dotenv_settings, file_secret_settings):
        return (init_settings,)


class AuthenticatedMcpRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settings = LocalSettings(
            _env_file=None, storage_provider="surreal", surrealdb_uri="mem://",
            surrealdb_namespace="routing", surrealdb_database="synthetic",
            axiom_mind_id="axiom",
        )
        self.storage = await create_storage(self.settings)
        self.records = RuntimeRecords(self.storage.mind)
        self.accounts = AccountService(self.settings, self.records)
        self.alpha = await self.accounts.create("alpha-routing", PASSWORD)
        self.beta = await self.accounts.create("beta-routing", PASSWORD)
        self.base = "https://routing.example"
        self.provider = AxiomAuthorizationServerProvider(
            self.base, username="legacy-admin", password="synthetic-admin-password",
            resource_path="/axiom-mcp",
        )
        self.provider._records = self.records
        self.provider.accounts = self.accounts
        self.oauth_client = OAuthClientInformationFull.model_validate({
            "client_id": "synthetic-routing-client",
            "redirect_uris": ["https://chatgpt.example/callback"],
        })
        await self.provider.register_client(self.oauth_client)
        self.tokens = {
            account.mind_id: await self.mint_account_token(account)
            for account in (self.alpha, self.beta)
        }

        # Production has no provider assignment in these fresh stores. Inject
        # the existing deterministic Steward only for isolated lifecycle tests.
        original_init = CognitiveMcpService.__init__

        @wraps(original_init)
        def deterministic_init(service, *args, **kwargs):
            kwargs["steward_factory"] = MemoryStewardTool
            original_init(service, *args, **kwargs)

        self.steward_patch = patch.object(CognitiveMcpService, "__init__", deterministic_init)
        self.steward_patch.start()
        self.addCleanup(self.steward_patch.stop)
        service = CognitiveMcpService(
            mind=self.storage.mind, journal=self.storage.journal, memory=self.storage.memory,
        )
        self.root_state = AppState(
            runtime=self.storage.runtime, storage=self.storage, mind_service=service,
            hosts=HostRuntime(self.storage.mind, service),
            task_dispatcher=TaskModelDispatcher(self.records),
            tenancy_probe={
                "status": "synthetic", "provider": "surreal",
                "primary_mind_id": "private-root-selector", "primary_initialized": False,
                "probe_mind_id": "private-probe-selector", "probe_initialized": True,
            },
        )
        self.ctx = SimpleNamespace(request_context=SimpleNamespace(lifespan_context=self.root_state))
        settings_patch = patch("aicognitive_mind.config.get_settings", return_value=self.settings)
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        self.server = build_chatgpt_mcp(self.base, self.provider)
        self.current_access = ContextVar("synthetic_mcp_access", default=None)
        token_patch = patch.object(account_mcp, "get_access_token", side_effect=self.current_access.get)
        token_patch.start()
        self.addCleanup(token_patch.stop)
        event_token_patch = patch.object(mcp_events, "get_access_token", side_effect=self.current_access.get)
        event_token_patch.start()
        self.addCleanup(event_token_patch.stop)

    async def asyncTearDown(self):
        await self.storage.runtime.close()

    async def mint_account_token(self, account):
        subject = await self.provider.authenticate(account.username, PASSWORD)
        self.assertEqual(subject, account.mind_id)
        params = AuthorizationParams(
            state="synthetic-state", scopes=[self.provider.required_scope],
            code_challenge="synthetic-challenge",
            redirect_uri=AnyUrl("https://chatgpt.example/callback"),
            redirect_uri_provided_explicitly=True, resource=self.provider.resource_url,
        )
        login = await self.provider.authorize(self.oauth_client, params)
        request_id = parse_qs(urlparse(login).query)["request"][0]
        callback = await self.provider.approve(request_id, subject=subject)
        code_value = parse_qs(urlparse(callback).query)["code"][0]
        code = await self.provider.load_authorization_code(self.oauth_client, code_value)
        issued = await self.provider.exchange_authorization_code(self.oauth_client, code)
        access = await self.provider.load_access_token(issued.access_token)
        self.assertEqual(access.subject, account.mind_id)
        return access

    async def invoke(self, name, account=None, *, access=None, **arguments):
        if access is None and account is not None:
            access = self.tokens[account.mind_id]
        handle = self.current_access.set(access)
        try:
            return await self.server._tool_manager.get_tool(name).fn(ctx=self.ctx, **arguments)
        finally:
            self.current_access.reset(handle)

    async def complete(self, account, key, marker):
        return await self.invoke(
            "complete_interaction", account, user_message=f"Remember synthetic project {marker}.",
            response_text=f"Synthetic project {marker} is recorded.",
            host_working_context=HostWorkingContext(summary=f"Project {marker}"),
            idempotency_key=key,
            proposed_memories=[MemoryProposal(
                memory_class="semantic", content=f"Synthetic project {marker} uses a ledger.",
                associations=(marker,), grounding=(f"Direct synthetic project statement {marker}",),
            )],
        )

    async def test_status_begin_complete_use_existing_account_minds_with_empty_root(self):
        for account, marker in ((self.alpha, "Alpha"), (self.beta, "Beta")):
            expected = await scope_storage(self.storage, account.mind_id).mind.load()
            status = await self.invoke("mind_status", account)
            self.assertEqual(status["mind"], expected.model_dump(mode="json"))
            self.assertEqual(status["journal_experience_count"], 0)
            self.assertEqual(status["active_storage"]["mind_id"], account.mind_id)
            self.assertEqual(status["storage_tenancy"], {
                "status": "synthetic", "provider": "surreal",
                "verification_scope": "deployment_startup",
            })
            begun = await self.invoke(
                "begin_interaction", account, user_message=f"Continue project {marker}.",
                host_working_context=HostWorkingContext(summary=marker),
            )
            self.assertEqual(begun["status"], "ready_to_reason")
            self.assertEqual(begun["mind"], status["mind"])
            completed = await self.complete(account, begun["idempotency_key"], marker)
            self.assertEqual(completed["status"], "interaction_committed")
            after = await self.invoke("mind_status", account)
            self.assertEqual(after["durable_memory_count"], 1)
            self.assertEqual(after["journal_experience_count"], 1)
        self.assertIsNone(await self.storage.mind.load())
        self.assertEqual(await self.storage.memory.read(), [])
        self.assertEqual(await self.storage.journal.read(), [])
        self.assertIs(self.ctx.request_context.lifespan_context, self.root_state)

    async def test_receipts_and_trace_are_isolated_for_same_completion_key(self):
        first = await self.complete(self.alpha, "same-turn", "Alpha")
        retried = await self.complete(self.alpha, "same-turn", "Alpha")
        second = await self.complete(self.beta, "same-turn", "Beta")
        self.assertEqual(retried, first)
        self.assertEqual(second["status"], "interaction_committed")
        for account, marker, other in (
            (self.alpha, "Alpha", "Beta"), (self.beta, "Beta", "Alpha"),
        ):
            tenant = scope_storage(self.storage, account.mind_id)
            self.assertEqual((await self.invoke("mind_status", account))["journal_experience_count"], 1)
            content = " ".join(item.content for item in await tenant.memory.read())
            self.assertIn(marker, content)
            self.assertNotIn(other, content)
            trace = await self.invoke("interaction_trace", account, interaction_id="same-turn")
            self.assertEqual(trace["status"], "complete")
            self.assertIn(marker, str(trace))
            self.assertNotIn(other, str(trace))
        untouched = await self.invoke("interaction_trace", self.beta, interaction_id="only-alpha")
        self.assertEqual(untouched["event_count"], 0)

    async def test_current_state_and_trace_cannot_cross_account_boundary(self):
        await self.invoke(
            "update_current_state", self.alpha, event="location_changed",
            updates={"values": {"locality": "Synthetic Alpha Lab"}}, source="synthetic test",
        )
        alpha = await self.invoke("read_current_state", self.alpha)
        beta = await self.invoke("read_current_state", self.beta)
        self.assertEqual(alpha["fields"]["locality"]["value"], "Synthetic Alpha Lab")
        self.assertNotEqual(beta["fields"]["locality"]["value"], "Synthetic Alpha Lab")
        await self.complete(self.alpha, "only-alpha", "Alpha")
        self.assertGreater((await self.invoke(
            "interaction_trace", self.alpha, interaction_id="only-alpha"
        ))["event_count"], 0)
        self.assertEqual((await self.invoke(
            "interaction_trace", self.beta, interaction_id="only-alpha"
        ))["event_count"], 0)

    async def test_missing_invalid_scope_resource_or_subject_fails_closed(self):
        original = self.tokens[self.alpha.mind_id]
        invalid = (
            None,
            original.model_copy(update={"subject": None}),
            original.model_copy(update={"subject": ""}),
            original.model_copy(update={"subject": "mind_" + "f" * 32}),
            original.model_copy(update={"scopes": []}),
            original.model_copy(update={"resource": "https://elsewhere.example/axiom-mcp"}),
        )
        for access in invalid:
            with self.subTest(access_present=access is not None):
                with self.assertRaises(MCPError):
                    await self.invoke("mind_status", access=access)
        self.assertIsNone(await self.storage.mind.load())

    async def test_realtime_transport_rechecks_revoked_portal_session_for_each_tool(self):
        from aicognitive_mind.api import revoke_portal_session, store_portal_session

        portal = SimpleNamespace(state=SimpleNamespace(runtime_records=self.records))
        cookie = "synthetic-realtime-portal-cookie"
        expiry = time.time() + 300
        await store_portal_session(portal, cookie, self.alpha.mind_id, expiry)
        issued = await self.provider.mint_service_access_token(
            subject=self.alpha.mind_id, client_id="axiom-realtime",
            portal_session_key="portal_session_" + hashlib.sha256(cookie.encode()).hexdigest(),
            expires_at=expiry,
        )
        access = await self.provider.load_access_token(issued)
        self.assertIsNotNone(access)
        before = await self.invoke("mind_status", access=access)
        self.assertEqual(before["active_storage"]["mind_id"], self.alpha.mind_id)

        # Simulate a transport retaining its original verified AccessToken:
        # no further OAuth load runs between logout and these actual tool calls.
        await revoke_portal_session(portal, cookie)
        with self.assertRaisesRegex(MCPError, "portal session has ended"):
            await self.invoke("mind_status", access=access)
        with self.assertRaisesRegex(MCPError, "portal session has ended"):
            await self.invoke(
                "complete_interaction", access=access, user_message="Synthetic stale turn",
                response_text="This must never be committed.",
                host_working_context=HostWorkingContext(), idempotency_key="stale-voice-turn",
            )
        tenant = scope_storage(self.storage, self.alpha.mind_id)
        self.assertEqual(await tenant.journal.read(), [])
        self.assertEqual(await tenant.memory.read(), [])
        # Unrelated account OAuth sessions remain usable after this logout.
        normal = await self.invoke("mind_status", self.beta)
        self.assertEqual(normal["active_storage"]["mind_id"], self.beta.mind_id)

    async def test_inactive_and_ambiguous_account_subjects_are_rejected(self):
        key = account_key(self.alpha.username)
        before = await self.records.get(key)
        await self.records.replace(key, before, {**before, "active": False})
        with self.assertRaises(MCPError):
            await self.invoke("mind_status", self.alpha)
        inactive = await self.records.get(key)
        await self.records.replace(key, inactive, before)
        beta_key = account_key(self.beta.username)
        beta_before = await self.records.get(beta_key)
        await self.records.replace(beta_key, beta_before, {
            **beta_before, "account_mind_id": self.alpha.mind_id,
        })
        with self.assertRaises(MCPError):
            await self.invoke("mind_status", self.alpha)
        self.assertIsNone(await self.storage.mind.load())

    async def test_request_arguments_cannot_authorize_another_tenant(self):
        tools = {tool.name: tool for tool in await self.server.list_tools()}
        for name in ("mind_status", "begin_interaction", "complete_interaction"):
            schema = tools[name].input_schema
            self.assertFalse({"mind_id", "account_mind_id", "subject"} & set(schema["properties"]))
        with self.assertRaises(TypeError):
            await self.invoke("mind_status", self.alpha, mind_id=self.beta.mind_id)
        self.assertIsNone(await self.storage.mind.load())

    async def test_execute_task_resolves_only_the_authenticated_tenants_configuration(self):
        alpha_records = RuntimeRecords(scope_storage(self.storage, self.alpha.mind_id).mind)
        await ProviderEndpointRegistry(alpha_records).replace([ProviderEndpoint(
            id="alpha-specialist", name="Synthetic Alpha", base_url="https://unused.example/v1",
            model="synthetic-alpha-model",
        )])
        assignments = TaskModelAssignmentRegistry(alpha_records)
        await assignments.replace([
            TaskModelAssignment(task="coding", provider="alpha-specialist", model="synthetic-alpha-model")
            if item.task == "coding" else item
            for item in await assignments.list()
        ])
        root_assignment = AsyncMock(side_effect=AssertionError("Root task configuration was consulted"))
        root_host = AsyncMock(side_effect=AssertionError("Root host configuration was consulted"))
        self.root_state.task_dispatcher = SimpleNamespace(assignment=root_assignment)
        self.root_state.hosts = SimpleNamespace(active=root_host)
        selected = []

        async def execute(dispatcher, context, payload):
            selected.append(dispatcher.endpoints.records.mind_id)
            self.assertEqual(context.provider, "alpha-specialist")
            self.assertEqual(context.model, "synthetic-alpha-model")
            return {"scope": dispatcher.endpoints.records.mind_id}

        with patch.object(TaskModelDispatcher, "execute", execute):
            alpha = await self.invoke(
                "execute_task", self.alpha, task="coding", operation="chat",
                messages=[{"role": "user", "content": "Synthetic coding task"}],
            )
            beta = await self.invoke(
                "execute_task", self.beta, task="coding", operation="chat",
                messages=[{"role": "user", "content": "Synthetic coding task"}],
            )
        self.assertEqual(alpha["status"], "completed")
        self.assertEqual(alpha["result"]["scope"], self.alpha.mind_id)
        self.assertEqual(selected, [self.alpha.mind_id])
        self.assertEqual(beta["status"], "task_failed")
        self.assertIn("No specialist is selected", beta["error"])
        root_assignment.assert_not_awaited()
        root_host.assert_not_awaited()

    async def test_configured_operator_subject_colliding_with_account_is_rejected(self):
        self.provider.username = self.alpha.mind_id
        with self.assertRaises(MCPError):
            await self.invoke("mind_status", self.alpha)
        self.assertIsNone(await self.storage.mind.load())

    async def test_legacy_subject_requires_one_existing_legacy_account(self):
        access = self.tokens[self.alpha.mind_id].model_copy(update={"subject": "__legacy__"})
        with self.assertRaises(MCPError):
            await self.invoke("mind_status", access=access)
        await self.records.create(account_key("legacy-first"), {
            "kind": "account", "username": "legacy-first", "active": True,
        })
        self.root_state.mind_service.status = AsyncMock(return_value={"legacy_root": True})
        selected = await self.invoke("mind_status", access=access)
        self.assertTrue(selected["legacy_root"])
        await self.records.create(account_key("legacy-second"), {
            "kind": "account", "username": "legacy-second", "active": True,
        })
        with self.assertRaises(MCPError):
            await self.invoke("mind_status", access=access)
        self.assertIsNone(await self.storage.mind.load())

    async def denied_event_principals(self):
        legacy = self.tokens[self.alpha.mind_id].model_copy(update={"subject": "__legacy__"})
        yield "missing_legacy", legacy
        key = account_key("inactive-event-account")
        await self.records.create(key, {
            "kind": "account", "username": "inactive-event-account", "active": False,
        })
        yield "inactive_legacy", legacy
        before = await self.records.get(key)
        await self.records.replace(key, before, {**before, "active": True})
        await self.records.create(account_key("second-event-account"), {
            "kind": "account", "username": "second-event-account", "active": True,
        })
        yield "ambiguous_legacy", legacy
        self.provider.username = self.alpha.mind_id
        try:
            yield "operator_collision", self.tokens[self.alpha.mind_id]
        finally:
            self.provider.username = "legacy-admin"

    async def invoke_event(self, method, access, arguments=None):
        entry = self.server._lowlevel_server._request_handlers[method]
        params = entry.params_type.model_validate(arguments or {})
        ctx = SimpleNamespace(lifespan_context=self.root_state)
        handle = self.current_access.set(access)
        try:
            return await entry.handler(ctx, params)
        finally:
            self.current_access.reset(handle)

    async def test_raw_events_use_each_accounts_registry_and_never_the_root_registry(self):
        import json

        arguments = {
            "name": "sensory.ready", "arguments": {"session_id": "same-body-session"},
            "delivery": {
                "mode": "webhook", "url": "https://callback.example/events",
                "secret": "whsec_" + base64.b64encode(bytes(range(32))).decode(),
            },
        }

        async def verify(_url, _secret, _event_id, payload, _subscription_id, previous_secret=None):
            return 200, json.dumps({"challenge": payload["challenge"]}).encode()

        with patch.object(mcp_events, "post_webhook", AsyncMock(side_effect=verify)) as post:
            subscriptions = []
            for account in (self.alpha, self.beta):
                access = self.tokens[account.mind_id]
                catalog = await self.invoke_event("events/list", access)
                self.assertEqual({item["name"] for item in catalog["events"]},
                                 {"message.created", "sensory.ready"})
                subscriptions.append(await self.invoke_event("events/subscribe", access, arguments))
                state = await RuntimeRecords(scope_storage(
                    self.storage, account.mind_id,
                ).mind).get(mcp_events.STATE_KEY)
                self.assertEqual(len(state["subscriptions"]), 1)
                saved = next(iter(state["subscriptions"].values()))
                self.assertEqual(saved["owner"]["subject"], account.mind_id)
                self.assertEqual(saved["name"], "sensory.ready")
                self.assertEqual((await self.invoke("mind_status", account))[
                    "message_events"
                ]["active_subscriptions"], 1)
                self.assertIsNone(await self.records.get(mcp_events.STATE_KEY))
            self.assertNotEqual(subscriptions[0]["id"], subscriptions[1]["id"])
            self.assertEqual(post.await_count, 2)

            key = account_key(self.alpha.username)
            saved_account = await self.records.get(key)
            self.assertTrue(await self.records.replace(key, saved_account, {**saved_account, "active": False}))
            self.assertEqual(await self.invoke_event(
                "events/list", self.tokens[self.alpha.mind_id],
            ), {"events": []})
            with self.assertRaises(MCPError):
                await self.invoke_event("events/subscribe", self.tokens[self.alpha.mind_id], arguments)
            self.assertEqual(post.await_count, 2, "Revocation must be checked before callback access.")

            cancel = {**arguments, "delivery": {
                key: value for key, value in arguments["delivery"].items() if key != "secret"
            }}
            await self.invoke_event("events/unsubscribe", self.tokens[self.beta.mind_id], cancel)
            beta = await RuntimeRecords(scope_storage(self.storage, self.beta.mind_id).mind).get(mcp_events.STATE_KEY)
            alpha = await RuntimeRecords(scope_storage(self.storage, self.alpha.mind_id).mind).get(mcp_events.STATE_KEY)
            self.assertEqual(beta["subscriptions"], {})
            self.assertEqual(len(alpha["subscriptions"]), 1)
            self.assertIsNone(await self.records.get(mcp_events.STATE_KEY))

    async def test_raw_events_list_does_not_advertise_root_registry_to_invalid_principals(self):
        async for label, access in self.denied_event_principals():
            with self.subTest(principal=label):
                self.assertEqual(await self.invoke_event("events/list", access), {"events": []})

    async def test_raw_event_subscription_rejects_before_webhook_or_registry_write(self):
        arguments = {
            "name": "message.created", "arguments": {},
            "delivery": {
                "mode": "webhook", "url": "https://unused.example/events",
                "secret": "whsec_" + base64.b64encode(bytes(range(32))).decode(),
            },
        }
        post = AsyncMock(side_effect=AssertionError("Unauthorized webhook attempt"))
        create = AsyncMock(side_effect=AssertionError("Unauthorized subscription record write"))
        with patch.object(mcp_events, "post_webhook", post), patch.object(
            self.root_state.hosts.records, "create", create,
        ):
            async for label, access in self.denied_event_principals():
                with self.subTest(principal=label), self.assertRaises(MCPError):
                    await self.invoke_event("events/subscribe", access, arguments)
        post.assert_not_awaited()
        create.assert_not_awaited()
        self.assertIsNone(await self.records.get(mcp_events.STATE_KEY))

    async def test_concurrent_requests_keep_context_and_exception_cleanup_separate(self):
        expected = {
            account.mind_id: (await scope_storage(self.storage, account.mind_id).mind.load()).model_dump(mode="json")["created_at"]
            for account in (self.alpha, self.beta)
        }
        original_status = CognitiveMcpService.status
        both_entered = asyncio.Event()
        entered = 0

        async def overlapping_status(service):
            nonlocal entered
            entered += 1
            if entered == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), 5)
            return await original_status(service)

        with patch.object(CognitiveMcpService, "status", overlapping_status):
            alpha, beta = await asyncio.gather(
                self.invoke("mind_status", self.alpha), self.invoke("mind_status", self.beta),
            )
        self.assertEqual(alpha["mind"]["created_at"], expected[self.alpha.mind_id])
        self.assertEqual(beta["mind"]["created_at"], expected[self.beta.mind_id])
        with self.assertRaises(ValueError):
            await self.invoke("update_current_state", self.alpha, event="unsupported-event")
        after = await self.invoke("mind_status", self.beta)
        self.assertEqual(after["mind"]["created_at"], expected[self.beta.mind_id])
        self.assertIs(self.ctx.request_context.lifespan_context, self.root_state)
        self.assertIs(self.root_state.storage, self.storage)
        self.assertIs(account_mcp.request_state(self.ctx), self.root_state)

    async def test_default_model_steward_still_reports_missing_configuration(self):
        # Stop only the deterministic local adapter: routing must not silently
        # replace the production Steward or fabricate a provider assignment.
        self.steward_patch.stop()
        with self.assertRaisesRegex(Exception, "memory_recall.*provider/model|memory_recall.*assignment"):
            await self.invoke("begin_interaction", self.alpha, user_message="Continue normally.")
        self.assertIsNone(await self.storage.mind.load())


if __name__ == "__main__":
    unittest.main()
