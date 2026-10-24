"""Content-free probe diagnostics; all database behavior here is local/synthetic."""

import copy
import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

from pydantic import BaseModel, ValidationError as ModelValidationError
from surrealdb import RecordID
from surrealdb.errors import NotFoundError, ServerError, ValidationError as SdkValidationError


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "startup_trace_local_fixtures", ROOT / "tests" / "test_surreal_startup_write.py",
)
fixtures = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fixtures)
command = fixtures.command
PRIVATE = fixtures.PRIVATE


def missing_table():
    return NotFoundError(
        "NotFound", PRIVATE, code=-32000,
        details={"kind": "Table", "details": {"name": PRIVATE}},
    )


class ForwardingDatabase:
    def __init__(self):
        self.calls = []
        self.result = {"private-result": PRIVATE}
        self.failure = None

    async def _call(self, name, *args):
        self.calls.append((name, *args))
        if self.failure is not None:
            raise self.failure
        return self.result

    async def query(self, sql, variables=None):
        return await self._call("query", sql, variables)

    async def query_raw(self, sql, variables=None):
        return await self._call("query_raw", sql, variables)

    async def select(self, record):
        return await self._call("select", record)

    async def create(self, record, data):
        return await self._call("create", record, data)


class StrictMissingTableDatabase(fixtures.MetadataDatabase):
    """Inject missing-table failures after bootstrap, as if a table disappeared.

    This deliberately forced fault tests trace preservation; normal fresh-start
    3.x bootstrap success is covered separately by the schema/runtime tests.
    """

    async def query(self, sql, variables=None):
        if sql.startswith("SELECT * FROM mind ") or sql.startswith("DELETE FROM "):
            self.calls.append(("query", sql, variables))
            raise missing_table()
        return await super().query(sql)


class CleanupFailureDatabase(fixtures.MetadataDatabase):
    def __init__(self, failure):
        super().__init__()
        self.failure = failure

    async def query(self, sql, variables=None):
        if sql.startswith("DELETE FROM "):
            self.calls.append(("query", sql, variables))
            raise self.failure
        return await super().query(sql)


class ProbeDatabaseTraceTests(unittest.IsolatedAsyncioTestCase):
    async def test_proxy_forwards_original_arguments_results_and_call_count(self):
        db = ForwardingDatabase()
        proxy = command.ProbeDatabase(db)
        variables = {"mind_id": "axiom", "private": PRIVATE}
        sql = "SELECT * FROM mind WHERE mind_id = $mind_id LIMIT 1;"
        self.assertIs(await proxy.query(sql, variables), db.result)
        record = RecordID("commit_state", PRIVATE)
        self.assertIs(await proxy.select(record), db.result)
        data = {"payload": PRIVATE}
        self.assertIs(await proxy.create("memory", data), db.result)
        self.assertEqual(db.calls, [
            ("query", sql, variables), ("select", record), ("create", "memory", data),
        ])
        self.assertEqual(proxy.last_successful_operation, "create_memory")
        self.assertIsNone(proxy.first_failure)

    async def test_original_error_survives_a_later_cleanup_error(self):
        db = ForwardingDatabase()
        proxy = command.ProbeDatabase(db)
        first = missing_table()
        db.failure = first
        with self.assertRaises(NotFoundError) as raised:
            await proxy.query(
                "SELECT * FROM mind WHERE mind_id = $mind_id LIMIT 1;",
                {"mind_id": "axiom"},
            )
        self.assertIs(raised.exception, first)
        original = copy.deepcopy(proxy.first_failure)
        with self.assertRaises(NotFoundError):
            await proxy.query(
                "DELETE FROM mind WHERE mind_id = $mind_id;",
                {"mind_id": "__tenancy_probe_" + PRIVATE},
            )
        self.assertEqual(proxy.first_failure, original)
        self.assertEqual(proxy.first_failure["operation"], "read_primary_mind")
        self.assertEqual(proxy.cleanup_failure["operation"], "cleanup_mind")
        serialized = json.dumps([proxy.first_failure, proxy.cleanup_failure])
        self.assertIn("NotFound", serialized)
        self.assertIn("Table", serialized)
        self.assertIn("-32000", serialized)
        self.assertNotIn(PRIVATE, serialized)
        self.assertEqual(len(db.calls), 2)

    async def test_raw_transaction_error_is_observed_without_changing_response(self):
        db = ForwardingDatabase()
        db.result = {"result": [
            {"status": "OK", "result": None},
            {"status": "ERR", "result": {
                "kind": "NotFound", "code": -32000, "message": PRIVATE,
                "details": {"kind": "Table", "details": {"name": PRIVATE}},
            }},
        ]}
        proxy = command.ProbeDatabase(db)
        sql = "BEGIN TRANSACTION; CREATE ONLY $record0 CONTENT $after0; COMMIT TRANSACTION;"
        parameters = {"mind_id": "__tenancy_probe_" + PRIVATE, "after0": {"private": PRIVATE}}
        self.assertIs(await proxy.query_raw(sql, parameters), db.result)
        self.assertEqual(db.calls, [("query_raw", sql, parameters)])
        self.assertEqual(proxy.first_failure["operation"], "initialize_probe_mind")
        self.assertEqual(proxy.first_failure["statement_index"], 1)
        self.assertNotIn(PRIVATE, json.dumps(proxy.first_failure))

    async def test_unknown_operation_and_exception_details_are_not_exposed(self):
        db = ForwardingDatabase()
        db.failure = RuntimeError(PRIVATE)
        proxy = command.ProbeDatabase(db)
        with self.assertRaises(RuntimeError):
            await proxy.query(PRIVATE, {"mind_id": PRIVATE, "password": PRIVATE})
        serialized = json.dumps(proxy.first_failure)
        self.assertNotIn(PRIVATE, serialized)
        self.assertNotIn("password", serialized)
        self.assertIsNotNone(proxy.first_failure)

    async def test_run_preserves_first_missing_read_when_cleanup_also_fails(self):
        db = StrictMissingTableDatabase()
        report = await command.run_check(fixtures.configured(), database_factory=lambda _uri: db)
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["stage"], "tenancy_probe")
        self.assertTrue(report["write_attempted"])
        self.assertEqual(report["cleanup"], "empty")
        self.assertTrue(all(count == 0 for count in report["after_counts"].values()))
        trace = report["probe_diagnostics"]
        self.assertEqual(trace["first_failure"]["operation"], "read_primary_mind")
        self.assertEqual(trace["cleanup_failure"]["operation"], "cleanup_mind")
        self.assertTrue(db.closed)
        self.assertNotIn(PRIVATE, json.dumps(report))

    async def test_cleanup_failure_retains_prior_model_validation_category(self):
        class Payload(BaseModel):
            count: int

        db = CleanupFailureDatabase(missing_table())

        async def model_then_cleanup(storage):
            try:
                Payload.model_validate({"count": PRIVATE})
            finally:
                await storage.mind._database.query(
                    "DELETE FROM mind WHERE mind_id = $mind_id;",
                    {"mind_id": "__tenancy_probe_" + PRIVATE},
                )

        probe = AsyncMock(side_effect=model_then_cleanup)
        report = await command.run_check(
            fixtures.configured(), database_factory=lambda _uri: db, probe=probe,
        )
        self.assertEqual(report["status"], "stopped")
        self.assertEqual(report["cleanup"], "empty")
        self.assertEqual(report["exception"]["exception_category"], "database_server")
        self.assertEqual(report["prior_exception"], {"exception_category": "model_validation"})
        # No SDK call failed until cleanup; the earlier Python validation is
        # represented separately rather than mislabeled as an SDK operation.
        self.assertEqual(report["probe_diagnostics"]["first_failure"]["operation"], "cleanup_mind")
        probe.assert_awaited_once()
        self.assertEqual(sum(call[0] == "signin" for call in db.calls), 1)
        self.assertTrue(db.closed)
        self.assertNotIn(PRIVATE, json.dumps(report))

    async def test_private_unknown_context_is_classified_without_details_or_retry(self):
        class PrivateContextError(Exception):
            pass

        db = CleanupFailureDatabase(RuntimeError(PRIVATE))

        async def unknown_then_cleanup(storage):
            try:
                raise PrivateContextError(PRIVATE)
            finally:
                await storage.mind._database.query(
                    "DELETE FROM mind WHERE mind_id = $mind_id;",
                    {"mind_id": "__tenancy_probe_" + PRIVATE},
                )

        probe = AsyncMock(side_effect=unknown_then_cleanup)
        report = await command.run_check(
            fixtures.configured(), database_factory=lambda _uri: db, probe=probe,
        )
        self.assertEqual(report["exception"], {"exception_category": "runtime"})
        self.assertEqual(report["prior_exception"], {"exception_category": "unclassified"})
        self.assertEqual(report["cleanup"], "empty")
        self.assertEqual(report["status"], "stopped")
        probe.assert_awaited_once()
        self.assertEqual(sum(call[0] == "signin" for call in db.calls), 1)
        self.assertEqual(sum(call[0] == "query" and call[1].startswith("DELETE ")
                             for call in db.calls), 1)
        self.assertTrue(db.closed)
        self.assertNotIn(PRIVATE, json.dumps(report))
        self.assertNotIn("PrivateContextError", json.dumps(report))

    async def test_real_embedded_probe_still_passes_and_cleans_up_with_trace(self):
        db = fixtures.EmbeddedDatabase()
        report = await command.run_check(fixtures.configured(), database_factory=lambda _uri: db)
        self.assertEqual(report["status"], "passed", report)
        self.assertEqual(report["cleanup"], "empty")
        self.assertIsNone(report["probe_diagnostics"]["first_failure"])
        self.assertTrue(all(count == 0 for count in report["after_counts"].values()))
        self.assertTrue(db.closed)
        self.assertNotIn(PRIVATE, json.dumps(report))


class SafeErrorMetadataTests(unittest.TestCase):
    def test_malformed_error_fields_are_ignored_without_stringification(self):
        for kind in ([], {}, None, PRIVATE):
            with self.subTest(kind_type=type(kind).__name__):
                safe = command.safe_error({
                    "kind": kind, "code": True,
                    "details": {"kind": PRIVATE, "details": {"password": PRIVATE}},
                })
                self.assertEqual(safe, {"exception_category": "database_server"})
                self.assertNotIn(PRIVATE, json.dumps(safe))

    def test_version_metadata_exposes_only_normalized_numeric_version(self):
        self.assertEqual(command._version("surrealdb-3.3.2"), "3.3.2")
        self.assertEqual(command._version("2.0.0+synthetic"), "2.0.0")
        for value in (PRIVATE, {"password": PRIVATE}, None, "3.3.2 " + PRIVATE):
            self.assertEqual(command._version(value), "unrecognized")
            self.assertNotIn(PRIVATE, command._version(value))

    def test_server_code_and_kind_are_allowlisted_without_details(self):
        safe = command.safe_error(missing_table())
        serialized = json.dumps(safe)
        self.assertIn("NotFound", serialized)
        self.assertIn("Table", serialized)
        self.assertIn("-32000", serialized)
        self.assertNotIn(PRIVATE, serialized)
        unknown = command.safe_error(ServerError(
            PRIVATE, PRIVATE, code=987654321,
            details={"kind": PRIVATE, "details": {"private": PRIVATE}},
        ))
        self.assertNotIn(PRIVATE, json.dumps(unknown))
        self.assertNotIn("987654321", json.dumps(unknown))

    def test_model_validation_and_sdk_validation_are_distinguishable(self):
        class Payload(BaseModel):
            count: int

        try:
            Payload.model_validate({"count": PRIVATE})
        except ModelValidationError as error:
            model = command.safe_error(error)
        sdk = command.safe_error(SdkValidationError(
            "Validation", PRIVATE, code=-32602, details={"kind": "InvalidParams"},
        ))
        self.assertNotEqual(model["exception_category"], sdk["exception_category"])
        self.assertNotIn(PRIVATE, json.dumps([model, sdk]))


if __name__ == "__main__":
    unittest.main()
