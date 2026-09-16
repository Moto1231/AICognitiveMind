import json
import unittest

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
    MindIdentity,
)
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore


class MemoryTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_persisted_trace_does_not_embed_recalled_journal_history(self) -> None:
        journal = InMemoryJournalStore()
        await journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={
                    "input": {
                        "source": "human",
                        "content": "My birthday is February 7.",
                    },
                    "memory_steward": {
                        "recalled_context": {
                            "prior_experience": [
                                {"legacy_recursive_payload": "x" * 250_000}
                            ]
                        }
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "I will remember that.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="When is my birthday?",
            memory=InMemoryMemoryStore(),
            journal=journal,
        )

        await tool.invoke({"action": "recall", "focus": "birthday"})
        trace = await tool.complete()

        payload = json.dumps(trace.model_dump(mode="json"))
        self.assertEqual(trace.recalled_context.prior_experience_count, 1)
        self.assertIn("My birthday is February 7.", trace.recalled_context.summary)
        self.assertNotIn('"prior_experience":', payload)
        self.assertNotIn("legacy_recursive_payload", payload)
        self.assertLess(len(payload), 5_000)

    async def test_recall_scoring_ignores_nested_steward_trace_content(self) -> None:
        journal = InMemoryJournalStore()
        await journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={
                    "input": {"source": "human", "content": "We discussed gardening."},
                    "memory_steward": {
                        "recalled_context": {
                            "summary": "birthday birthday birthday",
                            "legacy_recursive_payload": "birthday " * 20_000,
                        }
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Tomatoes need good sunlight.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="When is my birthday?",
            memory=InMemoryMemoryStore(),
            journal=journal,
        )

        await tool.invoke({"action": "recall", "focus": "birthday"})
        trace = await tool.complete()

        self.assertEqual(trace.recalled_context.prior_experience_count, 0)
        self.assertEqual(
            trace.recalled_context.summary,
            "No relevant knowledge is available.",
        )


if __name__ == "__main__":
    unittest.main()
