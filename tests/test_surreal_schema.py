"""Fresh Surreal startup schema and preservation checks; all data is synthetic."""

import copy
import re
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from surrealdb import AsyncSurreal

from aicognitive_mind.config import Settings
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.surreal_schema import APPLICATION_TABLES, bootstrap_tables
from aicognitive_mind.surreal_storage import SurrealRuntime


EXPECTED_TABLES = (
    "mind", "journal", "memory", "diagnostics", "evidence", "runtime_records",
    "commit_state", "commit_receipts",
)


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                  dotenv_settings, file_secret_settings):
        return (init_settings,)


class StrictDatabase:
    """Reject missing-table reads/updates as 3.x does, without any network."""

    def __init__(self, fail_table=None):
        self.calls = []
        self.definitions = {}
        self.fail_table = fail_table
        self.failure = RuntimeError("synthetic schema failure")

    async def connect(self):
        self.calls.append(("connect",))

    async def use(self, namespace, database):
        self.calls.append(("use", namespace, database))

    async def signin(self, credentials):
        self.calls.append(("signin", credentials))

    async def version(self):
        self.calls.append(("version",))
        return "synthetic-3.x"

    async def query(self, sql, variables=None):
        self.calls.append(("query", sql, variables))
        definition = re.fullmatch(
            r"DEFINE TABLE IF NOT EXISTS ([a-z_]+) SCHEMALESS PERMISSIONS NONE;", sql,
        )
        if definition:
            table = definition[1]
            if table == self.fail_table:
                raise self.failure
            self.definitions.setdefault(table, sql)
            return None
        migration = re.match(r"UPDATE ([a-z_]+) SET mind_id = \$mind_id WHERE mind_id = NONE;", sql)
        if migration:
            if migration[1] not in self.definitions:
                raise AssertionError("Startup touched an undefined table")
            return []
        raise AssertionError("Unexpected fixture SQL")

    async def select(self, record):
        self.calls.append(("select", record))
        if record.table_name not in self.definitions:
            raise AssertionError("Startup read an undefined table")
        return None

    async def close(self):
        self.calls.append(("close",))


class SurrealSchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.db = AsyncSurreal("mem://")
        await self.db.connect()
        await self.db.use("schema_test", "synthetic")

    async def asyncTearDown(self):
        await self.db.close()

    async def test_fresh_bootstrap_creates_only_eight_empty_application_tables(self):
        self.assertEqual(tuple(APPLICATION_TABLES), EXPECTED_TABLES)
        self.assertEqual((await self.db.query("INFO FOR DB;"))["tables"], {})
        await bootstrap_tables(self.db)
        info = await self.db.query("INFO FOR DB;")
        self.assertEqual(set(info["tables"]), set(EXPECTED_TABLES))
        for table in EXPECTED_TABLES:
            self.assertEqual(await self.db.select(table), [], table)
        self.assertEqual(await self.db.query("SELECT * FROM mind;"), [])

    async def test_repeat_bootstrap_preserves_existing_custom_schema_and_data(self):
        statements = (
            "DEFINE TABLE memory SCHEMAFULL PERMISSIONS FULL;",
            "DEFINE FIELD content ON TABLE memory TYPE string;",
            "DEFINE FIELD mind_id ON TABLE memory TYPE string;",
            "DEFINE INDEX unique_content ON TABLE memory FIELDS content UNIQUE;",
            "DEFINE EVENT preserve_event ON TABLE memory WHEN false THEN "
            "(CREATE diagnostics SET content = 'unused');",
            "CREATE memory:keep SET content = 'synthetic existing memory', mind_id = 'existing';",
        )
        for sql in statements:
            await self.db.query(sql)
        table_before = copy.deepcopy(await self.db.query("INFO FOR TABLE memory;"))
        definition_before = (await self.db.query("INFO FOR DB;"))["tables"]["memory"]
        records_before = copy.deepcopy(await self.db.select("memory"))
        await bootstrap_tables(self.db)
        await bootstrap_tables(self.db)
        self.assertEqual(await self.db.query("INFO FOR TABLE memory;"), table_before)
        self.assertEqual((await self.db.query("INFO FOR DB;"))["tables"]["memory"], definition_before)
        self.assertEqual(await self.db.select("memory"), records_before)
        self.assertEqual(await self.db.select("diagnostics"), [])

    async def test_repeat_bootstrap_is_idempotent_for_default_tables(self):
        await bootstrap_tables(self.db)
        before = copy.deepcopy(await self.db.query("INFO FOR DB;"))
        await bootstrap_tables(self.db)
        self.assertEqual(await self.db.query("INFO FOR DB;"), before)
        for table in EXPECTED_TABLES:
            self.assertEqual(await self.db.select(table), [])


class SurrealStartupOrderingTests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_precedes_every_legacy_update_and_state_read(self):
        db = StrictDatabase()
        with patch("aicognitive_mind.surreal_storage.AsyncSurreal", return_value=db):
            runtime = SurrealRuntime("wss://synthetic.invalid/rpc", "fixture_ns", "fixture_db",
                                     "fixture_user", "synthetic-password", "database")
            await runtime.initialize()
            await runtime.close()
        self.assertEqual(set(db.definitions), set(EXPECTED_TABLES))
        self.assertEqual([call[0] for call in db.calls[:4]], ["connect", "use", "signin", "version"])
        definitions = [index for index, call in enumerate(db.calls)
                       if call[0] == "query" and call[1].startswith("DEFINE ")]
        migration = [index for index, call in enumerate(db.calls)
                     if call[0] == "query" and call[1].startswith("UPDATE ")]
        reads = [index for index, call in enumerate(db.calls) if call[0] == "select"]
        self.assertEqual(len(definitions), 8)
        self.assertLess(max(definitions), min(migration + reads))

    async def test_bootstrap_failure_stops_initializer_before_migration_or_reads(self):
        db = StrictDatabase(fail_table="memory")
        with patch("aicognitive_mind.surreal_storage.AsyncSurreal", return_value=db):
            runtime = SurrealRuntime("wss://synthetic.invalid/rpc", "fixture_ns", "fixture_db")
            with self.assertRaises(RuntimeError) as raised:
                await runtime.initialize()
            self.assertIs(raised.exception, db.failure)
        self.assertFalse(any(call[0] == "select" for call in db.calls))
        self.assertFalse(any(call[0] == "query" and call[1].startswith("UPDATE ") for call in db.calls))
        self.assertNotIn("diagnostics", db.definitions)
        self.assertEqual(db.calls[-1], ("close",))
        self.assertEqual(sum(call[0] == "close" for call in db.calls), 1)

    async def test_partial_bootstrap_retry_preserves_preexisting_definition(self):
        for failed in ("mind", "memory"):
            with self.subTest(failed=failed):
                db = StrictDatabase(fail_table=failed)
                original = "DEFINE TABLE mind SCHEMAFULL PERMISSIONS FULL;"
                db.definitions["mind"] = original
                with self.assertRaises(RuntimeError):
                    await bootstrap_tables(db)
                db.fail_table = None
                await bootstrap_tables(db)
                self.assertEqual(set(db.definitions), set(EXPECTED_TABLES))
                self.assertEqual(db.definitions["mind"], original)
                for call in db.calls:
                    self.assertTrue(call[1].startswith("DEFINE TABLE IF NOT EXISTS "))
                    self.assertNotRegex(call[1], r"\b(?:OVERWRITE|DROP|REMOVE|DELETE)\b")

    async def test_close_failure_does_not_replace_original_bootstrap_failure(self):
        class FailingCloseDatabase(StrictDatabase):
            async def close(self):
                self.calls.append(("close",))
                raise ValueError("synthetic close failure")

        db = FailingCloseDatabase(fail_table="mind")
        with patch("aicognitive_mind.surreal_storage.AsyncSurreal", return_value=db):
            runtime = SurrealRuntime("wss://synthetic.invalid/rpc", "fixture_ns", "fixture_db")
            with self.assertRaises(RuntimeError) as raised:
                await runtime.initialize()
        self.assertIs(raised.exception, db.failure)
        self.assertEqual(db.calls[-1], ("close",))
        self.assertFalse(any(call[0] == "select" for call in db.calls))

    async def test_surreal_factory_bootstraps_before_returning_uninitialized_mind(self):
        db = StrictDatabase()
        settings = LocalSettings(_env_file=None, storage_provider="surreal", surrealdb_uri="mem://")
        with patch("aicognitive_mind.surreal_storage.AsyncSurreal", return_value=db):
            storage = await create_storage(settings)
            await storage.runtime.close()
        self.assertEqual(set(db.definitions), set(EXPECTED_TABLES))
        self.assertEqual(storage.mind_id, "axiom")
        self.assertFalse(any(call[0] == "create" for call in db.calls))

    async def test_mongo_factory_never_constructs_surreal_or_bootstraps_tables(self):
        runtime = MagicMock()
        runtime.initialize = AsyncMock()
        runtime.close = AsyncMock()
        settings = LocalSettings(_env_file=None, storage_provider="mongo",
                                 mongodb_uri="mongodb://synthetic.invalid")
        with patch("aicognitive_mind.persistence.MongoRuntime", return_value=runtime) as mongo, patch(
            "aicognitive_mind.surreal_storage.AsyncSurreal",
            side_effect=AssertionError("Mongo must not construct a Surreal client"),
        ) as surreal, patch(
            "aicognitive_mind.surreal_schema.bootstrap_tables", new_callable=AsyncMock,
        ) as bootstrap:
            storage = await create_storage(settings)
            await storage.runtime.close()
        mongo.assert_called_once()
        runtime.initialize.assert_awaited_once()
        surreal.assert_not_called()
        bootstrap.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
