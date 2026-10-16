import unittest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from pymongo import DESCENDING

from aicognitive_mind.domain import JournalEntry, JournalKind
from aicognitive_mind.mongo_storage import MongoJournalStore


class MongoCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_scoped_lookup_returns_full_checkpoint_without_journal_scan(self):
        entry = JournalEntry(
            kind=JournalKind.CHECKPOINT,
            occurred_at=datetime(2026, 10, 16, tzinfo=UTC),
            experience={
                "checkpoint_type": "current_state_ledger",
                "state_ledger": {"revision": 7, "fields": {"active_topic": {"value": "restore"}}},
            },
        )
        collection = MagicMock()
        collection.find_one = AsyncMock(return_value=entry.model_dump(mode="python"))
        database = MagicMock()
        database.__getitem__.return_value = collection
        store = MongoJournalStore(database, "alpha")

        self.assertEqual(await store.latest_checkpoint("current_state_ledger"), [entry])
        collection.find_one.assert_awaited_once_with(
            {
                "mind_id": "alpha",
                "kind": "checkpoint",
                "experience.checkpoint_type": "current_state_ledger",
            },
            {"_id": 0, "mind_id": 0},
            sort=[("occurred_at", DESCENDING)],
        )
        collection.find.assert_not_called()
        collection.count_documents.assert_not_called()

    async def test_missing_checkpoint_returns_empty_list(self):
        collection = MagicMock()
        collection.find_one = AsyncMock(return_value=None)
        database = MagicMock()
        database.__getitem__.return_value = collection
        self.assertEqual(await MongoJournalStore(database, "beta").latest_checkpoint("missing"), [])


if __name__ == "__main__":
    unittest.main()
