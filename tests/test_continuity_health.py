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
            self.assertFalse(status["interaction_outcome"]["report_persistence_error"])
        self.assertEqual(status["name"], "The Breaker")
        self.assertTrue(status["circuit_open"])
        self.assertEqual(status["consecutive_failures"], 5)
        self.assertIn("consecutive_failures", status["open_reasons"])

        held = await self.health.record(
            "failure-5", succeeded=False, failure_class="ReviewUnavailable",
        )
        self.assertFalse(held["interaction_outcome"]["presentation_allowed"])
        self.assertTrue(held["interaction_outcome"]["report_persistence_error"])
        self.assertEqual(held["consecutive_failures"], 6)

    async def test_rolling_35_of_100_waits_for_a_complete_window(self) -> None:
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
        self.assertFalse(threshold["interaction_outcome"]["report_persistence_error"])
        self.assertEqual(threshold["rolling_failures"], 35)
        self.assertEqual(threshold["consecutive_failures"], 1)
        self.assertEqual(threshold["rolling_sample_size"], 69)
        self.assertFalse(threshold["rolling_window_ready"])
        self.assertEqual(threshold["open_reasons"], [])

        for index in range(31):
            full_window = await self.health.record(f"window-success-{index}", succeeded=True)
        self.assertEqual(full_window["rolling_sample_size"], 100)
        self.assertTrue(full_window["rolling_window_ready"])
        self.assertEqual(full_window["open_reasons"], ["rolling_failures"])
        held = await self.health.record(
            "rolling-failure-35", succeeded=False, failure_class="ReviewUnavailable",
        )
        self.assertFalse(held["interaction_outcome"]["presentation_allowed"])
        self.assertTrue(held["interaction_outcome"]["report_persistence_error"])

    async def test_degraded_review_is_warning_only_even_while_rolling_circuit_is_open(self) -> None:
        for index in range(65):
            await self.health.record(f"success-{index}", succeeded=True)
        for index in range(35):
            opened = await self.health.record(
                f"failure-{index}", succeeded=False, failure_class="StorageTimeout",
            )
        self.assertTrue(opened["circuit_open"])

        degraded = await self.health.record(
            "journal-committed",
            succeeded=True,
            degraded=True,
            degradation_class="StewardAssessmentExhausted",
        )
        self.assertTrue(degraded["circuit_open"])
        self.assertTrue(degraded["interaction_outcome"]["presentation_allowed"])
        self.assertFalse(degraded["interaction_outcome"]["report_persistence_error"])
        self.assertTrue(degraded["interaction_outcome"]["degraded"])
        self.assertEqual(degraded["rolling_failures"], 35)
        self.assertEqual(degraded["degraded_reviews"], 1)
        self.assertEqual(degraded["consecutive_failures"], 0)
        self.assertEqual(degraded["last_degradation_class"], "StewardAssessmentExhausted")

    async def test_reset_clears_breaker_history_and_preserves_reset_audit(self) -> None:
        for index in range(5):
            await self.health.record(
                f"failure-{index}", succeeded=False, failure_class="StorageTimeout",
            )
        reset = await self.health.reset()
        self.assertFalse(reset["circuit_open"])
        self.assertEqual(reset["rolling_sample_size"], 0)
        self.assertEqual(reset["rolling_failures"], 0)
        self.assertEqual(reset["degraded_reviews"], 0)
        self.assertEqual(reset["reset_count"], 1)
        self.assertIsNotNone(reset["last_reset_at"])
        stored = await self.records.get(STATE_KEY)
        self.assertEqual(stored["recent_outcomes"], [])
        self.assertEqual(stored["version"], 2)

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
                "degraded",
                "degradation_class",
                "presentation_allowed",
                "recorded_at",
                "recovered_after_retry",
                "recovery_was_required",
            },
        )

    async def test_configured_thresholds_and_window_apply_without_losing_history(self) -> None:
        settings = {
            "consecutive_failure_limit": 2,
            "rolling_failure_limit": 3,
            "rolling_window_size": 20,
        }
        first = await self.health.record(
            "custom-1", succeeded=False, failure_class="ReviewUnavailable",
            settings=settings,
        )
        self.assertFalse(first["circuit_open"])
        second = await self.health.record(
            "custom-2", succeeded=False, failure_class="ReviewUnavailable",
            settings=settings,
        )
        self.assertTrue(second["circuit_open"])
        self.assertEqual(second["thresholds"], {
            "consecutive_failures": 2, "rolling_failures": 3, "rolling_window_size": 20,
        })

        for index in range(30):
            await self.health.record(f"later-{index}", succeeded=True, settings=settings)
        stored = await self.records.get(STATE_KEY)
        self.assertEqual(len(stored["recent_outcomes"]), 32)
        narrowed = await self.health.snapshot(settings=settings)
        self.assertEqual(narrowed["rolling_sample_size"], 20)
