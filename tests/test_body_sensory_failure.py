"""Unavailable passive media must fail truthfully rather than become an observation."""

import asyncio
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.host_runtime import HostRuntime


class BodySensoryFailureTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = SimpleNamespace(begin_interaction=AsyncMock(), complete_interaction=AsyncMock())
        self.runtime = HostRuntime(SimpleNamespace(mind_id="synthetic-failed-media"), self.service)
        self.token = (await self.runtime.attach("Synthetic media host", "test-model"))["lease_token"]
        self.tasks = []

    async def asyncTearDown(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def queued(self, *, human=False):
        options = {} if human else {
            "priority": 10, "task": "sensory_interpretation",
            "input_context": {
                "modality": "audio", "source": "test-microphone",
                "evidence": {"sha256": "f" * 64, "captured_at": "2026-10-26T20:00:00Z"},
            },
        }
        task = asyncio.create_task(self.runtime.submit("Original preserved input", **options))
        self.tasks.append(task)
        for _ in range(100):
            pending = await self.runtime.records.pending()
            if pending:
                return task, pending[-1]
            await asyncio.sleep(0.001)
        self.fail("Body input was not queued")

    async def test_failure_releases_waiting_caller_without_conscious_or_interpreted_success(self):
        task, before = await self.queued()
        claim = await self.runtime.next_request(self.token)
        reason = "This reasoning interface cannot decode audio input."
        failed = await self.runtime.fail(self.token, claim["request_id"], reason)

        self.assertEqual(failed["status"], "failed")
        self.assertEqual(failed["reason"], reason)
        with self.assertRaisesRegex(RuntimeError, "evidence was saved.*cannot decode audio"):
            await asyncio.wait_for(task, 1)
        stored = await self.runtime.records.get(claim["request_id"])
        self.assertEqual(stored["state"], "failed")
        self.assertEqual(stored["result"], {})
        self.assertEqual(stored["input_context"], before["input_context"])
        self.assertEqual(await self.runtime.records.pending(), [])
        self.service.begin_interaction.assert_not_awaited()
        self.service.complete_interaction.assert_not_awaited()
        ready = await self.runtime.ready_events(self.token, (claim["request_id"],))
        self.assertEqual(ready["finished_request_ids"], [claim["request_id"]])

    async def test_retries_are_idempotent_and_cannot_replace_failure_or_create_success(self):
        task, _ = await self.queued()
        claim = await self.runtime.next_request(self.token)
        first = await self.runtime.fail(self.token, claim["request_id"], "Unsupported audio.")
        self.assertEqual(await self.runtime.fail(
            self.token, claim["request_id"], "  Unsupported audio.  ",
        ), first)
        with self.assertRaisesRegex(CommitConflict, "another reason"):
            await self.runtime.fail(self.token, claim["request_id"], "A different reason.")
        with self.assertRaisesRegex(CommitConflict, "request is failed"):
            await self.runtime.complete(self.token, claim["request_id"], "Invented words")
        with self.assertRaises(RuntimeError):
            await task

    async def test_unclaimed_wrong_owner_and_human_requests_cannot_be_failed(self):
        task, request = await self.queued()
        with self.assertRaises(PermissionError):
            await self.runtime.fail(self.token, request["request_id"], "No claim")
        claim = await self.runtime.next_request(self.token)
        with self.assertRaises(PermissionError):
            await self.runtime.fail("not-the-lease", claim["request_id"], "Wrong owner")
        for invalid in ("", "  ", "x" * 501, None):
            with self.assertRaises(ValueError):
                await self.runtime.fail(self.token, claim["request_id"], invalid)
        self.assertEqual((await self.runtime.records.get(claim["request_id"]))["state"], "pending")
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        human, request = await self.queued(human=True)
        claim = await self.runtime.next_request(self.token)
        with self.assertRaisesRegex(ValueError, "Only passive"):
            await self.runtime.fail(self.token, claim["request_id"], "Do not expire human work")
        self.assertEqual((await self.runtime.records.get(request["request_id"]))["state"], "pending")
        self.assertFalse(human.done())

    async def test_expired_claim_is_not_failed(self):
        task, _ = await self.queued()
        claim = await self.runtime.next_request(self.token)
        request = await self.runtime.records.get(claim["request_id"])
        self.assertTrue(await self.runtime.records.replace(
            claim["request_id"], request, {**request, "claim_until": time.time() - 1},
        ))
        with self.assertRaisesRegex(CommitConflict, "claim expired"):
            await self.runtime.fail(self.token, claim["request_id"], "Too late")
        self.assertEqual((await self.runtime.records.get(claim["request_id"]))["state"], "pending")
        self.assertFalse(task.done())

    async def test_completion_that_wins_storage_race_is_preserved(self):
        task, _ = await self.queued()
        claim = await self.runtime.next_request(self.token)
        replace = self.runtime.records.replace
        result = {"response_text": "Observed successfully", "occurred_at": "2026-10-26T20:00:01Z"}

        async def completion_wins(key, before, after):
            if after.get("state") == "failed":
                self.assertTrue(await replace(key, before, {**before, "state": "complete", "result": result}))
                return False
            return await replace(key, before, after)

        self.runtime.records.replace = completion_wins
        with self.assertRaisesRegex(CommitConflict, "request is complete"):
            await self.runtime.fail(self.token, claim["request_id"], "Unavailable")
        self.assertEqual(await asyncio.wait_for(task, 1), result)
        stored = await self.runtime.records.get(claim["request_id"])
        self.assertEqual(stored["state"], "complete")
        self.assertNotIn("error", stored)

    async def test_event_claim_can_fail_without_starting_a_conscious_interaction(self):
        task, request = await self.queued()
        claim = await self.runtime.claim_incoming_sensory(request["request_id"])
        with self.assertRaises(PermissionError):
            await self.runtime.fail_incoming_sensory("wrong", request["request_id"], "Unsupported")
        failed = await self.runtime.fail_incoming_sensory(
            claim["claim_token"], request["request_id"], "Audio decoder unavailable.",
        )
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(await self.runtime.fail_incoming_sensory(
            claim["claim_token"], request["request_id"], "Audio decoder unavailable.",
        ), failed)
        with self.assertRaisesRegex(RuntimeError, "Audio decoder unavailable"):
            await asyncio.wait_for(task, 1)
        self.assertEqual((await self.runtime.claim_incoming_sensory(request["request_id"]))["status"], "failed")
        self.service.begin_interaction.assert_not_awaited()
        self.service.complete_interaction.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
