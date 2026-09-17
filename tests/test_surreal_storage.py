import unittest

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
)
from aicognitive_mind.storage import MindAlreadyInitializedError
from aicognitive_mind.surreal_storage import (
    SurrealDiagnosticStore,
    SurrealFoundationStore,
    SurrealJournalStore,
    SurrealMemoryStore,
    SurrealMindStore,
    SurrealRuntime,
)


class SurrealStorageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.runtime = SurrealRuntime("mem://", "test", "cognitive_mind")
        await self.runtime.initialize()

    async def asyncTearDown(self) -> None:
        await self.runtime.close()

    async def test_mind_round_trips_and_remains_singleton(self) -> None:
        store = SurrealMindStore(self.runtime.database)
        mind = CognitiveMind(identity=MindIdentity(self_name="Genesis"))

        created = await store.initialize(mind)
        loaded = await store.load()

        self.assertEqual(created, mind)
        self.assertEqual(loaded, mind)
        with self.assertRaises(MindAlreadyInitializedError):
            await store.initialize(mind)

    async def test_foundation_revisions_preserve_history(self) -> None:
        store = SurrealFoundationStore(self.runtime.database)

        first = await store.seed("conscious_workspace", "Version one")
        second = await store.revise(
            "conscious_workspace",
            "Version two",
            changed_by="administrator",
        )
        history = await store.read_history("conscious_workspace")
        active = await store.load_active("conscious_workspace")

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertEqual([record.version for record in history], [1, 2])
        self.assertFalse(history[0].active)
        self.assertTrue(history[1].active)
        self.assertEqual(active, history[1])

    async def test_journal_memory_and_diagnostics_round_trip(self) -> None:
        journal = SurrealJournalStore(self.runtime.database)
        memory = SurrealMemoryStore(self.runtime.database)
        diagnostics = SurrealDiagnosticStore(self.runtime.database)

        entry = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"input": {"source": "human", "content": "Hello"}},
        )
        durable = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The human's birthday is February 7.",
            associations=("birthday",),
            grounding=("human assertion",),
        )
        observation = DiagnosticObservation(
            component="surreal_storage",
            operation="round_trip",
            implementation={"engine": "surrealdb"},
        )

        await journal.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
        await memory.remember(
            durable,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        await diagnostics.record(observation)

        self.assertEqual(await journal.read(), [entry])
        self.assertEqual(await memory.read(), [durable])
        self.assertEqual(await diagnostics.read(), [observation])


if __name__ == "__main__":
    unittest.main()
