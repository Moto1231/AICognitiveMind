import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.host_runtime import HostAwareCore, HostRuntime, RuntimeRecords


class FakeService:
    async def begin_interaction(self, message):
        return {"ready": message}

    async def complete_interaction(self, message, response_text, **kwargs):
        return {"occurred_at": "2026-10-23T00:00:00Z"}


class HostLifecycleTests(unittest.IsolatedAsyncioTestCase):
    def make_runtime(self):
        mind = SimpleNamespace(mind_id="host-lifecycle-test")
        return mind, HostRuntime(mind, FakeService())

    async def test_stale_idle_host_is_reported_and_can_be_recovered(self):
        mind, runtime = self.make_runtime()
        await runtime.attach("ChatGPT", "GPT-6")
        mind._runtime_records["active_host"]["last_heartbeat_at"] = (
            time.time() - runtime.HEARTBEAT_STALE_AFTER_SECONDS - 1
        )

        self.assertIsNone(await runtime.active())
        status = await runtime.status()
        self.assertFalse(status["connected"])
        self.assertEqual(status["host_state"], "stale")

        replacement = await runtime.attach("ChatGPT", "GPT-6")
        self.assertTrue(replacement["lease_token"])
        self.assertIsNotNone(await runtime.active())
        self.assertEqual(
            mind._runtime_records["active_host"]["last_heartbeat_at"],
            mind._runtime_records["active_host"]["attached_at"],
        )

    async def test_persistent_host_does_not_expire_while_heartbeat_is_fresh(self):
        _, runtime = self.make_runtime()
        attached = await runtime.attach("ChatGPT", "GPT-6", lease_seconds=1)

        await runtime.renew(attached["lease_token"])
        host = await runtime.active()

        self.assertIsNotNone(host)
        self.assertIsNone(host["expires"])

    async def test_fresh_active_host_does_not_scan_pending_requests(self):
        _, runtime = self.make_runtime()
        await runtime.attach("ChatGPT", "GPT-6")
        with patch.object(runtime.records, "pending", wraps=runtime.records.pending) as pending:
            self.assertIsNotNone(await runtime.active())
            pending.assert_not_awaited()

    async def test_next_request_claims_sensory_work_through_shared_host_queue(self):
        mind, runtime = self.make_runtime()
        attached = await runtime.attach("ChatGPT", "GPT-6")
        records = RuntimeRecords(mind)
        request = {
            "kind": "body_request",
            "request_id": "vision-request-1",
            "state": "pending",
            "message": "Interpret this vision percept",
            "created": time.time(),
            "deadline": None,
            "claim": "",
            "claim_until": 0.0,
            "result": {},
        }
        await records.create(request["request_id"], request)

        claimed = await runtime.next_request(attached["lease_token"])

        self.assertEqual(claimed["request_id"], request["request_id"])
        self.assertEqual(claimed["user_message"], request["message"])
        self.assertEqual(claimed["context"], {"ready": request["message"]})

    async def test_no_event_handoff_retains_host_checks_and_completes(self):
        _, runtime = self.make_runtime()
        attached = await runtime.attach("ChatGPT", "GPT-6")
        runtime.active = AsyncMock(wraps=runtime.active)
        fallback = SimpleNamespace(interact=AsyncMock())
        task = asyncio.create_task(HostAwareCore(fallback, runtime).interact("Legacy handoff"))
        try:
            pending = []
            for _ in range(100):
                pending = await runtime.records.pending()
                if pending:
                    break
                await asyncio.sleep(0.001)
            self.assertEqual(len(pending), 1)
            self.assertFalse(pending[0]["notify_message_event"])
            self.assertEqual(runtime.active.await_count, 2)
            claimed = await runtime.next_request(attached["lease_token"])
            await runtime.complete(attached["lease_token"], claimed["request_id"], "Legacy reply")
            self.assertEqual((await task).response_text, "Legacy reply")
            fallback.interact.assert_not_awaited()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_no_event_human_message_still_rejects_missing_host(self):
        _, runtime = self.make_runtime()
        runtime.active = AsyncMock(wraps=runtime.active)
        fallback = SimpleNamespace(interact=AsyncMock())
        with patch("aicognitive_mind.config.body_allow_standalone_fallback_enabled", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "No external reasoning host"):
                await HostAwareCore(fallback, runtime).interact("No connected host")
        runtime.active.assert_awaited_once()
        self.assertEqual(await runtime.records.pending(), [])
        fallback.interact.assert_not_awaited()

    async def test_claimed_work_keeps_stale_host_active_using_actual_queue_snapshot(self):
        mind, runtime = self.make_runtime()
        attached = await runtime.attach("ChatGPT", "GPT-6")
        await runtime.records.create("long-request", {
            "kind": "body_request", "request_id": "long-request", "state": "pending",
            "message": "Long reasoning", "created": time.time(), "deadline": None,
            "claim": "", "claim_until": 0.0, "result": {},
        })
        claimed = await runtime.next_request(attached["lease_token"])
        mind._runtime_records["active_host"]["last_heartbeat_at"] = (
            time.time() - runtime.HEARTBEAT_STALE_AFTER_SECONDS - 1
        )
        snapshot = await runtime.records.pending()
        self.assertIsNone(snapshot[0]["claim_until"])
        with patch.object(runtime.records, "pending", wraps=runtime.records.pending) as pending:
            self.assertIsNotNone(await runtime.active(pending_requests=snapshot))
            pending.assert_not_awaited()
        with self.assertRaises(CommitConflict):
            await runtime.attach("replacement", "another-model")

        await runtime.complete(attached["lease_token"], claimed["request_id"], "Finished")
        empty_snapshot = await runtime.records.pending()
        self.assertEqual(empty_snapshot, [])
        with patch.object(runtime.records, "pending", wraps=runtime.records.pending) as pending:
            self.assertIsNone(await runtime.active(pending_requests=empty_snapshot))
            pending.assert_not_awaited()
        self.assertTrue((await runtime.attach("replacement", "another-model"))["lease_token"])
        with self.assertRaises(PermissionError):
            await runtime.require(attached["lease_token"])

    async def test_expired_or_detached_lease_is_not_revived_by_claimed_request_snapshot(self):
        for lease_state in ("expired", "detached"):
            with self.subTest(lease_state=lease_state):
                mind, runtime = self.make_runtime()
                attached = await runtime.attach("ChatGPT", "GPT-6")
                await runtime.records.create("claimed-request", {
                    "kind": "body_request", "request_id": "claimed-request", "state": "pending",
                    "message": "Reasoning", "created": time.time(), "deadline": None,
                    "claim": "", "claim_until": 0.0, "result": {},
                })
                await runtime.next_request(attached["lease_token"])
                snapshot = await runtime.records.pending()
                self.assertTrue(snapshot[0]["claim"])
                if lease_state == "expired":
                    mind._runtime_records["active_host"]["expires"] = time.time() - 1
                else:
                    await runtime.renew(attached["lease_token"], detach=True)
                self.assertIsNone(await runtime.active(pending_requests=snapshot))
                with self.assertRaises(PermissionError):
                    await runtime.require(attached["lease_token"])


if __name__ == "__main__":
    unittest.main()
