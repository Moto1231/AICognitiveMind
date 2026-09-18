import unittest

from aicognitive_mind.core import (
    IDENTITY_CLARIFICATION_RESPONSE,
    UNKNOWN_SPEAKER_KNOWLEDGE,
    _explicit_speaker_identity,
    _requires_speaker_identity,
    _scope_recalled_knowledge,
)
from aicognitive_mind.storage import InMemoryWorkingMemoryStore
from aicognitive_mind.working_memory import WorkingMemoryTool


class WorkingMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_context_persists_until_checkpoint_clear(self) -> None:
        store = InMemoryWorkingMemoryStore()
        tool = WorkingMemoryTool(store)

        initial = await tool.invoke({"action": "read"})
        self.assertEqual(initial["working_context"], {})

        updated = await store.set_context("current_speaker", "William")
        self.assertEqual(updated.context["current_speaker"], "William")
        self.assertEqual((await store.read()).context["current_speaker"], "William")

        with self.assertRaisesRegex(ValueError, "managed by the Mind boundary"):
            await tool.invoke(
                {"action": "set_context", "key": "current_speaker", "value": "Michael"}
            )

        cleared = await store.clear()
        self.assertEqual(cleared.context, {})
        self.assertEqual((await store.read()).context, {})

    async def test_working_memory_accepts_evolving_context_keys(self) -> None:
        store = InMemoryWorkingMemoryStore()
        tool = WorkingMemoryTool(store)

        await store.set_context("current_speaker", "William")
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

    def test_explicit_speaker_identity_is_acquired_by_the_mind_boundary(self) -> None:
        self.assertEqual(_explicit_speaker_identity("I'm William."), "William")
        self.assertEqual(_explicit_speaker_identity("This is Michael."), "Michael")
        self.assertEqual(_explicit_speaker_identity("My name is Tara."), "Tara")
        self.assertIsNone(_explicit_speaker_identity("Nice to meet you."))

    def test_identity_dependent_first_person_question_requires_speaker(self) -> None:
        self.assertTrue(_requires_speaker_identity("What is my birthday?", "unknown"))
        self.assertFalse(_requires_speaker_identity("What is my birthday?", "William"))
        self.assertFalse(_requires_speaker_identity("I like birthday parties.", "unknown"))
        self.assertIn("name", IDENTITY_CLARIFICATION_RESPONSE.casefold())

    def test_known_speaker_cannot_receive_another_persons_first_person_knowledge(
        self,
    ) -> None:
        knowledge = "William's birthday is February 7."

        visible, recall_allowed = _scope_recalled_knowledge(
            "What is my birthday?",
            "Michael",
            knowledge,
        )

        self.assertNotIn("February 7", visible)
        self.assertFalse(recall_allowed)

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
