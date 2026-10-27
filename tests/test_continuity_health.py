import unittest

from aicognitive_mind.continuity_health import (
    STATE_KEY,
    InteractionContinuityHealth,
)
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.storage import InMemoryMindStore


class InteractionContinuityHealthTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.records = RuntimeRecords(InMemoryMindStore())
        self.health = InteractionContinuityHealth(self.records)

    async def test_fifth_consecutive_failure_is_presented_and_sixth_is_held(self) -> None:
        for index in range(5):
            status = await self.health.record(
                f"failure-{index}", succeeded=False, failure_class="ReviewUnavailable",
            )
            self.assertTrue(status["interaction_outcome"]["presentation_allowed"])
        self.assertTrue(status["circuit_open"])
        self.assertEqual(status["consecutive_failures"], 5)
        self.assertIn("consecutive_failures", status["open_reasons"])

        held = await self.health.record(
            "failure-5", succeeded=False, failure_class="ReviewUnavailable",
        )
        self.assertFalse(held["interaction_outcome"]["presentation_allowed"])
        self.assertEqual(held["consecutive_failures"], 6)

    async def test_rolling_35_of_100_opens_without_five_consecutive_failures(self) -> None:
        for index in range(34):
            await self.health.record(
                f"rolling-failure-{index}",
                succeeded=False,
                failure_class="ReviewUnavailable",
            )
            status = await self.health.record(f"rolling-success-{index}", succeeded=True)
        self.assertFalse(status["circuit_open"])

        threshold = await self.health.record(
            "rolling-failure-34", succeeded=False, failure_class="ReviewUnavailable",
        )
        self.assertTrue(threshold["interaction_outcome"]["presentation_allowed"])
        self.assertEqual(threshold["rolling_failures"], 35)
        self.assertEqual(threshold["consecutive_failures"], 1)
        self.assertEqual(threshold["open_reasons"], ["rolling_failures"])

        recovery = await self.health.record("rolling-recovery", succeeded=True)
        self.assertTrue(recovery["interaction_outcome"]["presentation_allowed"])
        self.assertTrue(recovery["circuit_open"])
        held = await self.health.record(
            "rolling-failure-35", succeeded=False, failure_class="ReviewUnavailable",
        )
        self.assertFalse(held["interaction_outcome"]["presentation_allowed"])

    async def test_successful_identical_retry_replaces_failure_once(self) -> None:
        failed = await self.health.record(
            "retry-key", succeeded=False, failure_class="StorageTimeout",
        )
        self.assertEqual(failed["rolling_sample_size"], 1)
        self.assertEqual(failed["rolling_failures"], 1)

        recovered = await self.health.record("retry-key", succeeded=True)
        self.assertEqual(recovered["rolling_sample_size"], 1)
        self.assertEqual(recovered["rolling_failures"], 0)
        self.assertEqual(recovered["consecutive_failures"], 0)
        self.assertTrue(recovered["interaction_outcome"]["presentation_allowed"])

        unchanged = await self.health.record(
            "retry-key", succeeded=False, failure_class="LateDuplicate",
        )
        self.assertEqual(unchanged["rolling_failures"], 0)
        self.assertTrue(unchanged["interaction_outcome"]["succeeded"])

    async def test_rolling_window_evicts_old_failures(self) -> None:
        for index in range(35):
            await self.health.record(
                f"old-failure-{index}", succeeded=False, failure_class="ReviewUnavailable",
            )
        for index in range(65):
            status = await self.health.record(f"success-{index}", succeeded=True)
        self.assertEqual(status["rolling_sample_size"], 100)
        self.assertEqual(status["rolling_failures"], 35)
        self.assertTrue(status["circuit_open"])

        status = await self.health.record("evict-oldest-failure", succeeded=True)
        self.assertEqual(status["rolling_sample_size"], 100)
        self.assertEqual(status["rolling_failures"], 34)
        self.assertFalse(status["circuit_open"])

    async def test_runtime_record_contains_no_conversation_content(self) -> None:
        await self.health.record(
            "opaque-interaction-key", succeeded=False, failure_class="ReviewUnavailable",
        )
        stored = await self.records.get(STATE_KEY)
        self.assertNotIn("message", stored)
        self.assertNotIn("response", stored)
        self.assertNotIn("content", stored)
        self.assertEqual(
            set(stored["recent_outcomes"][0]),
            {
                "interaction_id",
                "succeeded",
                "failure_class",
                "presentation_allowed",
                "recorded_at",
                "recovered_after_retry",
                "recovery_was_required",
            },
        )
