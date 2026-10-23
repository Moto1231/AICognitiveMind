import os
import unittest
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.errors import ExecutionTimeout, OperationFailure

from aicognitive_mind.domain import DurableMemory, JournalEntry, JournalKind, MemoryClass
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.mongo_storage import (
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
    MongoRuntime,
)


class CandidateCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = [{"_id": uuid4().hex, **document} for document in documents]
        self.options: dict[str, Any] = {}

    def sort(self, field: str, direction: int) -> "CandidateCursor":
        self.options["sort"] = (field, direction)
        return self

    def limit(self, limit: int) -> "CandidateCursor":
        self.options["limit"] = limit
        return self

    def collation(self, collation: dict[str, Any]) -> "CandidateCursor":
        self.options["collation"] = collation
        return self

    def max_time_ms(self, milliseconds: int) -> "CandidateCursor":
        self.options["max_time_ms"] = milliseconds
        return self

    def __aiter__(self):
        async def rows():
            for document in self.documents[: self.options["limit"]]:
                yield document

        return rows()


class MongoCandidateTests(unittest.IsolatedAsyncioTestCase):
    def make_store(self, store_type, cursors, mind_id="alpha"):
        collection = MagicMock()
        collection.find.side_effect = cursors
        database = MagicMock()
        database.__getitem__.return_value = collection
        return store_type(database, mind_id), collection

    async def test_both_stores_return_full_scoped_records_from_one_text_query(self):
        entry = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"input": {"content": "archive"}, "new_field": {"proof": "retained"}},
        )
        memory = DurableMemory(memory_class=MemoryClass.SEMANTIC, content="archive")
        for store_type, value, date in (
            (MongoJournalStore, entry, "occurred_at"),
            (MongoMemoryStore, memory, "formed_at"),
        ):
            with self.subTest(store=store_type.__name__):
                cursor = CandidateCursor([value.model_dump(mode="python")])
                store, collection = self.make_store(store_type, [cursor])
                with patch.object(
                    store, "_portal_filter", side_effect=AssertionError("regex scan")
                ):
                    self.assertEqual(await store.query_candidates({"archive"}, 7), [value])
                collection.find.assert_called_once_with(
                    {"mind_id": "alpha", "$text": {"$search": "archive", "$language": "none"}},
                    {"mind_id": 0},
                )
                self.assertEqual(cursor.options["sort"], (date, DESCENDING))
                self.assertEqual(cursor.options["limit"], 7)
                self.assertEqual(cursor.options["max_time_ms"], 5000)
                self.assertEqual(cursor.options["collation"], {"locale": "simple"})
                collection.count_documents.assert_not_called()

    async def test_no_match_falls_back_to_bounded_scoped_history_without_count(self):
        memory = DurableMemory(memory_class=MemoryClass.SEMANTIC, content="most recent")
        cursors = [CandidateCursor([]), CandidateCursor([memory.model_dump(mode="python")])]
        store, collection = self.make_store(MongoMemoryStore, cursors)
        with patch.object(store, "query_page", side_effect=AssertionError("unnecessary count")):
            self.assertEqual(await store.query_candidates({"absent"}, 3), [memory])
        self.assertEqual(collection.find.call_args_list[1].args[0], {"mind_id": "alpha"})
        self.assertEqual([cursor.options["limit"] for cursor in cursors], [3, 3])
        collection.count_documents.assert_not_called()

    async def test_empty_tokens_and_empty_mind_id_never_drop_scope(self):
        cursor = CandidateCursor([])
        store, collection = self.make_store(MongoMemoryStore, [cursor], mind_id="")
        self.assertEqual(await store.query_candidates(set()), [])
        collection.find.assert_called_once_with({"mind_id": ""}, {"mind_id": 0})

    async def test_operator_punctuation_and_unicode_are_only_positive_word_terms(self):
        store, collection = self.make_store(
            MongoMemoryStore, [CandidateCursor([]), CandidateCursor([]), CandidateCursor([])]
        )
        await store.query_candidates({"-secret", '"two words"', "RENDER-api", "café_東京"})
        self.assertEqual(
            collection.find.call_args_list[0].args[0]["$text"],
            {"$search": "café secret two words 東京", "$language": "none"},
        )

    async def test_limit_and_query_size_are_bounded_and_zero_never_means_unlimited(self):
        store, collection = self.make_store(
            MongoJournalStore, [CandidateCursor([]), CandidateCursor([])]
        )
        self.assertEqual(await store.query_candidates({"hello"}, 0), [])
        self.assertEqual(await store.query_candidates({"hello"}, -1), [])
        collection.find.assert_not_called()
        await store.query_candidates({f"word{index}" for index in range(200)} | {"x" * 129}, 10000)
        words = collection.find.call_args_list[0].args[0]["$text"]["$search"].split()
        self.assertEqual(len(words), 64)
        self.assertTrue(all(len(word) <= 128 for word in words))
        self.assertEqual(collection.find.call_args_list[0].args[0]["mind_id"], "alpha")

    async def test_compound_matches_are_protected_without_requiring_them_for_plain_terms(self):
        old = datetime(2000, 1, 1, tzinfo=UTC)
        recent = datetime(2026, 10, 21, tzinfo=UTC)
        compound = {
            "_id": "compound",
            "memory_class": "semantic",
            "formed_at": old,
            "content": "Use gpt-6 for code",
        }
        general = {
            "_id": "general",
            "memory_class": "semantic",
            "formed_at": recent,
            "content": "Render is available",
        }
        store, collection = self.make_store(
            MongoMemoryStore,
            [
                CandidateCursor([general, compound]),
                CandidateCursor([compound]),
            ],
        )
        rows = await store.query_candidates({"gpt-6", "render"}, 2)
        self.assertEqual(
            [memory.content for memory in rows], [compound["content"], general["content"]]
        )
        self.assertEqual(collection.find.call_args_list[0].args[0]["$text"]["$search"], "render")
        self.assertEqual(collection.find.call_args_list[1].args[0]["$text"]["$search"], '"gpt-6"')

    async def test_compound_query_count_and_protected_page_sizes_are_bounded(self):
        memory = DurableMemory(memory_class=MemoryClass.SEMANTIC, content="general")
        cursors = [CandidateCursor([memory.model_dump(mode="python")])]
        cursors.extend(CandidateCursor([]) for _ in range(4))
        store, collection = self.make_store(MongoMemoryStore, cursors)
        await store.query_candidates({f"model-{number}" for number in range(10)}, 10000)
        self.assertEqual(collection.find.call_count, 5)
        self.assertEqual(cursors[0].options["limit"], 1000)
        self.assertEqual([cursor.options["limit"] for cursor in cursors[1:]], [64] * 4)
        self.assertEqual(
            [call.args[0]["$text"]["$search"] for call in collection.find.call_args_list[1:]],
            ['"model-0"', '"model-1"', '"model-2"', '"model-3"'],
        )
        self.assertTrue(
            all(call.args[0]["mind_id"] == "alpha" for call in collection.find.call_args_list)
        )

    async def test_timeout_and_missing_index_surface_without_recent_history_fallback(self):
        for error in (ExecutionTimeout("query timed out"), OperationFailure("text index required")):
            with self.subTest(error=type(error).__name__):
                store, collection = self.make_store(MongoJournalStore, [])
                collection.find.side_effect = error
                with self.assertRaises(type(error)):
                    await store.query_candidates({"archive"})
                collection.find.assert_called_once()

    def test_portal_literal_substring_filters_are_unchanged(self):
        for store_type in (MongoMemoryStore, MongoJournalStore):
            with self.subTest(store=store_type.__name__):
                store, _ = self.make_store(store_type, [])
                query = store._portal_filter(search="Axiom.foo")
                self.assertEqual(query["mind_id"], "alpha")
                self.assertNotIn("$text", query)
                clauses = query["$or"] if "$or" in query else query["$and"][0]["$or"]
                self.assertTrue(clauses)
                for clause in clauses:
                    self.assertEqual(
                        next(iter(clause.values())), {"$regex": r"Axiom\.foo", "$options": "i"}
                    )


class MongoRecallIndexTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_adds_native_indexes_without_rewriting_history(self):
        collections: dict[str, Any] = {}

        def collection(name):
            if name not in collections:
                collections[name] = MagicMock()
                collections[name].create_index = AsyncMock()
                collections[name].index_information = AsyncMock(return_value={})
            return collections[name]

        runtime = MongoRuntime("mongodb://localhost", "unit-test")
        await runtime.client.close()
        runtime.client = MagicMock()
        runtime.client.admin.command = AsyncMock()
        runtime.database = MagicMock()
        runtime.database.__getitem__.side_effect = collection
        runtime._migrate_legacy_scope = AsyncMock()

        await runtime.initialize()

        for table in ("journal", "memory"):
            collections[table].create_index.assert_any_await(
                [("mind_id", ASCENDING), ("$**", TEXT)],
                name="recall_text_v1",
                default_language="none",
                language_override="_recall_index_language",
                collation={"locale": "simple"},
            )
            collections[table].update_many.assert_not_called()
            collections[table].drop_index.assert_not_called()


@unittest.skipUnless(os.environ.get("MONGODB_TEST_URI"), "Requires disposable MongoDB")
class MongoCandidateIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.name = "axiom_retrieval_test_" + uuid4().hex
        self.runtime = MongoRuntime(os.environ["MONGODB_TEST_URI"], self.name)
        self.memory = MongoMemoryStore(self.runtime.database, "alpha")
        self.journal = MongoJournalStore(self.runtime.database, "alpha")
        old = datetime(2000, 1, 1, tzinfo=UTC)
        recent = datetime(2026, 10, 21, tzinfo=UTC)
        # Insert old-format records before index creation: no search shadow fields.
        await self.runtime.database["memory"].insert_many(
            [
                {
                    "mind_id": "alpha",
                    "memory_class": "semantic",
                    "formed_at": old,
                    "content": "Archival quasar launch; café MongoDB",
                    "artifacts": [
                        {"kind": "proof", "payload": {"future_field": "neutrino", "language": "C#"}}
                    ],
                },
                {
                    "mind_id": "beta",
                    "memory_class": "semantic",
                    "formed_at": recent,
                    "content": "Private quasar launch",
                },
                *[
                    {
                        "mind_id": "alpha",
                        "memory_class": "semantic",
                        "formed_at": recent + timedelta(seconds=index),
                        "content": f"Unrelated recent record {index}",
                    }
                    for index in range(300)
                ],
            ]
        )
        await self.runtime.database["journal"].insert_many(
            [
                {
                    "mind_id": "alpha",
                    "kind": "interaction",
                    "occurred_at": old,
                    "experience": {"input": {"content": "Quasar launch"}, "language": "Python"},
                },
                {
                    "mind_id": "beta",
                    "kind": "interaction",
                    "occurred_at": recent,
                    "experience": {"input": {"content": "Private quasar launch"}},
                },
                {
                    "mind_id": "alpha",
                    "kind": "interaction",
                    "occurred_at": recent,
                    "experience": {"input": {"content": "Unrelated recent journal"}},
                },
            ]
        )
        await self.runtime.initialize()

    async def asyncTearDown(self):
        assert self.name.startswith("axiom_retrieval_test_")
        await self.runtime.client.drop_database(self.name)
        await self.runtime.close()

    async def test_pending_diagnostics_preserve_full_scoped_rows_without_logging_payload(self):
        now = datetime.now(UTC).timestamp()
        older_text = "private-pending-older snowman \u2603"
        later_text = "private-pending-later"
        older_binary = b"private-binary-older"
        later_binary = b"private-binary-later\x00"
        older = {
            "kind": "body_request",
            "state": "pending",
            "created": now - 20,
            "deadline": None,
            "request_id": "private-request-older",
            "message": {"content": older_text, "attachments": [older_binary]},
            "claim": {
                "host_id": "private-host-marker",
                "claim_token": "private-claim-marker",
                "expires": now + 300,
            },
            "context": {"future_field": "private-extra-marker"},
        }
        later = {
            "kind": "body_request",
            "state": "pending",
            "created": now - 10,
            "deadline": now + 600,
            "request_id": "private-request-later",
            "message": {"content": later_text, "binary": later_binary},
            "claim": None,
            "extra_field": {"proof": ["private-proof-marker"]},
        }
        collection = self.runtime.database["runtime_records"]
        await collection.insert_many(
            [
                {"mind_id": "alpha", "key": "private-key-later", **later},
                {
                    "mind_id": "alpha", "key": "private-key-expired", **later,
                    "deadline": now - 60, "request_id": "private-expired-marker",
                },
                {"mind_id": "beta", "key": "private-key-beta", **older},
                {
                    "mind_id": "alpha", "key": "private-key-complete", **older,
                    "state": "complete", "request_id": "private-complete-marker",
                },
                {"mind_id": "alpha", "key": "private-key-older", **older},
            ]
        )
        records = RuntimeRecords(MongoMindStore(self.runtime.database, "alpha"))
        with (
            patch("aicognitive_mind.pending_diagnostics.timing.ENABLED", True),
            patch("aicognitive_mind.pending_diagnostics.timing.emit") as emit,
        ):
            rows = await records.pending()

        self.assertEqual(rows, [older, later])
        emit.assert_called_once()
        template, *values = emit.call_args.args
        message = template % tuple(values)
        fields = dict(field.split("=", 1) for field in message.split() if "=" in field)
        self.assertEqual(fields["backend"], "mongo")
        self.assertEqual(fields["client"], "AsyncMongoClient")
        self.assertEqual(fields["outcome"], "ok")
        self.assertEqual(fields["rows"], "2")
        older_chars = sum(map(len, (
            "body_request", "pending", older["request_id"], older_text,
            "private-host-marker", "private-claim-marker", "private-extra-marker",
        )))
        later_chars = sum(map(len, (
            "body_request", "pending", later["request_id"], later_text,
            "private-proof-marker",
        )))
        self.assertEqual(int(fields["string_chars_total"]), older_chars + later_chars)
        self.assertEqual(int(fields["string_chars_max"]), max(older_chars, later_chars))
        self.assertEqual(
            int(fields["binary_bytes_total"]), len(older_binary) + len(later_binary)
        )
        self.assertEqual(
            int(fields["binary_bytes_max"]), max(len(older_binary), len(later_binary))
        )
        self.assertEqual(fields["sizes_complete"], "True")
        for phase in (
            "wall_s", "cursor_construct_s", "first_next_s", "remaining_next_s",
            "materialize_s", "size_s",
        ):
            self.assertGreaterEqual(float(fields[phase]), 0)
        for private_value in (
            older_text, later_text, "private-binary", "private-request", "private-host",
            "private-claim", "private-extra", "private-proof", "private-key", "alpha",
            "beta", "private-expired", "private-complete",
        ):
            self.assertNotIn(private_value, message)

    async def test_old_documents_across_full_history_and_dynamic_fields_are_indexed(self):
        self.assertEqual(
            [memory.content for memory in await self.memory.query_candidates({"quasar"}, 1)],
            ["Archival quasar launch; café MongoDB"],
        )
        self.assertEqual(
            [
                entry.experience["input"]["content"]
                for entry in await self.journal.query_candidates({"quasar"})
            ],
            ["Quasar launch"],
        )
        self.assertEqual(len(await self.memory.query_candidates({"neutrino"})), 1)
        self.assertEqual(len(await self.memory.query_candidates({"CAFÉ"})), 1)
        # Repeated initialization must retain a single compatible native index.
        await self.runtime.initialize()
        info = await self.runtime.database["memory"].index_information()
        self.assertEqual(info["recall_text_v1"]["weights"], {"$**": 1})
        explained = (
            await self.runtime.database["memory"]
            .find({"mind_id": "alpha", "$text": {"$search": "quasar", "$language": "none"}})
            .explain()
        )
        self.assertIn("TEXT_MATCH", str(explained["queryPlanner"]["winningPlan"]))

    async def test_incompatible_existing_text_index_is_preserved_and_startup_fails(self):
        collection = self.runtime.database["journal"]
        await collection.drop_index("recall_text_v1")
        await collection.create_index(
            [("experience.input.content", TEXT)],
            name="operator_search",
            default_language="none",
            language_override="_recall_index_language",
        )
        before = await collection.count_documents({})
        with self.assertRaises(OperationFailure):
            await self.runtime.initialize()
        info = await collection.index_information()
        self.assertIn("operator_search", info)
        self.assertNotIn("recall_text_v1", info)
        self.assertEqual(await collection.count_documents({}), before)

    async def test_empty_and_no_match_queries_use_only_own_recent_history(self):
        for tokens in (set(), {"missingword"}):
            self.assertEqual(
                [memory.content for memory in await self.memory.query_candidates(tokens, 2)],
                ["Unrelated recent record 299", "Unrelated recent record 298"],
            )
        beta = MongoMemoryStore(self.runtime.database, "beta")
        self.assertEqual(
            [memory.content for memory in await beta.query_candidates({"quasar"})],
            ["Private quasar launch"],
        )

    async def test_portal_substrings_still_match_old_records(self):
        memories, total = await self.memory.query_page(
            offset=0, limit=10, newest_first=True, search="asar"
        )
        self.assertEqual(total, 1)
        self.assertEqual(memories[0].content, "Archival quasar launch; café MongoDB")
        entries, total = await self.journal.query_page(
            offset=0, limit=10, newest_first=True, search="asar"
        )
        self.assertEqual(total, 1)
        self.assertEqual(entries[0].experience["input"]["content"], "Quasar launch")

    async def test_compound_archive_is_not_crowded_out_by_newer_partial_terms(self):
        await self.runtime.database["memory"].insert_one(
            {
                "mind_id": "alpha",
                "memory_class": "semantic",
                "formed_at": datetime(1999, 1, 1, tzinfo=UTC),
                "content": "Use gpt-6 for code",
            }
        )
        await self.runtime.database["memory"].insert_many(
            [
                {
                    "mind_id": "alpha",
                    "memory_class": "semantic",
                    "formed_at": datetime(2026, 10, 22, tzinfo=UTC) + timedelta(seconds=index),
                    "content": f"gpt generic usage {index}",
                }
                for index in range(300)
            ]
        )
        rows = await self.memory.query_candidates({"gpt-6"})
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].content, "Use gpt-6 for code")
        # A separate ordinary term still supplies candidates even if they lack
        # the compound phrase; it must not become a phrase-required AND query.
        rows = await self.memory.query_candidates({"gpt-6", "quasar"})
        self.assertEqual(rows[0].content, "Use gpt-6 for code")
        self.assertTrue(
            any(memory.content == "Archival quasar launch; café MongoDB" for memory in rows)
        )


if __name__ == "__main__":
    unittest.main()
