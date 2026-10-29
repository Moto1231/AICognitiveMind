import json
import unittest

from aicognitive_mind.task_model_assignments import (
    TASK_LABELS,
    TaskModelAssignment,
    TaskModelAssignmentRegistry,
)
from aicognitive_mind.effective_skills import EffectiveSkillRegistry


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
    async def test_defaults_include_specialties_and_reasoning_with_protected_behaviors(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()

        self.assertEqual({item.task for item in assignments}, set(TASK_LABELS))
        reasoning = next(item for item in assignments if item.task == "reasoning")
        self.assertIn("ground-recalled-context", reasoning.behavior_ids)
        self.assertIn("verify-capabilities", reasoning.behavior_ids)
        self.assertTrue(all(item.provider == "" and item.model == "" for item in assignments))

    async def test_reasoning_assignment_is_populated_from_registered_host(self):
        records = FakeRecords()
        records.values["active_host"] = {"name": "Codex", "model": "gpt-6-sol"}
        assignments = await TaskModelAssignmentRegistry(records).list()
        reasoning = next(item for item in assignments if item.task == "reasoning")
        self.assertEqual(reasoning.provider, "connected-host")
        self.assertEqual(reasoning.model, "gpt-6-sol")
        self.assertNotIn("provider_endpoints", records.values)

    async def test_administrator_can_deselect_protected_reasoning_behavior(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()
        assignments = [item.model_copy(update={"behavior_ids": []})
                       if item.task == "reasoning" else item for item in assignments]
        await registry.replace(assignments)
        reasoning = next(item for item in await registry.list() if item.task == "reasoning")
        self.assertEqual(reasoning.behavior_ids, [])

    async def test_assignments_persist_and_round_trip(self):
        records = FakeRecords()
        registry = TaskModelAssignmentRegistry(records)
        assignments = await registry.list()
        assignments[0] = TaskModelAssignment(
            task=assignments[0].task,
            provider="Example Provider",
            model="example-vision-model",
            fallbacks=[
                {"provider": "Fallback Provider", "model": "fallback-vision-model"},
                {"provider": "Third Provider", "model": "third-vision-model"},
            ],
        )

        saved = await registry.replace(assignments)
        loaded = await registry.list()

        self.assertEqual(saved, loaded)
        self.assertEqual(loaded[0].provider, "Example Provider")
        self.assertEqual(loaded[0].model, "example-vision-model")
        self.assertEqual(loaded[0].fallbacks[0].model, "fallback-vision-model")
        self.assertEqual(loaded[0].fallbacks[1].provider, "Third Provider")

    async def test_clearing_media_specialists_round_trips_without_restoring_models(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()
        for item in assignments:
            if item.task in {"audio", "vision", "audio_voice"}:
                item.provider = "saved-endpoint"
                item.model = "saved-model"
                item.fallbacks = TaskModelAssignment(
                    task=item.task,
                    fallbacks=[{"provider": "backup", "model": "backup-model"}],
                ).fallbacks
        await registry.replace(assignments)
        assignments = await registry.list()
        voice_before = next(item for item in assignments if item.task == "audio_voice").model_dump()
        for item in assignments:
            if item.task in {"audio", "vision"}:
                item.provider = ""
                item.model = ""
                item.fallbacks = []
        await registry.replace(assignments)
        loaded = {item.task: item for item in await registry.list()}
        for task in ("audio", "vision"):
            self.assertEqual(loaded[task].provider, "")
            self.assertEqual(loaded[task].model, "")
            self.assertEqual(loaded[task].fallbacks, [])
        self.assertEqual(loaded["audio_voice"].model_dump(), voice_before)

    async def test_vision_and_audio_preserve_ten_ordered_fallbacks_after_reload(self):
        records = FakeRecords()
        registry = TaskModelAssignmentRegistry(records)
        assignments = await registry.list()
        voice_before = next(item for item in assignments if item.task == "audio_voice").model_dump()
        for task in ("vision", "audio"):
            assignments = [TaskModelAssignment(
                task=task, provider=f"{task}-primary", model=f"{task}-primary-model",
                provider_rotation="ordered",
                fallbacks=[{
                    "provider": f"{task}-backup-{index}",
                    "model": f"{task}-backup-model-{index}",
                } for index in range(1, 11)],
            ) if item.task == task else item for item in assignments]
        await registry.replace(assignments)

        restarted_records = FakeRecords()
        restarted_records.values = json.loads(json.dumps(records.values))
        loaded = {item.task: item for item in await TaskModelAssignmentRegistry(restarted_records).list()}
        for task in ("vision", "audio"):
            with self.subTest(task=task):
                self.assertEqual((loaded[task].provider, loaded[task].model),
                                 (f"{task}-primary", f"{task}-primary-model"))
                self.assertEqual(loaded[task].provider_rotation, "ordered")
                self.assertEqual([item.model_dump() for item in loaded[task].fallbacks], [{
                    "provider": f"{task}-backup-{index}",
                    "model": f"{task}-backup-model-{index}",
                } for index in range(1, 11)])
        self.assertEqual(loaded["audio_voice"].model_dump(), voice_before)

    async def test_migrates_legacy_single_fallback_into_chain(self):
        records = FakeRecords()
        records.values["task_model_assignments"] = {"items": [
            {"task": "vision", "provider": "Primary", "model": "primary-model",
             "fallback_provider": "Backup", "fallback_model": "backup-model"}
        ]}
        loaded = await TaskModelAssignmentRegistry(records).list()
        vision = next(item for item in loaded if item.task == "vision")
        self.assertEqual(vision.fallbacks[0].provider, "Backup")
        self.assertEqual(vision.fallbacks[0].model, "backup-model")

    async def test_rejects_incomplete_task_list(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()

        with self.assertRaisesRegex(ValueError, "missing tasks"):
            await registry.replace(assignments[:-1])

    async def test_rejects_duplicate_task_entries(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        assignments = await registry.list()
        assignments[-1] = assignments[0]

        with self.assertRaisesRegex(ValueError, "duplicate task entries"):
            await registry.replace(assignments)

    async def test_values_are_trimmed(self):
        assignment = TaskModelAssignment(
            task="vision",
            provider=" Example Provider ",
            model=" example-model ",
        )

        self.assertEqual(assignment.provider, "Example Provider")
        self.assertEqual(assignment.model, "example-model")

    async def test_optional_skill_order_round_trips_without_storing_required_core(self):
        records = FakeRecords()
        skills = EffectiveSkillRegistry(records)
        await skills.save("verify", {"name": "Verify", "content": "Verify."}, expected_revision=0)
        await skills.save("explain", {"name": "Explain", "content": "Explain."}, expected_revision=0)
        registry = TaskModelAssignmentRegistry(records)
        assignments = await registry.list()
        vision = next(item for item in assignments if item.task == "vision")
        vision.skill_ids = ["explain", "verify"]
        await registry.replace(assignments)
        loaded = next(item for item in await registry.list() if item.task == "vision")
        self.assertEqual(loaded.skill_ids, ["explain", "verify"])

    async def test_required_or_unknown_skills_cannot_be_saved_as_optional_memberships(self):
        registry = TaskModelAssignmentRegistry(FakeRecords())
        for slug in ("task-vision-core", "missing"):
            assignments = await registry.list()
            next(item for item in assignments if item.task == "vision").skill_ids = [slug]
            with self.subTest(slug=slug), self.assertRaisesRegex(ValueError, "non-assignable"):
                await registry.replace(assignments)


if __name__ == "__main__":
    unittest.main()
