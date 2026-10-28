import unittest
from copy import deepcopy

from pydantic import ValidationError

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.continuity_settings import (
    ContinuitySettingsConflict,
    ContinuitySettingsRegistry,
)


class Records:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return deepcopy(self.values.get(key))

    async def create(self, key, value):
        if key in self.values:
            raise CommitConflict("Already exists")
        self.values[key] = deepcopy(value)

    async def replace(self, key, before, after):
        if self.values.get(key) != before:
            return False
        self.values[key] = deepcopy(after)
        return True


class ContinuitySettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_are_revisioned_and_saved_with_cas(self):
        records = Records()
        registry = ContinuitySettingsRegistry(records)
        defaults = await registry.effective()
        self.assertEqual(defaults["revision"], 0)
        self.assertEqual(defaults["consecutive_failure_limit"], 5)
        self.assertEqual(defaults["rolling_failure_limit"], 35)
        self.assertEqual(defaults["rolling_window_size"], 100)
        self.assertEqual(defaults["provider_request_timeout_seconds"], 30)
        self.assertEqual(defaults["steward_assessment_timeout_seconds"], 60)
        self.assertEqual(defaults["rate_limit_retry_wait_cap_seconds"], 45)

        saved = await registry.save({
            "consecutive_failure_limit": 6,
            "rolling_failure_limit": 40,
            "rolling_window_size": 120,
            "provider_request_timeout_seconds": 20,
            "steward_assessment_timeout_seconds": 90,
            "rate_limit_retry_wait_cap_seconds": 15,
        }, expected_revision=0)
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(saved["source"], "administrator_override")
        self.assertEqual(saved["updated_by"], "administrator")
        with self.assertRaises(ContinuitySettingsConflict):
            await registry.save({"consecutive_failure_limit": 7}, expected_revision=0)

    async def test_invalid_threshold_relationships_are_rejected(self):
        registry = ContinuitySettingsRegistry(Records())
        for changes in (
            {"rolling_failure_limit": 4},
            {"rolling_failure_limit": 101},
            {"consecutive_failure_limit": 0},
            {"provider_request_timeout_seconds": 121},
            {"unsupported": 1},
        ):
            with self.subTest(changes=changes), self.assertRaises((ValueError, ValidationError)):
                await registry.save(changes, expected_revision=0)

    async def test_interaction_keeps_captured_revision_after_admin_edit(self):
        registry = ContinuitySettingsRegistry(Records())
        captured = await registry.capture("interaction-one")
        await registry.save({
            "consecutive_failure_limit": 2,
            "rolling_failure_limit": 10,
            "rolling_window_size": 40,
        }, expected_revision=0)
        bound = await registry.for_interaction("interaction-one")
        current = await registry.for_interaction("not-captured")
        self.assertEqual(bound["revision"], captured["revision"])
        self.assertEqual(bound["consecutive_failure_limit"], 5)
        self.assertEqual(bound["source"], "interaction_snapshot")
        self.assertEqual(current["revision"], 1)
        self.assertEqual(current["consecutive_failure_limit"], 2)

    async def test_interaction_snapshots_are_bounded_and_contain_no_content(self):
        records = Records()
        registry = ContinuitySettingsRegistry(records)
        for index in range(ContinuitySettingsRegistry.SNAPSHOT_LIMIT + 2):
            await registry.capture(f"opaque-{index}")
        stored = records.values[registry.SNAPSHOT_KEY]
        self.assertEqual(len(stored["items"]), registry.SNAPSHOT_LIMIT)
        self.assertEqual(stored["items"][0]["interaction_id"], "opaque-2")
        self.assertNotIn("message", str(stored).lower())
        self.assertNotIn("response", str(stored).lower())


if __name__ == "__main__":
    unittest.main()
