"""Verified account subjects and shared-connection tenant stores; synthetic data only."""

import hashlib
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from surrealdb import RecordID

from aicognitive_mind.accounts import AccountService
from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.config import Settings
from aicognitive_mind.domain import CognitiveActor, DurableMemory, MemoryClass
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.mongo_storage import (
    MongoDiagnosticStore, MongoEvidenceStore, MongoJournalStore, MongoMemoryStore, MongoMindStore,
)
from aicognitive_mind.persistence import StorageBundle, create_storage, scope_storage


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                                  dotenv_settings, file_secret_settings):
        return (init_settings,)


def account_key(username):
    return "account_" + hashlib.sha256(username.strip().lower().encode()).hexdigest()


class AccountSubjectTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.settings = LocalSettings(
            _env_file=None, storage_provider="surreal", surrealdb_uri="mem://",
            surrealdb_namespace="subjects", surrealdb_database="synthetic",
            surrealdb_username=None, surrealdb_password=None, axiom_mind_id="registry",
        )
        self.storage = await create_storage(self.settings)
        self.records = RuntimeRecords(self.storage.mind)
        self.accounts = AccountService(self.settings, self.records)
        self.alpha = await self.accounts.create("alpha", "synthetic-alpha-password")
        self.beta = await self.accounts.create("beta", "synthetic-beta-password")

    async def asyncTearDown(self):
        await self.storage.runtime.close()

    async def test_verified_subjects_resolve_across_registry_root_changes_without_initializing(self):
        other_root = scope_storage(self.storage, "changed-registry")
        accounts = AccountService(self.settings, RuntimeRecords(other_root.mind))
        with patch.object(accounts, "_ensure_mind", new_callable=AsyncMock) as initialize:
            self.assertEqual(await accounts.resolve_subject(self.alpha.mind_id), self.alpha)
            self.assertEqual(await accounts.resolve_subject(self.beta.mind_id), self.beta)
            initialize.assert_not_awaited()
        self.assertIsNone(await other_root.mind.load())
        self.assertIsNone(await self.storage.mind.load())

    async def test_missing_forged_and_malformed_subjects_never_choose_a_root_or_tenant(self):
        for subject in ("registry", "mind_" + "f" * 32, "__legacy__", "", " ",
                        " mind_alpha", "tenant/elsewhere", "tenant';DELETE mind", None, 123):
            with self.subTest(subject=subject):
                self.assertIsNone(await self.accounts.resolve_subject(subject))
        self.assertIsNone(await self.storage.mind.load())

    async def test_inactive_account_is_not_resolved(self):
        key = account_key("alpha")
        before = await self.records.get(key)
        self.assertTrue(await self.records.replace(key, before, {**before, "active": False}))
        self.assertIsNone(await self.accounts.resolve_subject(self.alpha.mind_id))
        self.assertEqual(await self.accounts.resolve_subject(self.beta.mind_id), self.beta)

    async def test_two_active_accounts_claiming_one_subject_fail_closed(self):
        key = account_key("beta")
        before = await self.records.get(key)
        self.assertTrue(await self.records.replace(
            key, before, {**before, "account_mind_id": self.alpha.mind_id},
        ))
        with self.assertRaisesRegex(CommitConflict, "Ambiguous account subject"):
            await self.accounts.resolve_subject(self.alpha.mind_id)

    async def test_canonical_lookup_rejects_a_duplicate_with_a_different_subject(self):
        key = account_key("alpha")
        before = await self.records.get(key)
        await self.storage.runtime.database.create(
            RecordID("runtime_records", "old-root__" + key),
            {**before, "key": key, "mind_id": "old-root", "account_mind_id": "different-subject"},
        )
        with self.assertRaisesRegex(CommitConflict, "Ambiguous account registry"):
            await self.accounts.resolve_subject(self.alpha.mind_id)

    async def test_canonical_account_changes_after_lookup_are_not_authorized(self):
        original = await self.records.get(account_key("alpha"))
        for revised in (
            {**original, "active": False},
            {**original, "account_mind_id": self.beta.mind_id},
            {**original, "username": "different-account"},
            {**original, "kind": "not-an-account"},
        ):
            with self.subTest(revised_keys=tuple(revised)), patch.object(
                self.records, "get", new_callable=AsyncMock, return_value=revised,
            ):
                self.assertIsNone(await self.accounts.resolve_subject(self.alpha.mind_id))

    async def test_non_uuid_subjects_are_verified_instead_of_assumed_to_be_admin(self):
        await self.records.create(account_key("custom-mapped-account"), {
            "kind": "account", "username": "custom-mapped-account", "active": True,
            "account_mind_id": "mind",
        })
        account = await self.accounts.resolve_subject("mind")
        self.assertEqual((account.username, account.mind_id), ("custom-mapped-account", "mind"))

    async def test_legacy_generated_mapping_and_single_legacy_account_remain_resolvable(self):
        for username, scope in (("historic-canonical", None), ("historic-scoped", "old-root")):
            key = account_key(username)
            target = "mind_" + ("a" if scope is None else "b") * 32
            row = {"kind": "account", "active": True, "username": username, "mind_id": target}
            if scope is not None:
                row["key"] = key
            await self.storage.runtime.database.create(
                RecordID("runtime_records", f"{scope}__{key}" if scope else key), row,
            )
            account = await self.accounts.resolve_subject(target)
            self.assertEqual((account.username, account.mind_id), (username, target))

        # Remove no records: use another namespace/database for the singular
        # pre-tenant legacy case, keeping the preservation test independent.
        await self.storage.runtime.database.use("subjects", "legacy_synthetic")
        from aicognitive_mind.surreal_schema import bootstrap_tables
        await bootstrap_tables(self.storage.runtime.database)
        await self.records.create(account_key("legacy-one"), {
            "kind": "account", "username": "legacy-one", "active": True,
        })
        account = await self.accounts.resolve_subject("__legacy__")
        self.assertEqual((account.username, account.mind_id), ("legacy-one", "__legacy__"))
        await self.records.create(account_key("legacy-two"), {
            "kind": "account", "username": "legacy-two", "active": True,
        })
        with self.assertRaisesRegex(CommitConflict, "Ambiguous account subject"):
            await self.accounts.resolve_subject("__legacy__")

    async def test_generated_storage_scope_is_not_treated_as_a_historical_selector(self):
        target = "mind_" + "c" * 32
        key = account_key("old-root-account")
        await self.storage.runtime.database.create(
            RecordID("runtime_records", target + "__" + key),
            {"kind": "account", "username": "old-root-account", "active": True,
             "key": key, "mind_id": target},
        )
        self.assertIsNone(await self.accounts.resolve_subject(target))

    async def test_subject_metadata_excludes_credentials_and_uses_bounded_projection(self):
        metadata = await self.records.account_subject_records(self.alpha.mind_id)
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0]["username"], "alpha")
        self.assertNotIn("password_hash", metadata[0])
        self.assertNotIn("password_salt", metadata[0])
        with patch("aicognitive_mind.host_runtime.surreal_query", new_callable=AsyncMock,
                   return_value=[[]]) as query:
            await self.records.account_subject_records(self.alpha.mind_id)
        sql, parameters = query.await_args.args[1:]
        self.assertNotIn("SELECT *", sql)
        self.assertNotIn("password", sql)
        self.assertIn("LIMIT 2", sql)
        self.assertNotIn(self.alpha.mind_id, sql)
        self.assertEqual(parameters, {"subject": self.alpha.mind_id})

    async def test_scope_storage_shares_connection_and_policy_without_bootstrap_or_root_writes(self):
        with patch.object(self.storage.runtime, "initialize", new_callable=AsyncMock) as initialize:
            alpha = scope_storage(self.storage, self.alpha.mind_id)
            beta = scope_storage(self.storage, self.beta.mind_id)
            initialize.assert_not_awaited()
        self.assertIs(scope_storage(self.storage, self.storage.mind_id), self.storage)
        for scoped in (alpha, beta):
            self.assertIs(scoped.runtime, self.storage.runtime)
            for field in ("mind", "journal", "memory", "diagnostics", "evidence"):
                self.assertEqual(getattr(scoped, field).mind_id, scoped.mind_id)
                self.assertIs(getattr(scoped, field)._database, self.storage.runtime.database)
            for field in ("mind", "journal", "memory"):
                self.assertIs(getattr(scoped, field)._policy, getattr(self.storage, field)._policy)
        await alpha.memory.remember(
            DurableMemory(memory_class=MemoryClass.SEMANTIC, content="alpha-only synthetic record"),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        self.assertEqual(len(await alpha.memory.read()), 1)
        self.assertEqual(await beta.memory.read(), [])
        self.assertEqual(await self.storage.memory.read(), [])
        self.assertIsNone(await self.storage.mind.load())


class FakeCursor:
    def __init__(self, rows, collection):
        self.rows = deepcopy(rows)
        self.collection = collection
        self.index = 0

    def limit(self, count):
        self.collection.last_limit = count
        self.rows = self.rows[:count]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index == len(self.rows):
            raise StopAsyncIteration
        row = self.rows[self.index]
        self.index += 1
        return row


class FakeCollection:
    def __init__(self, database, rows=()):
        self.database = database
        self.rows = deepcopy(list(rows))
        self.last_projection = None
        self.last_limit = None

    def matches(self, row, query):
        for key, value in query.items():
            if key == "$or":
                if not any(self.matches(row, item) for item in value):
                    return False
            elif key == "$and":
                if not all(self.matches(row, item) for item in value):
                    return False
            elif isinstance(value, dict) and "$exists" in value:
                if (key in row) != value["$exists"]:
                    return False
            elif row.get(key) != value:
                return False
        return True

    def find(self, query, projection=None):
        self.last_projection = projection
        rows = [row for row in self.rows if self.matches(row, query)]
        if projection:
            rows = [{key: value for key, value in row.items() if projection.get(key)} for row in rows]
        return FakeCursor(rows, self)


class FakeDatabase:
    def __init__(self, rows=()):
        self.collections = {"runtime_records": FakeCollection(self, rows)}

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(self)
        return self.collections[name]


class MongoAccountSubjectTests(unittest.IsolatedAsyncioTestCase):
    def records(self, rows):
        database = FakeDatabase(rows)
        return RuntimeRecords(MongoMindStore(database, "new-root")), database

    async def test_projection_and_legacy_subjects_are_global_and_credential_free(self):
        subject = "mind_" + "d" * 32
        key = account_key("mongo-user")
        records, database = self.records([{
            "_id": key, "kind": "account", "username": "mongo-user", "active": True,
            "mind_id": subject, "password_hash": "synthetic-hash", "password_salt": "synthetic-salt",
        }])
        metadata = await records.account_subject_records(subject)
        self.assertNotIn("password_hash", metadata[0])
        collection = database["runtime_records"]
        self.assertNotIn("password_hash", collection.last_projection)
        self.assertEqual(collection.last_limit, 2)
        account = await AccountService(LocalSettings(_env_file=None), records).resolve_subject(subject)
        self.assertEqual((account.username, account.mind_id), ("mongo-user", subject))

    async def test_duplicate_subjects_fail_closed_and_inactive_matches_are_excluded(self):
        subject = "tenant-synthetic"
        records, database = self.records([
            {"_id": account_key(name), "kind": "account", "username": name,
             "active": active, "account_mind_id": subject}
            for name, active in (("alpha", True), ("beta", True), ("inactive", False))
        ])
        with self.assertRaises(CommitConflict):
            await AccountService(LocalSettings(_env_file=None), records).resolve_subject(subject)
        self.assertEqual(database["runtime_records"].last_limit, 2)

    async def test_scope_storage_preserves_mongo_connection_and_all_store_scopes(self):
        database = FakeDatabase()
        runtime = SimpleNamespace(database=database, initialize=AsyncMock(), close=AsyncMock())
        root = StorageBundle(
            mind_id="registry", runtime=runtime, mind=MongoMindStore(database, "registry"),
            journal=MongoJournalStore(database, "registry"), memory=MongoMemoryStore(database, "registry"),
            diagnostics=MongoDiagnosticStore(database, "registry"), evidence=MongoEvidenceStore(database, "registry"),
        )
        scoped = scope_storage(root, "account-one")
        self.assertIs(scoped.runtime, runtime)
        for field in ("mind", "journal", "memory", "diagnostics", "evidence"):
            store = getattr(scoped, field)
            self.assertEqual(store.mind_id, "account-one")
            self.assertIs(store._collection.database, database)
        runtime.initialize.assert_not_awaited()
        runtime.close.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
