import unittest
from datetime import UTC, datetime, timedelta

from aicognitive_mind.config import Settings
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryArtifact,
    MemoryClass,
    MindIdentity,
)
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.storage import MindAlreadyInitializedError
from aicognitive_mind.surreal_storage import (
    SurrealDiagnosticStore,
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

    async def test_journal_searches_full_collection_before_paging(self) -> None:
        store = SurrealJournalStore(self.runtime.database)
        base = datetime(2026, 9, 18, 12, tzinfo=UTC)
        entries = [
            JournalEntry(
                kind=JournalKind.INTERACTION,
                occurred_at=base + timedelta(minutes=index),
                experience={
                    "input": {"content": text},
                    "expression": {"content": response},
                },
            )
            for index, (text, response) in enumerate(
                [
                    ("Hello", "Hello."),
                    ("When is my birthday?", "Your birthday is February 7."),
                    ("Birthday reminder", "February 7 remains remembered."),
                ]
            )
        ]
        for entry in entries:
            await store.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)

        page, total = await store.query_page(
            offset=0,
            limit=1,
            newest_first=True,
            search="birthday",
        )

        self.assertEqual(total, 2)
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0], entries[2])

        exact = await store.find_exact(
            kind=entries[1].kind.value,
            occurred_at=entries[1].occurred_at,
        )
        self.assertEqual(exact, entries[1])

    async def test_memory_searches_full_collection_and_replaces_exact_document(self) -> None:
        store = SurrealMemoryStore(self.runtime.database)
        base = datetime(2026, 9, 18, 12, tzinfo=UTC)
        memories = [
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                formed_at=base + timedelta(minutes=index),
                content=content,
                associations=associations,
                grounding=("direct-user-statement",),
            )
            for index, (content, associations) in enumerate(
                [
                    ("The user likes parks.", ("parks",)),
                    ("The user's birthday is February 7.", ("birthday", "personal")),
                    ("The user prefers concise iteration.", ("collaboration",)),
                ]
            )
        ]
        for memory in memories:
            await store.remember(
                memory,
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )

        page, total = await store.query_page(
            offset=0,
            limit=1,
            newest_first=True,
            search="birthday",
            association="personal",
        )

        self.assertEqual(total, 1)
        self.assertEqual(page, [memories[1]])

        replacement = memories[1].model_copy(
            update={"content": "Will's birthday is February 7."}
        )
        revised = await store.replace_exact(
            memories[1],
            replacement,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        self.assertEqual(revised, replacement)
        stored = await store.read()
        self.assertIn(replacement, stored)
        self.assertNotIn(memories[1], stored)


    async def test_memory_search_finds_evidence_provenance_outside_visible_text(self) -> None:
        store = SurrealMemoryStore(self.runtime.database)
        memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The deployment date is October 8.",
            grounding=("status update",),
            artifacts=(
                MemoryArtifact(
                    kind="evidence_appraisal",
                    payload={
                        "confidence": 0.85,
                        "weight": 0.6,
                        "provenance": [
                            {
                                "source": "project lead",
                                "context": "status meeting",
                                "condition": "verbal update",
                            }
                        ],
                        "basis": ["first-party project role"],
                    },
                ),
            ),
        )
        await store.remember(
            memory,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        page, total = await store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="project lead",
        )

        self.assertEqual(total, 1)
        self.assertEqual(page, [memory])

    async def test_diagnostics_round_trip(self) -> None:
        store = SurrealDiagnosticStore(self.runtime.database)
        observation = DiagnosticObservation(
            component="surreal_storage",
            operation="round_trip",
            implementation={"engine": "surrealdb"},
        )

        await store.record(observation)

        self.assertEqual(await store.read(), [observation])

    async def test_provider_factory_builds_surreal_bundle(self) -> None:
        settings = Settings(
            storage_provider="surreal",
            surrealdb_uri="mem://",
            surrealdb_namespace="factory",
            surrealdb_database="cognitive_mind",
        )
        storage = await create_storage(settings)
        try:
            mind = CognitiveMind(identity=MindIdentity(self_name="Factory Mind"))
            await storage.mind.initialize(mind)
            self.assertEqual(await storage.mind.load(), mind)
        finally:
            await storage.runtime.close()


if __name__ == "__main__":
    unittest.main()
