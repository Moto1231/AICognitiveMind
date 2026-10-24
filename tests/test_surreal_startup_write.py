"""Local-only safety coverage for the explicitly selected remote write probe."""

import asyncio
import contextlib
import copy
import importlib.util
import io
import json
import logging
import re
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from surrealdb import AsyncSurreal


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "surreal_startup_write_under_test", ROOT / "scripts" / "surreal_startup_write.py",
)
command = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(command)
PRIVATE = "synthetic-private-password-token-schema-payload"
PROBE_ID = "synthetic-private-probe-id"
EDITOR = (
    "DEFINE USER axiom_runtime ON DATABASE PASSHASH '" + PRIVATE + "' "
    "ROLES EDITOR DURATION FOR TOKEN 1h, FOR SESSION NONE COMMENT '" + PRIVATE + "'"
)


def configured(**changes):
    env = {
        "AXIOM_STARTUP_APP_SHA": command.APP_SHA,
        "AXIOM_RUNTIME_SURREALDB_USERNAME": "axiom_runtime",
        "AXIOM_RUNTIME_SURREALDB_PASSWORD": PRIVATE,
    }
    env.update(changes)
    return env


class MetadataDatabase:
    """Fixed metadata only; unexpected SQL is rejected, not executed."""

    def __init__(self):
        self.calls = []
        self.counts = {}
        self.role = EDITOR
        self.extra = {}
        self.schemas = {}
        self.table_definitions = {}
        self.after_probe = False
        self.fail_stage = None
        self.closed = False
        self.noisy = False

    async def connect(self):
        self.calls.append(("connect",))
        if self.noisy:
            print(PRIVATE)
            logging.getLogger(__name__).critical(PRIVATE)
        if self.fail_stage == "connection":
            raise RuntimeError(PRIVATE)

    async def signin(self, credentials):
        self.calls.append(("signin", credentials))
        if self.fail_stage == "authentication":
            raise RuntimeError(PRIVATE)
        return PRIVATE

    async def use(self, namespace, database):
        self.calls.append(("use", namespace, database))

    async def version(self):
        self.calls.append(("version",))
        return "synthetic-version"

    async def query(self, sql):
        self.calls.append(("query", sql))
        if self.after_probe and self.fail_stage == "after_inventory":
            raise RuntimeError(PRIVATE)
        if sql == "INFO FOR DB;":
            return {
                "users": {"axiom_runtime": self.role},
                "tables": {name: self.table_definitions.get(
                    name, "DEFINE TABLE " + name + " TYPE ANY SCHEMALESS PERMISSIONS NONE",
                ) for name in self.counts},
                **copy.deepcopy(self.extra),
            }
        match = re.fullmatch(r"INFO FOR TABLE ([a-z_]+);", sql)
        if match:
            return copy.deepcopy(self.schemas.get(match[1], {
                "events": {}, "fields": {}, "indexes": {}, "tables": {},
            }))
        match = re.fullmatch(r"SELECT count\(\) AS total FROM ([a-z_]+) GROUP ALL;", sql)
        if match and match[1] in command.TABLES:
            return [{"total": self.counts[match[1]]}]
        raise AssertionError("Unexpected diagnostic SQL")

    async def close(self):
        self.calls.append(("close",))
        self.closed = True
        if self.fail_stage == "close":
            raise RuntimeError(PRIVATE)


class EmbeddedDatabase:
    """Real isolated mem:// data path with synthetic authentication metadata.

    This intentionally does not claim to verify Cloud authentication or grants.
    No endpoint, credentials, files or ambient settings are read.
    """

    def __init__(self, *, fail_memory_create=False):
        self.real = AsyncSurreal("mem://")
        self.calls = []
        self.closed = False
        self.fail_memory_create = fail_memory_create

    async def connect(self):
        self.calls.append(("connect",))
        await self.real.connect()

    async def signin(self, credentials):
        self.calls.append(("signin", credentials))
        return PRIVATE

    async def use(self, namespace, database):
        self.calls.append(("use", namespace, database))
        await self.real.use(namespace, database)

    async def version(self):
        return await self.real.version()

    async def query(self, sql, variables=None):
        self.calls.append(("query", sql, variables))
        result = await self.real.query(sql, variables)
        if sql == "INFO FOR DB;":
            result["users"] = {"axiom_runtime": EDITOR}
        return result

    async def query_raw(self, sql, variables=None):
        self.calls.append(("query_raw", sql, variables))
        return await self.real.query_raw(sql, variables)

    async def select(self, record):
        self.calls.append(("select", record))
        return await self.real.select(record)

    async def create(self, record, data):
        self.calls.append(("create", record, data))
        if record == "memory" and self.fail_memory_create:
            raise RuntimeError(PRIVATE)
        return await self.real.create(record, data)

    async def close(self):
        self.closed = True
        await self.real.close()


class StartupWriteGuardTests(unittest.IsolatedAsyncioTestCase):
    async def run_fixture(self, db, *, probe=None, env=None, **options):
        async def passed(storage):
            db.after_probe = True
            self.assertEqual(storage.mind.mind_id, "axiom")
            return {"status": "passed", "primary_initialized": False, "probe_mind_id": PROBE_ID}

        factory = Mock(return_value=db)
        probe = AsyncMock(side_effect=passed) if probe is None else probe
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            result = await command.run_check(
                configured() if env is None else env,
                database_factory=factory, probe=probe, **options,
            )
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertNotIn(PROBE_ID, json.dumps(result))
        return result, factory, probe

    async def test_configuration_failure_never_constructs_client(self):
        cases = [
            {}, configured(AXIOM_STARTUP_APP_SHA="other"),
            configured(AXIOM_RUNTIME_SURREALDB_USERNAME="root"),
            configured(AXIOM_RUNTIME_SURREALDB_USERNAME="axiom_preflight_reader"),
            configured(AXIOM_RUNTIME_SURREALDB_USERNAME=""),
            configured(AXIOM_RUNTIME_SURREALDB_PASSWORD=""),
        ]
        for env in cases:
            with self.subTest(keys=sorted(env)):
                result, factory, probe = await self.run_fixture(MetadataDatabase(), env=env)
                factory.assert_not_called()
                probe.assert_not_awaited()
                self.assertEqual(result["status"], "stopped")
                self.assertEqual(result["stage"], "configuration")
                self.assertFalse(result["write_attempted"])

    async def test_target_scope_and_source_are_fixed_not_environment_selected(self):
        db = MetadataDatabase()
        result, factory, probe = await self.run_fixture(db, env=configured(
            SURREALDB_URI="wss://unapproved.invalid/rpc",
            SURREALDB_NAMESPACE="elsewhere", SURREALDB_DATABASE="elsewhere",
            SURREALDB_AUTH_LEVEL="root", STORAGE_PROVIDER="mongo", AXIOM_MIND_ID="elsewhere",
        ))
        self.assertEqual(command.APP_SHA, "65157abe34b659b0da2c6c162fa51ee8fff5de6d")
        self.assertEqual(command.HOST, "mir-ai-06gmqbgl1duq581garj3eabaq4.aws-use1.surreal.cloud")
        factory.assert_called_once_with(f"wss://{command.HOST}/rpc")
        self.assertEqual([call for call in db.calls if call[0] == "signin"], [("signin", {
            "namespace": "mir_ai", "database": "ai_cognitive_mind",
            "username": "axiom_runtime", "password": PRIVATE,
        })])
        self.assertIn(("use", "mir_ai", "ai_cognitive_mind"), db.calls)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["role"], "EDITOR")
        self.assertEqual(result["legacy_migration"], "skipped")
        self.assertEqual(result["cleanup"], "empty")
        self.assertEqual(set(result["before_counts"]), set(command.TABLES))
        self.assertTrue(all(value == 0 for value in result["after_counts"].values()))
        probe.assert_awaited_once()
        self.assertTrue(db.closed)

    async def test_authentication_failure_is_not_retried_or_followed_by_use(self):
        db = MetadataDatabase()
        db.fail_stage = "authentication"
        result, _, probe = await self.run_fixture(db)
        self.assertEqual(result["stage"], "authentication")
        self.assertEqual(result["error_kind"], "operation_failed")
        self.assertEqual(sum(call[0] == "signin" for call in db.calls), 1)
        self.assertFalse(any(call[0] == "use" for call in db.calls))
        self.assertFalse(result["write_attempted"])
        probe.assert_not_awaited()
        self.assertTrue(db.closed)

    async def test_wrong_missing_or_misleading_roles_fail_before_probe(self):
        for definition in (
            None, {}, "DEFINE USER axiom_runtime ON DATABASE ROLES OWNER",
            "DEFINE USER axiom_runtime ON DATABASE ROLES VIEWER",
            "DEFINE USER axiom_runtime ON DATABASE ROLES EDITOR, VIEWER",
            "DEFINE USER axiom_runtime ON ROOT ROLES EDITOR",
            "DEFINE USER another_user ON DATABASE ROLES EDITOR",
            "DEFINE USER axiom_runtime ON DATABASE COMMENT 'ROLES EDITOR'",
            "DEFINE USER axiom_runtime ON DATABASE ROLES VIEWER COMMENT 'ROLES EDITOR'",
            'DEFINE USER axiom_runtime ON DATABASE ROLES OWNER COMMENT "ROLES EDITOR"',
        ):
            with self.subTest(definition=definition):
                db = MetadataDatabase()
                db.role = definition
                result, _, probe = await self.run_fixture(db)
                self.assertEqual(result["error_kind"], "editor_database_role_unverified")
                self.assertFalse(result["write_attempted"])
                probe.assert_not_awaited()

    async def test_nonempty_target_is_not_reset(self):
        db = MetadataDatabase()
        db.counts = {"mind": 1, "runtime_records": 2}
        result, _, probe = await self.run_fixture(db)
        self.assertEqual(result["error_kind"], "target_nonempty")
        self.assertEqual(result["before_counts"]["runtime_records"], 2)
        self.assertEqual(db.counts, {"mind": 1, "runtime_records": 2})
        self.assertFalse(result["write_attempted"])
        probe.assert_not_awaited()

    async def test_unknown_tables_and_custom_database_code_are_rejected(self):
        for changes, kind in (
            ({"counts": {"private_table_" + PRIVATE: 0}}, "unknown_tables_present"),
            ({"extra": {"functions": {"private_function": PRIVATE}}}, "unexpected_schema"),
        ):
            with self.subTest(kind=kind):
                db = MetadataDatabase()
                for key, value in changes.items():
                    setattr(db, key, value)
                result, _, probe = await self.run_fixture(db)
                self.assertEqual(result["error_kind"], kind)
                self.assertFalse(result["write_attempted"])
                probe.assert_not_awaited()

    async def test_existing_table_fields_indexes_or_events_are_rejected(self):
        for part in ("fields", "events", "indexes"):
            with self.subTest(part=part):
                db = MetadataDatabase()
                db.counts = {"memory": 0}
                db.schemas = {"memory": {part: {"custom": PRIVATE}}}
                result, _, probe = await self.run_fixture(db)
                self.assertEqual(result["error_kind"], "unexpected_table_schema")
                self.assertFalse(result["write_attempted"])
                probe.assert_not_awaited()

    async def test_custom_table_definitions_are_rejected_before_writes(self):
        for definition in (
            "DEFINE TABLE memory SCHEMAFULL PERMISSIONS NONE",
            "DEFINE TABLE memory TYPE RELATION SCHEMALESS PERMISSIONS NONE",
            "DEFINE TABLE memory TYPE ANY SCHEMALESS CHANGEFEED 1h PERMISSIONS NONE",
            "DEFINE TABLE memory AS SELECT * FROM another_table PERMISSIONS NONE",
            "DEFINE TABLE memory TYPE ANY SCHEMALESS PERMISSIONS FULL",
        ):
            with self.subTest(definition=definition):
                db = MetadataDatabase()
                db.counts = {"memory": 0}
                db.table_definitions["memory"] = definition
                result, _, probe = await self.run_fixture(db)
                self.assertEqual(result["error_kind"], "unexpected_table_schema")
                self.assertFalse(result["write_attempted"])
                probe.assert_not_awaited()

    async def test_probe_exception_reports_residue_without_cleanup_reset_or_retry(self):
        db = MetadataDatabase()

        async def failed(_storage):
            db.after_probe = True
            db.counts = {"memory": 1}
            raise RuntimeError(PRIVATE)

        probe = AsyncMock(side_effect=failed)
        result, _, _ = await self.run_fixture(db, probe=probe)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["stage"], "tenancy_probe")
        self.assertEqual(result["error_kind"], "operation_failed")
        self.assertEqual(result["cleanup"], "records_remain")
        self.assertEqual(result["after_counts"]["memory"], 1)
        self.assertEqual(db.counts["memory"], 1)
        probe.assert_awaited_once()
        self.assertTrue(result["write_attempted"])

    async def test_failed_probe_with_empty_target_stays_failed(self):
        probe = AsyncMock(side_effect=RuntimeError(PRIVATE))
        result, _, _ = await self.run_fixture(MetadataDatabase(), probe=probe)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["cleanup"], "empty")
        probe.assert_awaited_once()

    async def test_unexpected_check_exception_argument_is_not_reported(self):
        probe = AsyncMock(side_effect=command.CheckStopped(PRIVATE))
        result, _, _ = await self.run_fixture(MetadataDatabase(), probe=probe)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["error_kind"], "operation_failed")

    async def test_probe_cannot_claim_success_if_primary_was_initialized(self):
        probe = AsyncMock(return_value={"status": "passed", "primary_initialized": True})
        result, _, _ = await self.run_fixture(MetadataDatabase(), probe=probe)
        self.assertEqual(result["error_kind"], "tenancy_probe_failed")
        self.assertEqual(result["status"], "stopped")

    async def test_successful_probe_is_followed_by_independent_zero_count_check(self):
        db = MetadataDatabase()

        async def residue(_storage):
            db.after_probe = True
            db.counts = {"commit_state": 1}
            return {"status": "passed", "primary_initialized": False}

        result, _, _ = await self.run_fixture(db, probe=AsyncMock(side_effect=residue))
        self.assertEqual(result["error_kind"], "post_probe_target_nonempty")
        self.assertEqual(result["cleanup"], "records_remain")
        self.assertEqual(result["after_counts"]["commit_state"], 1)

    async def test_post_probe_metadata_failure_leaves_cleanup_unverified(self):
        db = MetadataDatabase()
        db.fail_stage = "after_inventory"
        result, _, _ = await self.run_fixture(db)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["stage"], "after_inventory")
        self.assertEqual(result["cleanup"], "unverified")

    async def test_timeout_is_bounded_and_not_retried(self):
        entered = asyncio.Event()

        async def waits_forever(_storage):
            entered.set()
            await asyncio.Event().wait()

        probe = AsyncMock(side_effect=waits_forever)
        result, _, _ = await self.run_fixture(
            MetadataDatabase(), probe=probe, timeout_seconds=0.02,
        )
        self.assertTrue(entered.is_set())
        self.assertEqual(result["error_kind"], "timeout")
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["cleanup"], "empty")
        probe.assert_awaited_once()

    async def test_connection_close_failure_prevents_pass(self):
        db = MetadataDatabase()
        db.fail_stage = "close"
        result, _, _ = await self.run_fixture(db)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["stage"], "close")
        self.assertEqual(result["error_kind"], "close_failed")
        self.assertEqual(result["cleanup"], "empty")

    async def test_transport_output_and_private_exception_details_are_suppressed(self):
        db = MetadataDatabase()
        db.noisy = True
        db.fail_stage = "authentication"
        result, _, _ = await self.run_fixture(db)
        self.assertNotIn(PRIVATE, json.dumps(result))

    async def test_real_local_probe_cleans_every_table_without_normal_initializer(self):
        db = EmbeddedDatabase()
        factory = Mock(return_value=db)
        with patch("aicognitive_mind.surreal_storage.SurrealRuntime.initialize", side_effect=AssertionError("Migration is excluded")) as initialize, patch(
            "aicognitive_mind.persistence.create_storage", side_effect=AssertionError("Migration is excluded"),
        ) as create_storage:
            result = await command.run_check(configured(), database_factory=factory)
        initialize.assert_not_called()
        create_storage.assert_not_called()
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["cleanup"], "empty")
        self.assertTrue(all(count == 0 for count in result["after_counts"].values()))
        self.assertFalse(any("WHERE mind_id = NONE" in str(call) for call in db.calls))
        self.assertTrue(db.closed)
        for call in db.calls:
            if call[0] == "query" and call[1].startswith("DELETE "):
                self.assertTrue(call[2]["mind_id"].startswith("__tenancy_probe_"))
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertNotIn("probe_mind_id", result)

    async def test_real_local_probe_partial_failure_cleans_generated_scope(self):
        db = EmbeddedDatabase(fail_memory_create=True)
        result = await command.run_check(configured(), database_factory=lambda _uri: db)
        self.assertEqual(result["status"], "stopped")
        self.assertEqual(result["stage"], "tenancy_probe")
        self.assertEqual(result["cleanup"], "empty", result)
        self.assertTrue(result["write_attempted"])
        self.assertTrue(all(count == 0 for count in result["after_counts"].values()))
        self.assertTrue(db.closed)
        self.assertNotIn(PRIVATE, json.dumps(result))


class StartupWriteCommandTests(unittest.TestCase):
    def test_workflow_is_manual_pinned_and_uses_only_separate_runtime_secrets(self):
        workflow = (ROOT / ".github" / "workflows" / "surreal-startup-write.yml").read_text(encoding="utf-8")
        self.assertRegex(workflow, r"(?m)^on:\n  workflow_dispatch:\n")
        for trigger in ("push:", "pull_request:", "schedule:"):
            self.assertNotIn(trigger, workflow)
        self.assertIn("ref: " + command.APP_SHA, workflow)
        self.assertIn("git -C startup-source rev-parse HEAD", workflow)
        self.assertIn("pip install ./startup-source", workflow)
        self.assertIn("python -I -B scripts/surreal_startup_write.py", workflow)
        self.assertIn("contents: read", workflow)
        self.assertEqual(set(re.findall(r"secrets\.([A-Z0-9_]+)", workflow)), {
            "AXIOM_RUNTIME_SURREALDB_USERNAME", "AXIOM_RUNTIME_SURREALDB_PASSWORD",
        })
        self.assertNotIn("CANONICAL_", workflow)
        self.assertNotIn("MONGODB", workflow)
        self.assertNotIn("migrate-from-atlas", workflow)
        self.assertNotIn("render_trigger_deploy", workflow)

    def test_command_prints_only_report_and_returns_matching_exit_status(self):
        for status, code in (("passed", 0), ("stopped", 1)):
            report = {"status": status, "stage": "complete"}
            output = io.StringIO()
            with self.subTest(status=status), patch.object(
                command, "run_check", AsyncMock(return_value=report),
            ), contextlib.redirect_stdout(output):
                with self.assertRaises(SystemExit) as result:
                    command.main()
                self.assertEqual(result.exception.code, code)
            self.assertEqual(json.loads(output.getvalue()), report)


if __name__ == "__main__":
    unittest.main()
