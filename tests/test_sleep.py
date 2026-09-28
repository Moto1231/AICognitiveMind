import unittest
from datetime import UTC, datetime, timedelta

from aicognitive_mind.domain import (
    CognitiveActor,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
)
from aicognitive_mind.sleep import SleepConsolidator
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore


class SleepConsolidatorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.journal = InMemoryJournalStore()
        self.memory = InMemoryMemoryStore()
        self.sleep = SleepConsolidator(journal=self.journal, memory=self.memory)

    async def test_sleep_consolidates_repeated_durable_association(self) -> None:
        for content in (
            "Axiom uses SurrealDB as the canonical cognitive store.",
            "Axiom tenancy isolates each mind in SurrealDB.",
        ):
            await self.memory.remember(
                DurableMemory(
                    memory_class=MemoryClass.SEMANTIC,
                    content=content,
                    associations=("Axiom", "SurrealDB"),
                    grounding=("established project evidence",),
                ),
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )

        report = await self.sleep.sleep(
            started_at=datetime(2026, 9, 28, 5, 0, tzinfo=UTC)
        )

        self.assertTrue(any(p.association == "surrealdb" for p in report.patterns))
        self.assertTrue(
            any("surrealdb" in content.casefold() for content in report.consolidated_memories)
        )
        memories = await self.memory.read()
        reflection = memories[-1]
        self.assertEqual(reflection.memory_class, MemoryClass.REFLECTIVE)
        self.assertIn("pattern recognition", reflection.associations)
        self.assertEqual(len(reflection.grounding), 2)

    async def test_sleep_does_not_promote_one_off_association(self) -> None:
        await self.memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="One isolated observation.",
                associations=("one-off",),
                grounding=("single evidence item",),
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        report = await self.sleep.sleep()

        self.assertFalse(report.patterns)
        self.assertFalse(report.consolidated_memories)
        self.assertEqual(len(await self.memory.read()), 1)

    async def test_sleep_records_recurring_journal_signal_without_promoting_it(self) -> None:
        base = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)
        for index in range(3):
            await self.journal.append(
                JournalEntry(
                    kind=JournalKind.INTERACTION,
                    occurred_at=base + timedelta(minutes=index),
                    experience={
                        "input": {"content": "Identity tracking needs continuity."},
                        "expression": {"content": "Continuity remains the focus."},
                    },
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )

        report = await self.sleep.sleep(started_at=base + timedelta(hours=4))

        self.assertIn("continuity", report.recurring_journal_signals)
        self.assertFalse(report.consolidated_memories)
        entries = await self.journal.read()
        checkpoint = entries[-1]
        self.assertEqual(checkpoint.kind, JournalKind.CHECKPOINT)
        self.assertEqual(checkpoint.experience["phase"], "sleep_consolidation")

    async def test_repeated_sleep_is_idempotent_for_pattern_memory(self) -> None:
        for content in ("First project fact.", "Second project fact."):
            await self.memory.remember(
                DurableMemory(
                    memory_class=MemoryClass.PROCEDURAL,
                    content=content,
                    associations=("shared-pattern",),
                    grounding=("evidence",),
                ),
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )

        first = await self.sleep.sleep()
        second = await self.sleep.sleep()

        self.assertEqual(len(first.consolidated_memories), 1)
        self.assertEqual(len(second.consolidated_memories), 0)


if __name__ == "__main__":
    unittest.main()
