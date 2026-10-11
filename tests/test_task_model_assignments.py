import unittest

from aicognitive_mind.task_model_assignments import (
    TASK_LABELS,
    TaskModelAssignment,
    TaskModelAssignmentRegistry,
)


class FakeRecords:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def create(self, key, value):
        self.values[key] = value

    async def replace(self, key, before, after):
        if self.values.get(key) != before:
            return False
        self.values[key] = after
        return True


class TaskModelAssignmentRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_defaults_include_specialties_but_not_reasoning(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()

        self.assertEqual({item.task for item in assignments}, set(TASK_LABELS))
        self.assertNotIn("reasoning", {item.task for item in assignments})
        self.assertTrue(all(item.provider == "" and item.model == "" for item in assignments))

    async def test_assignments_persist_and_round_trip(self):
        records = FakeRecords()
        registry = TaskModelAssignmentRegistry(records)
        assignments = await registry.list()
        assignments[0] = TaskModelAssignment(
            task=assignments[0].task,
            provider="Example Provider",
            model="example-vision-model",
            fallback_provider="Fallback Provider",
            fallback_model="fallback-vision-model",
        )

        saved = await registry.replace(assignments)
        loaded = await registry.list()

        self.assertEqual(saved, loaded)
        self.assertEqual(loaded[0].provider, "Example Provider")
        self.assertEqual(loaded[0].model, "example-vision-model")
        self.assertEqual(loaded[0].fallback_model, "fallback-vision-model")

    async def test_rejects_incomplete_task_list(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()

        with self.assertRaisesRegex(ValueError, "missing tasks"):
            await registry.replace(assignments[:-1])

    async def test_values_are_trimmed(self):
        assignment = TaskModelAssignment(
            task="vision",
            provider=" Example Provider ",
            model=" example-model ",
        )

        self.assertEqual(assignment.provider, "Example Provider")
        self.assertEqual(assignment.model, "example-model")


if __name__ == "__main__":
    unittest.main()
