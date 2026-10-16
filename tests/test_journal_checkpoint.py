import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.domain import CognitiveActor, JournalEntry, JournalKind
from aicognitive_mind.storage import InMemoryJournalStore
from aicognitive_mind.surreal_storage import SurrealJournalStore


class InMemoryJournalCheckpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_checkpoint_uses_last_append_when_event_times_tie(self) -> None:
        store = InMemoryJournalStore()
        timestamp = datetime(2026, 10, 16, tzinfo=UTC)
        for revision in (1, 2):
            await store.append(
                JournalEntry(
                    kind=JournalKind.CHECKPOINT,
                    occurred_at=timestamp,
                    experience={
                        "checkpoint_type": "current_state_ledger",
                        "state_ledger": {"revision": revision},
                    },
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )

        latest = await store.latest_checkpoint("current_state_ledger")

        self.assertEqual(latest[0].experience["state_ledger"]["revision"], 2)

    async def test_latest_checkpoint_matches_exact_kind_and_type_and_uses_event_time(self) -> None:
        store = InMemoryJournalStore()
        base = datetime(2026, 10, 16, tzinfo=UTC)
        expected = JournalEntry(
            kind=JournalKind.CHECKPOINT,
            occurred_at=base + timedelta(minutes=2),
            experience={
                "checkpoint_type": "current_state_ledger",
                "state_ledger": {"revision": 2, "answers": {"project": "restoration"}},
            },
        )
        entries = [
            expected,
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                occurred_at=base,
                experience={"checkpoint_type": "current_state_ledger"},
            ),
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                occurred_at=base + timedelta(minutes=3),
                experience={"checkpoint_type": "current_state_ledger_backup"},
            ),
            JournalEntry(
                kind=JournalKind.INTERACTION,
                occurred_at=base + timedelta(minutes=4),
                experience={"checkpoint_type": "current_state_ledger"},
            ),
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                occurred_at=base + timedelta(minutes=5),
                experience={"description": "current_state_ledger"},
            ),
        ]
        for entry in entries:
            await store.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)

        with (
            patch.object(store, "read", side_effect=AssertionError("unbounded read")),
            patch.object(store, "query_page", side_effect=AssertionError("counting query")),
        ):
            result = await store.latest_checkpoint("current_state_ledger")

        self.assertEqual(result, [expected])
        result[0].experience["state_ledger"]["answers"]["project"] = "changed"
        self.assertEqual(await store.latest_checkpoint("current_state_ledger"), [expected])
        self.assertEqual(await store.latest_checkpoint("missing"), [])

    async def test_checkpoint_type_is_searchable_without_ledger_payload(self) -> None:
        store = InMemoryJournalStore()
        checkpoint = JournalEntry(
            kind=JournalKind.CHECKPOINT,
            experience={"checkpoint_type": "current_state_ledger"},
        )
        await store.append(checkpoint, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)

        page, total = await store.query_page(
            offset=0,
            limit=1,
            newest_first=True,
            kind=JournalKind.CHECKPOINT.value,
            search="CURRENT_STATE_LEDGER",
        )

        self.assertEqual((page, total), ([checkpoint], 1))


class SurrealJournalCheckpointQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_latest_checkpoint_uses_one_bounded_exact_scoped_query(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.CHECKPOINT,
            experience={"checkpoint_type": "current_state_ledger", "state_ledger": {"revision": 7}},
        )
        database = SimpleNamespace(
            query=AsyncMock(
                return_value=[
                    {
                        "id": "journal:checkpoint",
                        "mind_id": "alpha",
                        **entry.model_dump(mode="json"),
                    }
                ]
            )
        )
        store = SurrealJournalStore(database, "alpha")
        with (
            patch.object(store, "read", side_effect=AssertionError("unbounded read")),
            patch.object(store, "query_page", side_effect=AssertionError("counting query")),
        ):
            result = await store.latest_checkpoint("current_state_ledger")

        self.assertEqual(result, [entry])
        database.query.assert_awaited_once()
        sql, variables = database.query.call_args.args
        self.assertIn("mind_id = $mind_id", sql)
        self.assertIn("kind = $kind", sql)
        self.assertIn("experience.checkpoint_type = $checkpoint_type", sql)
        self.assertIn("ORDER BY occurred_at DESC", sql)
        self.assertIn("LIMIT 1", sql)
        self.assertNotIn("count(", sql.lower())
        self.assertEqual(sql.count(";"), 1)
        self.assertEqual(
            variables,
            {"mind_id": "alpha", "kind": "checkpoint", "checkpoint_type": "current_state_ledger"},
        )

    async def test_latest_checkpoint_returns_empty_when_none_exists(self) -> None:
        database = SimpleNamespace(query=AsyncMock(return_value=[]))
        self.assertEqual(
            await SurrealJournalStore(database, "beta").latest_checkpoint("current_state_ledger"),
            [],
        )


if __name__ == "__main__":
    unittest.main()
