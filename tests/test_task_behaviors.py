import unittest

from aicognitive_mind.task_behaviors import (
    TASK_FOUNDATIONS,
    TaskBehaviorRegistry,
    TaskExecutionContext,
    TaskPromptAssembler,
)
from aicognitive_mind.task_behaviors import TASK_BEHAVIOR_LABELS
from aicognitive_mind.host_behaviors import HostBehavior, HostBehaviorRegistry
from aicognitive_mind.task_model_assignments import TaskModelAssignmentRegistry


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


class TaskBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_task_has_code_owned_foundation_and_mutable_profile(self):
        registry = TaskBehaviorRegistry(FakeRecords())
        profiles = await registry.list()
        self.assertEqual({item.task for item in profiles}, set(TASK_BEHAVIOR_LABELS))
        self.assertEqual(set(TASK_FOUNDATIONS), set(TASK_BEHAVIOR_LABELS))
        for profile in profiles:
            self.assertTrue(TASK_FOUNDATIONS[profile.task])

    async def test_external_behavior_is_mutable_but_does_not_replace_foundation(self):
        registry = TaskBehaviorRegistry(FakeRecords())
        profiles = await registry.list()
        updated = [
            item.model_copy(update={"instructions": "Be concise and state uncertainty."})
            if item.task == "vision" else item
            for item in profiles
        ]
        saved = await registry.replace(updated)
        vision = next(item for item in saved if item.task == "vision")
        self.assertEqual(vision.instructions, "Be concise and state uncertainty.")
        self.assertEqual(vision.revision, 2)
        audio = next(item for item in saved if item.task == "audio")
        self.assertEqual(audio.instructions, "")
        self.assertEqual(audio.revision, 1)
        self.assertEqual(TASK_FOUNDATIONS["vision"].startswith("You are Axiom"), True)
        self.assertFalse(hasattr(vision, "foundation"))

    async def test_prompt_layers_foundation_behavior_assignment_and_compact_context(self):
        registry = TaskBehaviorRegistry(FakeRecords())
        profiles = await registry.list()
        await registry.replace([
            item.model_copy(update={"instructions": "Be concise."})
            if item.task == "vision" else item
            for item in profiles
        ])
        assembler = TaskPromptAssembler(registry)
        prompt = await assembler.system_prompt(TaskExecutionContext(
            task="vision",
            provider="local",
            model="vision-model",
            behavior_revision=2,
            session_id="session-17",
            state_ref="working-state-9",
            memory_refs=("memory-3",),
            working_context="Current frame shows a doorway.",
        ))
        self.assertLess(prompt.index("IMMUTABLE AXIOM TASK FOUNDATION"), prompt.index("CONFIGURABLE TASK BEHAVIOR"))
        self.assertLess(prompt.index("CONFIGURABLE TASK BEHAVIOR"), prompt.index("CURRENT ASSIGNMENT"))
        self.assertIn(TASK_FOUNDATIONS["vision"], prompt)
        self.assertIn("Be concise.", prompt)
        self.assertIn("Model: vision-model", prompt)
        self.assertIn("Session reference: session-17", prompt)
        self.assertIn("Working-state reference: working-state-9", prompt)
        self.assertIn("memory-3", prompt)
        self.assertIn("Current frame shows a doorway.", prompt)
        self.assertNotIn("entire conversation", prompt)

    async def test_empty_behavior_does_not_hide_immutable_foundation(self):
        registry = TaskBehaviorRegistry(FakeRecords())
        assembler = TaskPromptAssembler(registry)
        prompt = await assembler.system_prompt(TaskExecutionContext(task="audio"))
        self.assertIn(TASK_FOUNDATIONS["audio"], prompt)
        self.assertNotIn("CONFIGURABLE TASK BEHAVIOR", prompt)

    async def test_reasoning_has_its_own_mutable_profile_without_model_assignment(self):
        registry = TaskBehaviorRegistry(FakeRecords())
        profiles = await registry.list()
        reasoning = next(item for item in profiles if item.task == "reasoning")
        self.assertEqual(reasoning.name, "Reasoning (connected host)")
        prompt = await TaskPromptAssembler(registry).system_prompt(TaskExecutionContext(task="reasoning", provider="connected-host", model="host-selected"))
        self.assertIn(TASK_FOUNDATIONS["reasoning"], prompt)
        self.assertIn("Model: host-selected", prompt)

    async def test_shared_catalog_behavior_applies_only_to_selected_tasks(self):
        records = FakeRecords()
        catalog = HostBehaviorRegistry(records)
        await catalog.replace([
            *await catalog.list(),
            HostBehavior(id="concise", name="Concise", instruction="Use short sentences."),
        ])
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace([
            item.model_copy(update={"behavior_ids": ["concise"]}) if item.task == "coding" else item
            for item in await assignments.list()
        ])
        assembler = TaskPromptAssembler(TaskBehaviorRegistry(records))
        coding = await assembler.system_prompt(TaskExecutionContext(task="coding"))
        vision = await assembler.system_prompt(TaskExecutionContext(task="vision"))
        self.assertIn("Use short sentences.", coding)
        self.assertNotIn("Use short sentences.", vision)
        self.assertNotIn("ground-recalled-context", coding)

    async def test_legacy_inline_instructions_survive_catalog_membership_save(self):
        records = FakeRecords()
        profiles = TaskBehaviorRegistry(records)
        await profiles.replace([
            item.model_copy(update={"instructions": "Describe the evidence before interpreting."})
            if item.task == "vision" else item for item in await profiles.list()
        ])
        assignments = TaskModelAssignmentRegistry(records)
        loaded = await assignments.list()
        vision = next(item for item in loaded if item.task == "vision")
        self.assertEqual(vision.behavior_ids, ["task-vision-legacy"])
        await assignments.replace(loaded)
        self.assertIn("host_behaviors", records.values)
        catalog = HostBehaviorRegistry(records)
        await catalog.replace([
            item.model_copy(update={"instruction": "Updated in the Behaviors form."})
            if item.id == "task-vision-legacy" else item for item in await catalog.list()
        ])
        prompt = await TaskPromptAssembler(profiles).system_prompt(TaskExecutionContext(task="vision"))
        self.assertIn("Updated in the Behaviors form.", prompt)
        self.assertNotIn("Describe the evidence before interpreting.", prompt)

    async def test_removed_behavior_membership_is_ignored_and_cleaned_on_read(self):
        records = FakeRecords()
        catalog = HostBehaviorRegistry(records)
        await catalog.replace([
            *await catalog.list(),
            HostBehavior(id="temporary", name="Temporary", instruction="Temporary rule."),
        ])
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace([
            item.model_copy(update={"behavior_ids": ["temporary"]}) if item.task == "vision" else item
            for item in await assignments.list()
        ])
        await catalog.replace([item for item in await catalog.list() if item.id != "temporary"])
        vision = next(item for item in await assignments.list() if item.task == "vision")
        self.assertEqual(vision.behavior_ids, [])
        prompt = await TaskPromptAssembler(TaskBehaviorRegistry(records)).system_prompt(TaskExecutionContext(task="vision"))
        self.assertNotIn("Temporary rule.", prompt)

    async def test_removing_promoted_instruction_does_not_restore_it_from_old_profile(self):
        records = FakeRecords()
        profiles = TaskBehaviorRegistry(records)
        await profiles.replace([
            item.model_copy(update={"instructions": "Old instruction to remove."})
            if item.task == "vision" else item for item in await profiles.list()
        ])
        catalog = HostBehaviorRegistry(records)
        await catalog.replace([item for item in await catalog.list() if item.id != "task-vision-legacy"])
        self.assertNotIn("task-vision-legacy", {item.id for item in await catalog.list()})
        prompt = await TaskPromptAssembler(profiles).system_prompt(TaskExecutionContext(task="vision"))
        self.assertNotIn("Old instruction to remove.", prompt)


if __name__ == "__main__":
    unittest.main()
