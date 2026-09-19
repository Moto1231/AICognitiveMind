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

    async def test_journal_search_finds_deliberation_guidance(self) -> None:
        store = SurrealJournalStore(self.runtime.database)
        tension = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "status": "unresolved",
                "subject": "deployment",
                "attribute": "date",
                "competing_values": {
                    "existing": "October 1",
                    "proposed": "October 8",
                },
                "evidence": {
                    "existing": "The deployment date is October 1.",
                    "proposed": "The deployment date is October 8.",
                },
                "deliberation": {
                    "existing_support_count": 1,
                    "proposed_support_count": 1,
                    "provenance_relationship": "overlap_detected",
                    "existing_provenance_depth": 2,
                    "proposed_provenance_depth": 2,
                    "appraisal_gaps": [],
                    "context_observations": [],
                    "investigation_questions": [
                        "Trace the shared provenance upstream to determine whether the evidence is independent or repeated reporting."
                    ],
                },
            },
        )
        await store.append(
            tension,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        page, total = await store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="shared provenance",
        )

        self.assertEqual(total, 1)
        self.assertEqual(page, [tension])

        reassessment = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "phase": "reassessment",
                "status": "unresolved",
                "subject": "deployment",
                "attribute": "date",
                "competing_values": {
                    "existing": "October 1",
                    "proposed": "October 8",
                },
                "current_evidence": [
                    {
                        "query": "release calendar",
                        "response": "The release board lists October 8.",
                        "articles": [],
                        "appraisal": {
                            "confidence": 0.9,
                            "weight": 0.6,
                            "provenance": [
                                {
                                    "source": "release board",
                                    "context": "current calendar",
                                    "condition": "published",
                                }
                            ],
                            "basis": [],
                        },
                        "semantic_interpretation": {
                            "subject": "deployment",
                            "attribute": "date",
                            "value": "October 8",
                        },
                        "tension_finding": {
                            "subject": "deployment",
                            "attribute": "date",
                            "existing_value": "October 1",
                            "proposed_value": "October 8",
                            "provenance_independence": "verified_independent",
                            "temporal_relationship": "same_timeframe",
                            "contextual_relationship": "same_context",
                            "basis": ["independence verified"],
                        },
                    }
                ],
                "deliberation": {
                    "subject": "deployment",
                    "attribute": "date",
                    "existing_value": "October 1",
                    "proposed_value": "October 8",
                    "revision": 2,
                    "trigger": "current_evidence_reassessment",
                    "current_evidence_considered": 1,
                    "current_existing_support_count": 0,
                    "current_proposed_support_count": 1,
                    "existing_support_count": 1,
                    "proposed_support_count": 2,
                    "provenance_relationship": "no_overlap_observed",
                    "existing_provenance_depth": 1,
                    "proposed_provenance_depth": 1,
                    "appraisal_gaps": [],
                    "context_observations": [],
                    "investigation_questions": [
                        "Seek independent corroboration for the existing value."
                    ],
                    "resolution_readiness": {
                        "status": "candidate_ready",
                        "candidate_side": "proposed",
                        "candidate_value": "October 8",
                        "existing": {
                            "value": "October 1",
                            "support_count": 1,
                            "appraised_support_count": 1,
                            "distinct_immediate_sources": 1,
                            "confidence_floor": 0.55,
                            "confidence_ceiling": 0.55,
                            "weight_floor": 0.4,
                            "weight_ceiling": 0.4,
                        },
                        "proposed": {
                            "value": "October 8",
                            "support_count": 2,
                            "appraised_support_count": 2,
                            "distinct_immediate_sources": 2,
                            "confidence_floor": 0.8,
                            "confidence_ceiling": 0.9,
                            "weight_floor": 0.7,
                            "weight_ceiling": 0.75,
                        },
                        "blockers": [],
                        "basis": ["candidate evidence is independently corroborated"],
                    },
                },
            },
        )
        await store.append(
            reassessment,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        evidence_page, evidence_total = await store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="release board",
        )
        self.assertEqual(evidence_total, 1)
        self.assertEqual(evidence_page, [reassessment])

        phase_page, phase_total = await store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="reassessment",
        )
        self.assertEqual(phase_total, 1)
        self.assertEqual(phase_page, [reassessment])

        ready_page, ready_total = await store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="candidate_ready",
        )
        self.assertEqual(ready_total, 1)
        self.assertEqual(ready_page, [reassessment])

        finding_page, finding_total = await store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="verified_independent",
        )
        self.assertEqual(finding_total, 1)
        self.assertEqual(finding_page, [reassessment])

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
