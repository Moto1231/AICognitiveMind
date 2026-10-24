import hashlib
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from surrealdb import RecordID

from aicognitive_mind.accounts import AccountService
from aicognitive_mind.commit import CommitConflict, surreal_query
from aicognitive_mind.config import Settings
from aicognitive_mind.domain import CognitiveActor, DurableMemory, MemoryClass
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.mongo_storage import MongoMindStore
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.surreal_storage import SurrealMemoryStore, SurrealMindStore


PASSWORD = "synthetic-account-test-password"


class LocalSettings(Settings):
    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return (init_settings,)


def account_key(username):
    return "account_" + hashlib.sha256(username.strip().lower().encode()).hexdigest()


def legacy_account(username, **extra):
    salt, digest = AccountService._password_hash(PASSWORD)
    return {
        "kind": "account",
        "username": username,
        "password_salt": salt,
        "password_hash": digest,
        "active": True,
        **extra,
    }


class SurrealAccountTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix="axiom_accounts_", ignore_cleanup_errors=True
        )
        path = Path(self.directory.name).resolve()
        self.assertTrue(path.is_relative_to(Path(tempfile.gettempdir()).resolve()))
        self.settings = LocalSettings(
            _env_file=None,
            storage_provider="surreal",
            surrealdb_uri="surrealkv://" + (path / "accounts").as_posix(),
            surrealdb_namespace="local_account_tests",
            surrealdb_database="accounts",
            surrealdb_username=None,
            surrealdb_password=None,
            axiom_mind_id="registry-root",
        )
        self.storage = await create_storage(self.settings)
        self.bind_accounts()

    def bind_accounts(self):
        self.records = RuntimeRecords(self.storage.mind)
        self.accounts = AccountService(self.settings, self.records)

    async def asyncTearDown(self):
        await self.storage.runtime.close()
        self.directory.cleanup()

    async def count(self, table):
        self.assertIn(table, {"mind", "runtime_records"})
        results = await surreal_query(
            self.storage.runtime.database, f"SELECT count() AS count FROM {table} GROUP ALL;"
        )
        return results[0][0]["count"] if results[0] else 0

    async def seed(self, username, *, scope=None, key_field=True, **extra):
        key = account_key(username)
        identifier = f"{scope}__{key}" if scope else key
        value = legacy_account(username, **extra)
        if key_field:
            value["key"] = key
        await self.storage.runtime.database.create(RecordID("runtime_records", identifier), value)
        return key

    async def test_clean_signup_reads_back_and_authenticates_its_own_unnamed_mind(self):
        created = await self.accounts.create("  First-Account  ", PASSWORD)
        self.assertEqual(created.username, "first-account")
        self.assertRegex(created.mind_id, r"^mind_[0-9a-f]{32}$")
        self.assertEqual(await self.accounts.authenticate(" FIRST-ACCOUNT ", PASSWORD), created)
        stored = await self.records.get(account_key(created.username))
        self.assertEqual(stored["account_mind_id"], created.mind_id)
        self.assertNotIn("mind_id", stored)
        self.assertTrue(stored["password_hash"] != PASSWORD)
        tenant = SurrealMindStore(self.storage.runtime.database, created.mind_id)
        mind = await tenant.load()
        self.assertIsNone(mind.identity.self_name)
        self.assertEqual(mind.developmental_state, "genesis")
        self.assertIsNone(await self.storage.mind.load())
        self.assertEqual(await self.count("mind"), 1)
        self.assertEqual(await self.count("runtime_records"), 1)

    async def test_two_accounts_have_distinct_minds_and_isolated_memory(self):
        alpha = await self.accounts.create("alpha", PASSWORD)
        beta = await self.accounts.create("beta", PASSWORD)
        self.assertNotEqual(alpha.mind_id, beta.mind_id)
        self.assertEqual((await self.accounts.authenticate("alpha", PASSWORD)).mind_id, alpha.mind_id)
        self.assertEqual((await self.accounts.authenticate("beta", PASSWORD)).mind_id, beta.mind_id)
        alpha_memory = SurrealMemoryStore(self.storage.runtime.database, alpha.mind_id)
        beta_memory = SurrealMemoryStore(self.storage.runtime.database, beta.mind_id)
        await alpha_memory.remember(
            DurableMemory(memory_class=MemoryClass.SEMANTIC, content="alpha-only synthetic fact"),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        self.assertEqual(len(await alpha_memory.read()), 1)
        self.assertEqual(await beta_memory.read(), [])
        self.assertIsNotNone(await SurrealMindStore(self.storage.runtime.database, beta.mind_id).load())

    async def test_duplicate_signup_does_not_create_another_mind_or_replace_password(self):
        first = await self.accounts.create("duplicate", PASSWORD)
        before = (await self.count("mind"), await self.count("runtime_records"))
        with self.assertRaisesRegex(ValueError, "Account already exists"):
            await self.accounts.create(" DUPLICATE ", "different-synthetic-password")
        self.assertEqual((await self.count("mind"), await self.count("runtime_records")), before)
        self.assertEqual(await self.accounts.authenticate("duplicate", PASSWORD), first)
        self.assertIsNone(await self.accounts.authenticate("duplicate", "different-synthetic-password"))

    async def test_bad_credentials_and_inactive_account_are_not_authenticated(self):
        await self.accounts.create("active-account", PASSWORD)
        self.assertIsNone(await self.accounts.authenticate("active-account", "incorrect-password"))
        self.assertIsNone(await self.accounts.authenticate("missing-account", PASSWORD))
        key = account_key("active-account")
        before = await self.records.get(key)
        self.assertTrue(await self.records.replace(key, before, {**before, "active": False}))
        self.assertIsNone(await self.accounts.authenticate("active-account", PASSWORD))

    async def test_accounts_and_mind_mapping_survive_restart_and_root_id_change(self):
        alpha = await self.accounts.create("persistent-alpha", PASSWORD)
        beta = await self.accounts.create("persistent-beta", PASSWORD)
        await self.storage.runtime.close()
        self.settings = self.settings.model_copy(update={"axiom_mind_id": "different-registry-root"})
        self.storage = await create_storage(self.settings)
        self.bind_accounts()
        self.assertEqual(await self.accounts.authenticate("persistent-alpha", PASSWORD), alpha)
        self.assertEqual(await self.accounts.authenticate("persistent-beta", PASSWORD), beta)
        self.assertIsNotNone(await SurrealMindStore(self.storage.runtime.database, alpha.mind_id).load())
        self.assertIsNotNone(await SurrealMindStore(self.storage.runtime.database, beta.mind_id).load())
        self.assertEqual(await self.count("mind"), 2)
        with self.assertRaisesRegex(ValueError, "Account already exists"):
            await self.accounts.create("persistent-alpha", PASSWORD)
        self.assertEqual(await self.count("mind"), 2)

    async def test_legacy_canonical_generated_tenant_mapping_is_preserved_without_key_field(self):
        target = "mind_" + "a" * 32
        await self.seed("legacy-mapped", key_field=False, mind_id=target)
        self.assertEqual((await self.accounts.authenticate("legacy-mapped", PASSWORD)).mind_id, target)

    async def test_legacy_scoped_generated_target_is_distinct_from_storage_scope(self):
        target = "mind_" + "b" * 32
        await self.seed("legacy-scoped-mapped", scope="old-root", mind_id=target)
        self.assertEqual((await self.accounts.authenticate("legacy-scoped-mapped", PASSWORD)).mind_id, target)

    async def test_legacy_accounts_without_tenant_mapping_keep_legacy_selection(self):
        cases = (
            ("legacy-no-key", {"key_field": False}),
            ("legacy-canonical-root", {"mind_id": "old-root"}),
            ("legacy-scoped-root", {"scope": "old-root", "mind_id": "old-root"}),
            ("legacy-scoped-uuid", {"scope": "mind_" + "c" * 32, "mind_id": "mind_" + "c" * 32}),
        )
        for username, options in cases:
            with self.subTest(username=username):
                await self.seed(username, **options)
                self.assertEqual((await self.accounts.authenticate(username, PASSWORD)).mind_id, "__legacy__")

    async def test_explicit_account_mapping_wins_over_legacy_storage_metadata(self):
        await self.seed("explicit-mapping", mind_id="mind_" + "d" * 32,
                        account_mind_id="explicit-tenant")
        self.assertEqual((await self.accounts.authenticate("explicit-mapping", PASSWORD)).mind_id,
                         "explicit-tenant")

    async def test_ambiguous_global_accounts_fail_closed(self):
        await self.seed("ambiguous", key_field=False, account_mind_id="tenant-a")
        await self.seed("ambiguous", scope="old-root", account_mind_id="tenant-b")
        with self.assertRaises(CommitConflict):
            await self.accounts.authenticate("ambiguous", PASSWORD)

    async def test_nonaccount_records_remain_scoped_and_hide_storage_metadata(self):
        other = RuntimeRecords(SurrealMindStore(self.storage.runtime.database, "other-root"))
        await self.records.create("shared-setting", {"value": "root"})
        await other.create("shared-setting", {"value": "other"})
        self.assertEqual(await self.records.get("shared-setting"), {"value": "root"})
        self.assertEqual(await other.get("shared-setting"), {"value": "other"})


class FakeCursor:
    def __init__(self, rows):
        self.rows = deepcopy(rows)
        self.index = 0

    def limit(self, count):
        self.rows = self.rows[:count]
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= len(self.rows):
            raise StopAsyncIteration
        row = self.rows[self.index]
        self.index += 1
        return row


class FakeCollection:
    def __init__(self, database, rows):
        self.database = database
        self.rows = deepcopy(rows)

    @staticmethod
    def matches(row, query):
        return all(
            any(FakeCollection.matches(row, candidate) for candidate in value)
            if key == "$or" else row.get(key) == value
            for key, value in query.items()
        )

    def find(self, query):
        return FakeCursor([row for row in self.rows if self.matches(row, query)])

    async def find_one(self, query):
        return next((deepcopy(row) for row in self.rows if self.matches(row, query)), None)


class FakeMongoDatabase:
    def __init__(self, rows):
        self.collections = {}
        self.collections["runtime_records"] = FakeCollection(self, rows)

    def __getitem__(self, name):
        if name not in self.collections:
            self.collections[name] = FakeCollection(self, [])
        return self.collections[name]


class MongoAccountCompatibilityTests(unittest.IsolatedAsyncioTestCase):
    def records(self, rows):
        return RuntimeRecords(MongoMindStore(FakeMongoDatabase(rows), "new-root"))

    async def test_canonical_account_without_key_is_found_by_id(self):
        key = account_key("mongo-canonical")
        record = legacy_account("mongo-canonical", _id=key, mind_id="mind_" + "e" * 32)
        account = await AccountService(LocalSettings(_env_file=None), self.records([record])).authenticate(
            "mongo-canonical", PASSWORD
        )
        self.assertEqual(account.mind_id, "mind_" + "e" * 32)

    async def test_old_scoped_mongo_root_metadata_is_not_tenant_mapping(self):
        key = account_key("mongo-scoped")
        scope = "mind_" + "f" * 32
        record = legacy_account("mongo-scoped", _id=f"{scope}:{key}", key=key, mind_id=scope)
        account = await AccountService(LocalSettings(_env_file=None), self.records([record])).authenticate(
            "mongo-scoped", PASSWORD
        )
        self.assertEqual(account.mind_id, "__legacy__")

    async def test_ambiguous_mongo_account_keys_fail_closed(self):
        key = account_key("mongo-duplicate")
        records = self.records([
            legacy_account("mongo-duplicate", _id=key, account_mind_id="tenant-a"),
            legacy_account("mongo-duplicate", _id=f"old:{key}", key=key, account_mind_id="tenant-b"),
        ])
        with self.assertRaises(CommitConflict):
            await AccountService(LocalSettings(_env_file=None), records).authenticate("mongo-duplicate", PASSWORD)


if __name__ == "__main__":
    unittest.main()
