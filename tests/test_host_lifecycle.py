import time
import unittest
from types import SimpleNamespace

from aicognitive_mind.host_runtime import HostRuntime, RuntimeRecords


class FakeService:
    async def begin_interaction(self, message):
        return {"ready": message}


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


if __name__ == "__main__":
    unittest.main()
