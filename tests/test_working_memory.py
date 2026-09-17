import unittest

from aicognitive_mind.core import UNKNOWN_SPEAKER_KNOWLEDGE, _scope_recalled_knowledge
from aicognitive_mind.storage import InMemoryWorkingMemoryStore
from aicognitive_mind.working_memory import WorkingMemoryTool


class WorkingMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_persists_until_checkpoint_clear(self) -> None:
        store = InMemoryWorkingMemoryStore()
        tool = WorkingMemoryTool(store)

        initial = await tool.invoke({"action": "read"})
        self.assertEqual(initial["working_context"], {})

        updated = await tool.invoke(
            {"action": "set_context", "key": "current_speaker", "value": "William"}
        )
        self.assertEqual(updated["working_context"]["current_speaker"], "William")
        self.assertEqual((await store.read()).context["current_speaker"], "William")

        cleared = await store.clear()
        self.assertEqual(cleared.context, {})
        self.assertEqual((await store.read()).context, {})

    async def test_working_memory_accepts_evolving_context_keys(self) -> None:
        store = InMemoryWorkingMemoryStore()
        tool = WorkingMemoryTool(store)

        await tool.invoke(
            {"action": "set_context", "key": "current_speaker", "value": "William"}
        )
        await tool.invoke(
            {"action": "set_context", "key": "location", "value": "workshop"}
        )
        await tool.invoke(
            {"action": "set_context", "key": "attention", "value": "memory architecture"}
        )

        state = await store.read()
        self.assertEqual(
            state.context,
            {
                "current_speaker": "William",
                "location": "workshop",
                "attention": "memory architecture",
            },
        )

    def test_unknown_speaker_cannot_receive_first_person_recalled_knowledge(self) -> None:
        knowledge = "William's birthday is February 7."

        visible, recall_allowed = _scope_recalled_knowledge(
            "What is my birthday?",
            "unknown",
            knowledge,
        )
        self.assertEqual(visible, UNKNOWN_SPEAKER_KNOWLEDGE)
        self.assertFalse(recall_allowed)

        visible, recall_allowed = _scope_recalled_knowledge(
            "What is my birthday?",
            "William",
            knowledge,
        )
        self.assertEqual(visible, knowledge)
        self.assertTrue(recall_allowed)

        visible, recall_allowed = _scope_recalled_knowledge(
            "What is William's birthday?",
            "unknown",
            knowledge,
        )
        self.assertEqual(visible, knowledge)
        self.assertTrue(recall_allowed)


if __name__ == "__main__":
    unittest.main()
