import os
import unittest
from uuid import uuid4

from aicognitive_mind.commit import commit
from aicognitive_mind.domain import MindIdentity
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.mongo_storage import (
    MongoDiagnosticStore,
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
    MongoRuntime,
)
from aicognitive_mind.snapshot import cognitive_snapshot


@unittest.skipUnless(os.environ.get("MONGODB_TEST_URI"), "Requires disposable Mongo replica set")
class MongoTransactions(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.name = "axiom_transaction_test_" + uuid4().hex
        self.runtime = MongoRuntime(os.environ["MONGODB_TEST_URI"], self.name)
        await self.runtime.initialize()
        self.mind = MongoMindStore(self.runtime.database)
        self.journal = MongoJournalStore(self.runtime.database)
        self.memory = MongoMemoryStore(self.runtime.database)
        self.service = CognitiveMcpService(self.mind, self.journal, self.memory)
        await self.service.initialize("Axiom")

    async def asyncTearDown(self):
        assert self.name.startswith("axiom_transaction_test_")
        await self.runtime.client.drop_database(self.name)
        await self.runtime.close()

    async def test_rollback_receipt_and_consistent_snapshot(self):
        original = await self.mind.load()
        replacement = original.model_copy(update={"identity": MindIdentity(self_name="Changed")})
        missing = original.model_copy(update={"identity": MindIdentity(self_name="Missing")})
        with self.assertRaises(Exception):
            await commit(
                {"mind": self.mind},
                [
                    ("mind", "replace", original, replacement),
                    ("mind", "replace", missing, original),
                ],
                None,
                {},
            )
        self.assertEqual(await self.mind.load(), original)
        first = await self.service.complete_interaction("Hello", "Hello", idempotency_key="retry")
        self.assertEqual(
            first,
            await self.service.complete_interaction("Hello", "Hello", idempotency_key="retry"),
        )
        snapshot = await cognitive_snapshot(
            self.mind, self.journal, self.memory, MongoDiagnosticStore(self.runtime.database)
        )
        self.assertEqual(snapshot["mind"], original)
        self.assertEqual(len(snapshot["journal"]), 2)
