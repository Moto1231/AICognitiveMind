"""Observe one existing queue read without inspecting or exposing its contents."""

import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from aicognitive_mind import pending_diagnostics
from aicognitive_mind.host_runtime import RuntimeRecords


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class MongoClientFixture:
    def __repr__(self):
        raise AssertionError("database client must never be represented")


class TimedRow(dict):
    def __init__(self, clock, cost, **values):
        super().__init__(values)
        self.clock, self.cost = clock, cost

    def items(self):
        self.clock.advance(self.cost)
        return super().items()


class Cursor:
    def __init__(self, clock, rows, *, failure=None):
        self.clock, self.rows, self.failure = clock, rows, failure
        self.options = []
        self.iterations = self.advances = self.index = 0

    def sort(self, *args):
        self.options.append(("sort", args))
        self.clock.advance(3)
        return self

    def limit(self, *args):
        self.options.append(("limit", args))
        self.clock.advance(5)
        return self

    def __aiter__(self):
        self.iterations += 1
        return self

    async def __anext__(self):
        self.advances += 1
        if self.index < len(self.rows):
            self.clock.advance(7 if self.index == 0 else 11)
            row = self.rows[self.index]
            self.index += 1
            return row
        self.clock.advance(13)
        if self.failure is not None:
            raise self.failure
        raise StopAsyncIteration


class Collection:
    def __init__(self, clock, cursor):
        self.clock, self.cursor, self.calls = clock, cursor, []

    def find(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        self.clock.advance(2)
        return self.cursor


class MongoDatabase:
    def __init__(self, collection):
        self.client = MongoClientFixture()
        self.collection, self.collections = collection, []

    def __getitem__(self, name):
        self.collections.append(name)
        return self.collection

    def __repr__(self):
        raise AssertionError("database URI must never be represented")


class PendingDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.clock = Clock()
        self.enterContext(patch("aicognitive_mind.timing.ENABLED", True))
        self.enterContext(patch("aicognitive_mind.timing.time.perf_counter", self.clock))
        self.enterContext(patch("aicognitive_mind.host_runtime.time.time", return_value=1000.0))

    def mongo(self, rows, *, failure=None):
        cursor = Cursor(self.clock, rows, failure=failure)
        collection = Collection(self.clock, cursor)
        database = MongoDatabase(collection)
        mind = SimpleNamespace(
            mind_id="private-mind-filter", _collection=SimpleNamespace(database=database),
        )
        return RuntimeRecords(mind), database, collection, cursor

    def fields(self, logs):
        self.assertEqual(len(logs.records), 1)
        message = logs.records[0].getMessage()
        self.assertTrue(message.startswith("timing runtime_records.pending "))
        return dict(item.split("=", 1) for item in message.split() if "=" in item)

    def assert_seconds(self, fields, **expected):
        for name, value in expected.items():
            self.assertAlmostEqual(float(fields.get(name, "0")), value, places=3, msg=name)

    async def test_mongo_one_cursor_keeps_query_results_and_attributes_each_phase(self):
        rows = [
            TimedRow(self.clock, 3, _id="private-document-id", mind_id="private-mind-id",
                     key="private-key", request_id="private-request-id", claim="private-claim-token",
                     message="é😀", nested={"note": "abcdefg", "blob": b"abc"},
                     blobs=(bytearray(b"de"), memoryview(b"fghi"))),
            TimedRow(self.clock, 5, message="second", blob=b"12345"),
        ]
        records, database, collection, cursor = self.mongo(rows)
        with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
            result = await records.pending()
        expected = [
            {key: value for key, value in dict.items(row) if key not in {"_id", "mind_id", "key"}}
            for row in rows
        ]
        self.assertEqual(result, expected)
        self.assertIs(result[0]["nested"], rows[0]["nested"])
        self.assertEqual(database.collections, ["runtime_records"])
        self.assertEqual(collection.calls, [(({
            "mind_id": "private-mind-filter", "kind": "body_request", "state": "pending",
            "$or": [{"deadline": {"$gt": 1000.0}}, {"deadline": {"$exists": False}},
                    {"deadline": None}],
        },), {})])
        self.assertEqual(cursor.options, [("sort", ("created", 1)), ("limit", (512,))])
        self.assertEqual((cursor.iterations, cursor.advances), (1, 3))
        fields = self.fields(logs)
        self.assertEqual(fields["backend"], "mongo")
        self.assertEqual(fields["client"], "MongoClientFixture")
        self.assertEqual(fields["outcome"], "ok")
        self.assertEqual(fields["rows"], "2")
        self.assert_seconds(fields, wall_s=49, cursor_construct_s=10, first_next_s=7,
                            remaining_next_s=24, materialize_s=8, size_s=0)
        first_chars = 2 + 7 + len("private-request-id") + len("private-claim-token")
        self.assertEqual(int(fields["string_chars_total"]), first_chars + 6)
        self.assertEqual(int(fields["string_chars_max"]), first_chars)
        self.assertEqual(fields["binary_bytes_total"], "14")
        self.assertEqual(fields["binary_bytes_max"], "9")
        self.assertEqual(fields["sizes_complete"], "True")
        output = "\n".join(logs.output)
        for secret in ("private-document-id", "private-mind-id", "private-key", "private-mind-filter",
                       "private-request-id", "private-claim-token", "é😀", "abcdefg", "second"):
            self.assertNotIn(secret, output)

    async def test_empty_cursor_attributes_initial_exhaustion_without_extra_advance(self):
        records, _, _, cursor = self.mongo([])
        with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
            self.assertEqual(await records.pending(), [])
        fields = self.fields(logs)
        self.assert_seconds(fields, wall_s=23, cursor_construct_s=10, first_next_s=13,
                            remaining_next_s=0, materialize_s=0)
        self.assertEqual((cursor.iterations, cursor.advances), (1, 1))
        self.assertEqual(fields["rows"], "0")
        self.assertEqual(fields["sizes_complete"], "True")

    async def test_size_walk_time_is_separate_from_query_wall_time(self):
        records, _, _, _ = self.mongo([])
        measure_sizes = pending_diagnostics._payload_sizes

        def sizes(rows):
            self.clock.advance(5)
            return measure_sizes(rows)

        with patch("aicognitive_mind.pending_diagnostics._payload_sizes", side_effect=sizes):
            with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
                self.assertEqual(await records.pending(), [])
        self.assert_seconds(self.fields(logs), wall_s=23, size_s=5)

    async def test_query_error_and_cancellation_keep_original_exception_and_partial_rows(self):
        for failure, outcome in ((ValueError("private-query-error"), "error"),
                                 (asyncio.CancelledError("private-cancel-detail"), "cancelled")):
            with self.subTest(outcome=outcome):
                records, _, _, cursor = self.mongo(
                    [TimedRow(self.clock, 3, message="private-partial-row")], failure=failure,
                )
                with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
                    with self.assertRaises(type(failure)) as caught:
                        await records.pending()
                self.assertIs(caught.exception, failure)
                fields = self.fields(logs)
                self.assertEqual(fields["outcome"], outcome)
                self.assertEqual(fields["rows"], "1")
                self.assert_seconds(fields, wall_s=33, cursor_construct_s=10, first_next_s=7,
                                    remaining_next_s=13, materialize_s=3)
                self.assertEqual((cursor.iterations, cursor.advances), (1, 2))
                for private in ("private-query-error", "private-cancel-detail", "private-partial-row"):
                    self.assertNotIn(private, "\n".join(logs.output))

    async def test_diagnostic_helper_logger_and_clock_failures_do_not_change_results(self):
        for target in ("aicognitive_mind.pending_diagnostics._payload_sizes",
                       "aicognitive_mind.timing.logger.info",
                       "aicognitive_mind.timing.time.perf_counter"):
            with self.subTest(target=target):
                records, _, _, cursor = self.mongo([{"message": "unchanged"}])
                with patch(target, side_effect=RuntimeError("private-diagnostic-failure")):
                    self.assertEqual(await records.pending(), [{"message": "unchanged"}])
                self.assertEqual((cursor.iterations, cursor.advances), (1, 2))

    async def test_failed_mark_clock_does_not_interrupt_query(self):
        records, _, _, cursor = self.mongo([{"message": "unchanged"}])
        with patch("aicognitive_mind.timing.time.perf_counter",
                   side_effect=[0.0, RuntimeError("private-clock-failure")]):
            self.assertEqual(await records.pending(), [{"message": "unchanged"}])
        self.assertEqual((cursor.iterations, cursor.advances), (1, 2))

    async def test_unavailable_client_metadata_does_not_interrupt_query(self):
        records, database, _, cursor = self.mongo([{"message": "unchanged"}])
        del database.client
        self.assertEqual(await records.pending(), [{"message": "unchanged"}])
        self.assertEqual((cursor.iterations, cursor.advances), (1, 2))

    async def test_diagnostic_failure_cannot_mask_query_error_or_cancellation(self):
        for failure in (ValueError("query-failure"), asyncio.CancelledError("cancelled")):
            for target in ("aicognitive_mind.pending_diagnostics._payload_sizes",
                           "aicognitive_mind.timing.logger.info",
                           "aicognitive_mind.timing.time.perf_counter"):
                with self.subTest(failure=type(failure).__name__, diagnostic=target):
                    records, _, _, _ = self.mongo([], failure=failure)
                    with patch(target, side_effect=RuntimeError("diagnostic-failure")):
                        with self.assertRaises(type(failure)) as caught:
                            await records.pending()
                    self.assertIs(caught.exception, failure)

    async def test_disabled_diagnostics_skip_payload_walk_and_log(self):
        records, _, _, cursor = self.mongo([{"message": "unchanged"}])
        with patch("aicognitive_mind.timing.ENABLED", False), patch(
            "aicognitive_mind.pending_diagnostics._payload_sizes",
        ) as walk, patch("aicognitive_mind.timing.emit") as emit:
            self.assertEqual(await records.pending(), [{"message": "unchanged"}])
        walk.assert_not_called()
        emit.assert_not_called()
        self.assertEqual((cursor.iterations, cursor.advances), (1, 2))

    async def test_surreal_preserves_one_query_and_original_result(self):
        expected = [{"message": "private-surreal-payload"}]
        clock = self.clock

        class SurrealDatabase:
            def __init__(self):
                self.calls = []

            async def query(self, *args):
                self.calls.append(args)
                clock.advance(23)
                return expected

        database = SurrealDatabase()
        records = RuntimeRecords(SimpleNamespace(mind_id="private-selector", _database=database))
        with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
            result = await records.pending()
        self.assertIs(result, expected)
        self.assertEqual(database.calls, [(
            "SELECT * OMIT id, mind_id, key FROM runtime_records "
            "WHERE mind_id = $mind_id AND kind = 'body_request' "
            "AND state = 'pending' AND (deadline IS NONE OR deadline IS NULL OR deadline > $now) "
            "ORDER BY created LIMIT 512;", {"now": 1000.0, "mind_id": "private-selector"},
        )])
        fields = self.fields(logs)
        self.assertEqual((fields["backend"], fields["client"]), ("surreal", "SurrealDatabase"))
        self.assert_seconds(fields, wall_s=23, query_s=23)
        self.assertNotIn("private-selector", "\n".join(logs.output))
        self.assertNotIn("private-surreal-payload", "\n".join(logs.output))

    async def test_memory_preserves_filter_order_limit_and_deep_copy(self):
        mind = SimpleNamespace(mind_id="memory-fixture")
        mind._runtime_records = {
            str(index): {"kind": "body_request", "state": "pending", "created": index,
                         "deadline": None, "nested": {"value": index}}
            for index in range(512, -1, -1)
        }
        mind._runtime_records.update({
            "expired": {"kind": "body_request", "state": "pending", "created": -1, "deadline": 999},
            "completed": {"kind": "body_request", "state": "complete", "created": -2},
            "other-kind": {"kind": "other", "state": "pending", "created": -3},
        })
        records = RuntimeRecords(mind)
        with self.assertLogs("aicognitive_mind.timing", level="INFO") as logs:
            result = await records.pending()
        self.assertEqual(len(result), 512)
        self.assertEqual([row["created"] for row in result], list(range(512)))
        result[0]["nested"]["value"] = "changed-result"
        self.assertEqual(mind._runtime_records["0"]["nested"]["value"], 0)
        fields = self.fields(logs)
        self.assertEqual(fields["backend"], "memory")
        self.assertEqual(fields["rows"], "512")


class PayloadSizeTests(unittest.TestCase):
    def test_decoded_character_binary_and_per_row_totals_without_serializing(self):
        class StringWithoutEncoding(str):
            def encode(self, *args, **kwargs):
                raise AssertionError("UTF-8 copy is forbidden")

            def __str__(self):
                raise AssertionError("payload representation is forbidden")

        rows = [
            {"private-key-does-not-count": [StringWithoutEncoding("é😀"), "abcdefg"],
             "binary": (b"abc", bytearray(b"de"), memoryview(b"fghi"))},
            {"text": "second", "bytes": b"12345", "scalars": [1, False, None, 0.5]},
        ]
        with patch("json.dumps", side_effect=AssertionError("JSON copy is forbidden")), patch(
            "bson.BSON.encode", side_effect=AssertionError("BSON copy is forbidden"),
        ):
            self.assertEqual(pending_diagnostics._payload_sizes(rows), {
                "string_chars_total": 15, "string_chars_max": 9,
                "binary_bytes_total": 14, "binary_bytes_max": 9, "sizes_complete": True,
            })
            self.assertEqual(pending_diagnostics._payload_sizes([{
                "large-text": StringWithoutEncoding("é" * 200_000),
                "large-binary": b"x" * 200_000,
            }]), {
                "string_chars_total": 200_000, "string_chars_max": 200_000,
                "binary_bytes_total": 200_000, "binary_bytes_max": 200_000,
                "sizes_complete": True,
            })

    def test_cycle_depth_node_and_unknown_value_guards_mark_incomplete(self):
        cycle = []
        cycle.append(cycle)
        deep = "private-deep-payload"
        for _ in range(20):
            deep = [deep]
        wide_at_depth = [0] * 65_536
        for _ in range(15):
            wide_at_depth = [wide_at_depth]

        class Opaque:
            def __repr__(self):
                raise AssertionError("unknown values must not be represented")

        for label, payload in (("cycle", cycle), ("depth", deep),
                               ("wide-depth", wide_at_depth), ("nodes", [0] * 65_536),
                               ("unknown", Opaque())):
            with self.subTest(guard=label):
                result = pending_diagnostics._payload_sizes([{"payload": payload}])
                self.assertFalse(result["sizes_complete"])
                self.assertEqual(result["string_chars_total"], 0)
                self.assertEqual(result["binary_bytes_total"], 0)


if __name__ == "__main__":
    unittest.main()
