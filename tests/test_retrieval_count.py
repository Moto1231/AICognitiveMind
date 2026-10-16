import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.commit import StagedStore
from aicognitive_mind.domain import (
    CognitiveActor,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
)
from aicognitive_mind.retrieval import count
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore
from aicognitive_mind.surreal_storage import SurrealJournalStore, SurrealRuntime


def journal_entries() -> list[JournalEntry]:
    return [
        JournalEntry(
            kind=JournalKind.CHECKPOINT,
            experience={"checkpoint_type": "current_state_ledger"},
        ),
        JournalEntry(
            kind=JournalKind.CHECKPOINT,
            experience={"checkpoint_type": "current_state_ledger_backup"},
        ),
        JournalEntry(kind=JournalKind.CHECKPOINT, experience={}),
        JournalEntry(kind=JournalKind.CHECKPOINT, experience={"checkpoint_type": None}),
        JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"checkpoint_type": "current_state_ledger"},
        ),
        JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"input": {"content": "current_state_ledger"}},
        ),
    ]


class RetrievalCountTests(unittest.IsolatedAsyncioTestCase):
    async def test_in_memory_excludes_only_exact_ledger_checkpoints_without_read(self) -> None:
        journal = InMemoryJournalStore()
        for entry in journal_entries():
            await journal.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)

        with patch.object(journal, "read", side_effect=AssertionError("full journal read")):
            self.assertEqual(await count(journal), 6)
            self.assertEqual(
                await count(journal, exclude_checkpoint_type="current_state_ledger"), 5
            )
            self.assertEqual(await count(journal, exclude_checkpoint_type="missing"), 6)

    async def test_staged_counts_include_only_pending_writes_for_their_table(self) -> None:
        journal = InMemoryJournalStore()
        memory = InMemoryMemoryStore()
        for entry in journal_entries():
            await journal.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
        operations = []
        staged_journal = StagedStore(journal, "journal", operations)
        staged_memory = StagedStore(memory, "memory", operations)
        await staged_journal.append(
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                experience={"checkpoint_type": "current_state_ledger"},
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await staged_journal.append(
            JournalEntry(kind=JournalKind.INTERACTION, experience={"input": {"content": "hello"}}),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        pending_memory = DurableMemory(memory_class=MemoryClass.SEMANTIC, content="pending")
        await staged_memory.remember(
            pending_memory, recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD
        )

        with (
            patch.object(journal, "read", side_effect=AssertionError("full journal read")),
            patch.object(memory, "read", side_effect=AssertionError("full memory read")),
        ):
            self.assertEqual(await count(staged_journal), 8)
            self.assertEqual(
                await count(staged_journal, exclude_checkpoint_type="current_state_ledger"), 6
            )
            self.assertEqual(await count(staged_memory), 1)
            self.assertEqual(await count(journal), 6)
            self.assertEqual(await count(memory), 0)

        replacement = pending_memory.model_copy(update={"content": "revised"})
        operations.append(("memory", "replace", pending_memory, replacement))
        self.assertEqual(await count(staged_memory), 1)

    async def test_mongo_count_uses_exact_exclusion_and_mind_scope(self) -> None:
        collection = SimpleNamespace(count_documents=AsyncMock(return_value=5))
        journal = SimpleNamespace(_collection=collection, mind_id="alpha")

        self.assertEqual(await count(journal, exclude_checkpoint_type="current_state_ledger"), 5)

        collection.count_documents.assert_awaited_once_with(
            {
                "mind_id": "alpha",
                "$nor": [
                    {"kind": "checkpoint", "experience.checkpoint_type": "current_state_ledger"}
                ],
            }
        )

    async def test_surreal_count_uses_one_scoped_count_without_fetching_rows(self) -> None:
        database = SimpleNamespace(query=AsyncMock(return_value=[{"total": 5}]))
        journal = SurrealJournalStore(database, "alpha")
        with patch.object(journal, "read", side_effect=AssertionError("full journal read")):
            self.assertEqual(
                await count(journal, exclude_checkpoint_type="current_state_ledger"), 5
            )

        database.query.assert_awaited_once()
        sql, variables = database.query.call_args.args
        self.assertIn("SELECT count() AS total FROM journal", sql)
        self.assertIn("mind_id = $mind_id", sql)
        self.assertIn("experience.checkpoint_type = NONE", sql)
        self.assertNotIn("SELECT *", sql)
        self.assertEqual(sql.count(";"), 1)
        self.assertEqual(
            variables,
            {
                "mind_id": "alpha",
                "checkpoint_kind": "checkpoint",
                "checkpoint_type": "current_state_ledger",
            },
        )


class SurrealRetrievalCountTests(unittest.IsolatedAsyncioTestCase):
    async def test_checkpoint_exclusion_keeps_missing_null_and_other_type_entries(self) -> None:
        runtime = SurrealRuntime("mem://", "count_test", "cognitive_mind")
        await runtime.initialize()
        try:
            alpha = SurrealJournalStore(runtime.database, "alpha")
            beta = SurrealJournalStore(runtime.database, "beta")
            for entry in journal_entries():
                await alpha.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
            await beta.append(
                JournalEntry(kind=JournalKind.INTERACTION, experience={}),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )

            self.assertEqual(await count(alpha), 6)
            self.assertEqual(await count(alpha, exclude_checkpoint_type="current_state_ledger"), 5)
            self.assertEqual(await count(beta, exclude_checkpoint_type="current_state_ledger"), 1)
            self.assertEqual(await count(alpha, exclude_checkpoint_type="missing"), 6)
            staged = StagedStore(alpha, "journal", [])
            await staged.append(
                JournalEntry(kind=JournalKind.INTERACTION, experience={}),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
            self.assertEqual(await count(staged, exclude_checkpoint_type="current_state_ledger"), 6)
        finally:
            await runtime.close()


if __name__ == "__main__":
    unittest.main()
