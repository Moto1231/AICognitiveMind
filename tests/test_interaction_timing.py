"""Attribute wrapper latency without exposing interaction payloads in timing logs."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp.server.auth.provider import AccessToken

from aicognitive_mind.chatgpt_mcp import build_chatgpt_mcp
from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
from aicognitive_mind.commit import atomic, commit, receipt, revision
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.host_runtime import HostRuntime


class InteractionTimingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = 0.0
        self.clock_patch = patch(
            "aicognitive_mind.timing.time.perf_counter", side_effect=lambda: self.clock,
        )
        self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        self.enabled_patch = patch("aicognitive_mind.timing.ENABLED", True)
        self.enabled_patch.start()
        self.addCleanup(self.enabled_patch.stop)
        self.secret = "private-user-message-and-key"
        provider = AxiomAuthorizationServerProvider(
            "https://axiom.example", username="mind", password="secret",
        )
        self.access_patch = patch(
            "aicognitive_mind.account_mcp.get_access_token",
            return_value=AccessToken(
                token="synthetic-timing-access", client_id="timing-fixture",
                subject=provider.username, scopes=[provider.required_scope],
                resource=provider.resource_url,
            ),
        )
        self.access_patch.start()
        self.addCleanup(self.access_patch.stop)

    def server(self):
        base = "https://axiom.example"
        provider = AxiomAuthorizationServerProvider(base, username="mind", password="secret")
        return build_chatgpt_mcp(base, provider)

    def context(self, service, diagnostics):
        return SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(
                mind_service=service,
                storage=SimpleNamespace(mind=object(), diagnostics=diagnostics),
            ),
        ))

    def assert_private(self, log):
        self.assertNotIn(self.secret, log)
        self.assertNotIn("private-error-detail", log)

    async def test_begin_attributes_queue_host_and_trace_delays_outside_service(self):
        snapshot = [{"message": self.secret, "priority": 0}]

        async def begin(*args):
            self.clock += 2
            return {"status": "ready_to_reason", "idempotency_key": self.secret}

        async def pending():
            self.clock += 3
            return snapshot

        async def active(*, pending_requests):
            self.assertIs(pending_requests, snapshot)
            self.clock += 5
            return {"lease_token": self.secret}

        async def record(observation):
            self.clock += 7

        service = SimpleNamespace(begin_interaction=AsyncMock(side_effect=begin))
        diagnostics = SimpleNamespace(record=AsyncMock(side_effect=record))
        hosts = SimpleNamespace(
            records=SimpleNamespace(pending=AsyncMock(side_effect=pending)),
            active=AsyncMock(side_effect=active),
        )
        tool = self.server()._tool_manager.get_tool("begin_interaction").fn
        with patch("aicognitive_mind.chatgpt_mcp.HostRuntime", return_value=hosts):
            with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
                result = await tool(user_message=self.secret, ctx=self.context(service, diagnostics))

        self.assertEqual(result["idempotency_key"], self.secret)
        self.assertTrue(result["body_work"]["host_attached"])
        self.assertEqual(result["body_work"]["pending_human_messages"], 1)
        hosts.records.pending.assert_awaited_once_with()
        hosts.active.assert_awaited_once_with(pending_requests=snapshot)
        self.assertEqual(diagnostics.record.await_count, 1)
        log = "\n".join(logs.output)
        for expected in (
            "mcp.begin_interaction total=17.000s", "service=2.000s",
            "body_queue=3.000s", "active_host=5.000s", "trace=7.000s",
        ):
            self.assertIn(expected, log)
        self.assert_private(log)

    def body_request_scenarios(self, now):
        queued = [
            {"priority": 0, "message": self.secret},
            {"priority": 10, "message": "Interpret this audio percept."},
            {"priority": 5, "message": "Other queued work."},
        ]
        for label, claim, claim_until, attached in (
            ("valid claim", "test-claim", now + 30, True),
            ("indefinite claim", "test-claim", None, True),
            ("expired claim", "test-claim", now - 1, False),
            ("unclaimed request", None, None, False),
        ):
            claimed = {
                "priority": 10, "message": "Interpret this vision percept.",
                "claim": claim, "claim_until": claim_until,
            }
            yield label, [claimed, *queued], attached
        yield "empty snapshot", [], False

    async def stale_host_runtime(self, service, requests, now):
        mind = SimpleNamespace(mind_id="timing-fixture")
        hosts = HostRuntime(mind, service)
        await hosts.records.create("active_host", {
            "name": "Timing fixture", "model": "fixture-model", "expires": None,
            "last_heartbeat_at": now - hosts.HEARTBEAT_STALE_AFTER_SECONDS - 1,
        })
        for index, request in enumerate(requests):
            await hosts.records.create(f"request-{index}", {
                "kind": "body_request", "request_id": f"request-{index}", "state": "pending",
                "created": now - 10 + index, "deadline": now + 60, **request,
            })
        snapshots = []
        read_pending = hosts.records.pending

        async def pending():
            snapshot = await read_pending()
            snapshots.append(snapshot)
            return snapshot

        hosts.records.pending = AsyncMock(side_effect=pending)
        return hosts, mind, snapshots

    async def test_begin_reuses_real_pending_snapshot_for_stale_host_claims(self):
        now = 1000.0
        tool = self.server()._tool_manager.get_tool("begin_interaction").fn
        for label, requests, attached in self.body_request_scenarios(now):
            with self.subTest(case=label):
                service = SimpleNamespace(begin_interaction=AsyncMock(return_value={
                    "status": "ready_to_reason", "idempotency_key": self.secret,
                }))
                diagnostics = SimpleNamespace(record=AsyncMock())
                hosts, mind, snapshots = await self.stale_host_runtime(service, requests, now)
                hosts.active = AsyncMock(wraps=hosts.active)
                ctx = self.context(service, diagnostics)
                ctx.request_context.lifespan_context.storage.mind = mind
                with (
                    patch("aicognitive_mind.host_runtime.time.time", return_value=now),
                    patch("aicognitive_mind.chatgpt_mcp.HostRuntime", return_value=hosts),
                ):
                    result = await tool(user_message=self.secret, ctx=ctx)

                hosts.records.pending.assert_awaited_once_with()
                self.assertIs(hosts.active.await_args.kwargs["pending_requests"], snapshots[0])
                summary = result["body_work"]
                in_progress = int(attached)
                self.assertEqual(summary["host_attached"], attached)
                self.assertEqual(summary["in_progress_requests"], in_progress)
                self.assertEqual(summary["pending_requests"], len(requests) - in_progress)
                self.assertEqual(summary["pending_human_messages"], int(bool(requests)))
                self.assertEqual(summary["pending_other_requests"], int(bool(requests)))
                self.assertEqual(
                    summary["pending_sensory_interpretations"],
                    2 - in_progress if requests else 0,
                )
                self.assertEqual(result["idempotency_key"], self.secret)
                diagnostics.record.assert_awaited_once()

    async def test_status_reuses_real_pending_snapshot_for_stale_host_claims(self):
        now = 1000.0
        for label, requests, attached in self.body_request_scenarios(now):
            with self.subTest(case=label):
                hosts, _mind, _snapshots = await self.stale_host_runtime(
                    SimpleNamespace(), requests, now,
                )
                with patch("aicognitive_mind.host_runtime.time.time", return_value=now):
                    status = await hosts.status()

                hosts.records.pending.assert_awaited_once_with()
                self.assertEqual(status["connected"], attached)
                self.assertEqual(status["host_state"], "connected" if attached else "stale")
                self.assertEqual(status["requests"]["in_progress"], int(attached))
                self.assertEqual(status["requests"]["pending"], len(requests) - int(attached))
                self.assertEqual(len(status["requests"]["items"]), len(requests))

    async def test_begin_failed_queue_still_logs_partial_stages_and_error_class(self):
        async def pending():
            self.clock += 11
            raise RuntimeError("private-error-detail")

        service = SimpleNamespace(begin_interaction=AsyncMock(return_value={
            "status": "ready_to_reason", "idempotency_key": self.secret,
        }))
        diagnostics = SimpleNamespace(record=AsyncMock())
        hosts = SimpleNamespace(
            records=SimpleNamespace(pending=AsyncMock(side_effect=pending)),
            active=AsyncMock(),
        )
        tool = self.server()._tool_manager.get_tool("begin_interaction").fn
        with patch("aicognitive_mind.chatgpt_mcp.HostRuntime", return_value=hosts):
            with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
                with self.assertRaisesRegex(RuntimeError, "private-error-detail"):
                    await tool(user_message=self.secret, ctx=self.context(service, diagnostics))
        hosts.active.assert_not_awaited()
        diagnostics.record.assert_not_awaited()
        log = "\n".join(logs.output)
        self.assertIn("mcp.begin_interaction error=RuntimeError", log)
        self.assertIn("body_queue=11.000s", log)
        self.assertIn("total=11.000s", log)
        self.assert_private(log)

    async def test_complete_attributes_trace_writes_and_keeps_commit_result(self):
        async def complete(**kwargs):
            self.clock += 3
            return {"status": "interaction_committed"}

        async def record(observation):
            self.clock += 2

        service = SimpleNamespace(complete_interaction=AsyncMock(side_effect=complete))
        diagnostics = SimpleNamespace(record=AsyncMock(side_effect=record))
        tool = self.server()._tool_manager.get_tool("complete_interaction").fn
        with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
            result = await tool(
                user_message=self.secret, response_text=self.secret,
                host_working_context=HostWorkingContext(summary=self.secret),
                idempotency_key=self.secret, proposed_memories=[],
                ctx=self.context(service, diagnostics),
            )
        self.assertEqual(result["status"], "interaction_committed")
        self.assertEqual(result["interaction_trace_id"], self.secret)
        service.complete_interaction.assert_awaited_once_with(
            user_message=self.secret, response_text=self.secret,
            proposed_memories=(), current_evidence=(), idempotency_key=self.secret,
            host_working_context=HostWorkingContext(summary=self.secret).model_dump(mode="json"),
        )
        self.assertEqual(diagnostics.record.await_count, 2)
        log = "\n".join(logs.output)
        for expected in (
            "mcp.complete_interaction total=7.000s", "trace_request=2.000s",
            "service=3.000s", "trace_response=2.000s",
        ):
            self.assertIn(expected, log)
        self.assert_private(log)

    async def test_complete_failed_service_logs_error_trace_without_error_text(self):
        async def complete(**kwargs):
            self.clock += 3
            raise ValueError("private-error-detail")

        async def record(observation):
            self.clock += 2

        service = SimpleNamespace(complete_interaction=AsyncMock(side_effect=complete))
        diagnostics = SimpleNamespace(record=AsyncMock(side_effect=record))
        tool = self.server()._tool_manager.get_tool("complete_interaction").fn
        with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
            with self.assertRaisesRegex(ValueError, "private-error-detail"):
                await tool(
                    user_message=self.secret, response_text=self.secret,
                    host_working_context=HostWorkingContext(), idempotency_key=self.secret,
                    proposed_memories=[], ctx=self.context(service, diagnostics),
                )
        self.assertEqual(diagnostics.record.await_count, 2)
        self.assertEqual(
            diagnostics.record.await_args.args[0].implementation["phase"], "complete_error",
        )
        log = "\n".join(logs.output)
        for expected in (
            "mcp.complete_interaction error=ValueError", "total=7.000s",
            "trace_request=2.000s", "service=3.000s", "trace_error=2.000s",
        ):
            self.assertIn(expected, log)
        self.assert_private(log)

    async def test_atomic_attributes_receipt_revision_commit_and_retry(self):
        clock = self

        class Service:
            def __init__(self):
                self._journal = SimpleNamespace(_policy=object(), _entries=[])
                self.calls = []

            @atomic
            async def operation(self, message, idempotency_key=None):
                clock.clock += 7
                self.calls.append(message)
                return {"answer": message}

        async def timed_receipt(*args):
            self.clock += 3
            return await receipt(*args)

        async def timed_revision(*args):
            self.clock += 2
            return await revision(*args)

        async def timed_commit(*args):
            self.clock += 5
            return await commit(*args)

        service = Service()
        with (
            patch("aicognitive_mind.commit.receipt", side_effect=timed_receipt),
            patch("aicognitive_mind.commit.revision", side_effect=timed_revision),
            patch("aicognitive_mind.commit.commit", side_effect=timed_commit),
        ):
            with self.assertLogs("aicognitive_mind.timing", level="INFO") as first_logs:
                first = await service.operation(self.secret, idempotency_key=self.secret)
            with self.assertLogs("aicognitive_mind.timing", level="INFO") as retry_logs:
                retry = await service.operation(self.secret, idempotency_key=self.secret)
        self.assertEqual(first, {"answer": self.secret})
        self.assertEqual(retry, first)
        self.assertEqual(service.calls, [self.secret])
        self.assertEqual(service._journal._commit_revision, 1)
        log = "\n".join(first_logs.output)
        for expected in (
            "commit.atomic method=operation total=17.000s", "receipt=3.000s",
            "revision=2.000s", "method=7.000s", "commit=5.000s",
        ):
            self.assertIn(expected, log)
        retry_log = "\n".join(retry_logs.output)
        self.assertIn("total=3.000s", retry_log)
        self.assertNotIn("commit=", retry_log)
        self.assert_private(log + retry_log)

    async def test_atomic_uncertain_commit_recovers_receipt_once(self):
        class Service:
            def __init__(self):
                self._journal = SimpleNamespace(_policy=object(), _entries=[])

            @atomic
            async def operation(self, message, idempotency_key=None):
                return {"answer": message}

        async def uncertain_commit(*args):
            await commit(*args)
            self.clock += 5
            raise RuntimeError("private-error-detail")

        async def timed_receipt(*args):
            self.clock += 3
            return await receipt(*args)

        service = Service()
        with (
            patch("aicognitive_mind.commit.receipt", side_effect=timed_receipt),
            patch("aicognitive_mind.commit.commit", side_effect=uncertain_commit) as write,
        ):
            with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
                result = await service.operation(self.secret, idempotency_key=self.secret)
        self.assertEqual(result, {"answer": self.secret})
        self.assertEqual(service._journal._commit_revision, 1)
        write.assert_awaited_once()
        log = "\n".join(logs.output)
        self.assertIn("total=11.000s", log)
        self.assertIn("recovery_receipt=3.000s", log)
        self.assert_private(log)
