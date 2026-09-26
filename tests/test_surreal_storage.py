import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

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
    SensoryEvidenceArtifact,
)
from surrealdb import RecordID
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.permissions import CognitivePermissionError
from aicognitive_mind.storage import MindAlreadyInitializedError
from aicognitive_mind.surreal_storage import (
    SurrealDiagnosticStore,
    SurrealEvidenceStore,
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


    async def test_runtime_uses_database_scoped_credentials(self) -> None:
        class FakeDatabase:
            def __init__(self) -> None:
                self.credentials = None
                self.used = None

            async def connect(self) -> None:
                return None

            async def use(self, namespace: str, database: str) -> None:
                self.used = (namespace, database)

            async def signin(self, credentials: dict[str, str]) -> None:
                self.credentials = credentials

            async def version(self) -> str:
                return "test"

            async def query(
                self,
                _sql: str,
                _variables: dict | None = None,
            ) -> list:
                return []

            async def select(self, _record: object) -> None:
                return None

            async def create(
                self,
                _record: object,
                _value: dict,
            ) -> None:
                return None

            async def close(self) -> None:
                return None

        fake = FakeDatabase()
        with patch("aicognitive_mind.surreal_storage.AsyncSurreal", return_value=fake):
            runtime = SurrealRuntime(
                "wss://example.invalid",
                "mir_ai",
                "ai_cognitive_mind",
                "cognitive_mind_service",
                "secret",
                "database",
            )
            await runtime.initialize()
            await runtime.close()

        self.assertEqual(fake.used, ("mir_ai", "ai_cognitive_mind"))
        self.assertEqual(
            fake.credentials,
            {
                "namespace": "mir_ai",
                "database": "ai_cognitive_mind",
                "username": "cognitive_mind_service",
                "password": "secret",
            },
        )

    async def test_mind_round_trips_and_remains_singleton(self) -> None:
        store = SurrealMindStore(self.runtime.database)
        mind = CognitiveMind(identity=MindIdentity(self_name="Genesis"))

        created = await store.initialize(mind)
        loaded = await store.load()

        self.assertEqual(created, mind)
        self.assertEqual(loaded, mind)

        revised = mind.model_copy(
            update={
                "identity": mind.identity.model_copy(
                    update={"self_name": "Aster"}
                )
            }
        )
        replaced = await store.replace_exact(
            mind,
            revised,
            recorded_by=CognitiveActor.VALUES_STEWARD,
        )
        self.assertEqual(replaced, revised)
        self.assertEqual(await store.load(), revised)

        with self.assertRaises(CognitivePermissionError):
            await store.replace_exact(
                revised,
                mind,
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )

        with self.assertRaises(MindAlreadyInitializedError):
            await store.initialize(revised)

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

    async def test_belief_transition_searches_journal_and_memory_artifacts(self) -> None:
        journal = SurrealJournalStore(self.runtime.database)
        memory_store = SurrealMemoryStore(self.runtime.database)

        transition_entry = JournalEntry(
            kind=JournalKind.BELIEF_TRANSITION,
            experience={
                "source": "conscious_memory_steward",
                "subject": "deployment",
                "attribute": "date",
                "from_value": "October 1",
                "to_value": "October 8",
                "deliberation_revision": 2,
                "readiness_basis": ["candidate evidence is independently corroborated"],
                "candidate_evidence": ["The deployment date is October 8."],
                "superseded_evidence": ["The deployment date is October 1."],
                "status": "committed",
            },
        )
        await journal.append(
            transition_entry,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        page, total = await journal.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="October 8",
        )
        self.assertEqual(total, 1)
        self.assertEqual(page, [transition_entry])

        memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The deployment date is October 8.",
            grounding=("project lead update",),
            artifacts=(
                MemoryArtifact(
                    kind="semantic_interpretation",
                    payload={
                        "subject": "deployment",
                        "attribute": "date",
                        "value": "October 8",
                    },
                ),
                MemoryArtifact(
                    kind="belief_status",
                    payload={
                        "subject": "deployment",
                        "attribute": "date",
                        "value": "October 8",
                        "status": "current",
                        "current_value": "October 8",
                        "deliberation_revision": 2,
                    },
                ),
                MemoryArtifact(
                    kind="belief_transition",
                    payload={
                        "status": "committed",
                        "subject": "deployment",
                        "attribute": "date",
                        "from_value": "October 1",
                        "to_value": "October 8",
                        "deliberation_revision": 2,
                        "readiness_basis": ["candidate evidence is independently corroborated"],
                    },
                ),
            ),
        )
        await memory_store.remember(
            memory,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        memory_page, memory_total = await memory_store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="superseded",
        )
        self.assertEqual(memory_total, 0)

        current_page, current_total = await memory_store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="current",
        )
        self.assertEqual(current_total, 1)
        self.assertEqual(current_page, [memory])

    async def test_belief_reframe_searches_scopes_and_memory_artifacts(self) -> None:
        journal = SurrealJournalStore(self.runtime.database)
        memory_store = SurrealMemoryStore(self.runtime.database)

        reframe_entry = JournalEntry(
            kind=JournalKind.BELIEF_REFRAME,
            experience={
                "source": "conscious_memory_steward",
                "status": "committed",
                "subject": "service",
                "attribute": "owner",
                "relationship": "temporal",
                "existing_value": "Alice",
                "existing_scope": "before September 1",
                "proposed_value": "Bob",
                "proposed_scope": "on or after September 1",
                "deliberation_revision": 2,
                "basis": ["ownership changed on September 1"],
                "existing_evidence": ["The service owner is Alice."],
                "proposed_evidence": ["The service owner is Bob."],
            },
        )
        await journal.append(
            reframe_entry,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        page, total = await journal.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="before September 1",
        )
        self.assertEqual(total, 1)
        self.assertEqual(page, [reframe_entry])

        memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The service owner is Alice.",
            grounding=("original assignment",),
            artifacts=(
                MemoryArtifact(
                    kind="semantic_interpretation",
                    payload={
                        "subject": "service",
                        "attribute": "owner",
                        "value": "Alice",
                    },
                ),
                MemoryArtifact(
                    kind="scoped_belief",
                    payload={
                        "subject": "service",
                        "attribute": "owner",
                        "value": "Alice",
                        "scope": "before September 1",
                        "relationship": "temporal",
                        "status": "valid_in_scope",
                        "deliberation_revision": 2,
                    },
                ),
                MemoryArtifact(
                    kind="belief_reframe",
                    payload={
                        "status": "committed",
                        "subject": "service",
                        "attribute": "owner",
                        "relationship": "temporal",
                        "existing_value": "Alice",
                        "existing_scope": "before September 1",
                        "proposed_value": "Bob",
                        "proposed_scope": "on or after September 1",
                        "deliberation_revision": 2,
                        "basis": ["ownership changed on September 1"],
                    },
                ),
            ),
        )
        await memory_store.remember(
            memory,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        memory_page, memory_total = await memory_store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="before September 1",
        )
        self.assertEqual(memory_total, 1)
        self.assertEqual(memory_page, [memory])

    async def test_semantic_scope_is_searchable_in_journal_and_memory(self) -> None:
        journal = SurrealJournalStore(self.runtime.database)
        memory_store = SurrealMemoryStore(self.runtime.database)

        tension = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "phase": "detected",
                "status": "unresolved",
                "subject": "invoice",
                "attribute": "approval_route",
                "scope": {"kind": "contextual", "label": "Customer A"},
                "competing_values": {
                    "existing": "Alpha",
                    "proposed": "Gamma",
                },
            },
        )
        await journal.append(
            tension,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        page, total = await journal.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="Customer A",
        )
        self.assertEqual(total, 1)
        self.assertEqual(page, [tension])

        memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="Customer A approval route is Alpha.",
            grounding=("Customer A configuration",),
            artifacts=(
                MemoryArtifact(
                    kind="semantic_interpretation",
                    payload={
                        "subject": "invoice",
                        "attribute": "approval_route",
                        "value": "Alpha",
                        "scope": {
                            "kind": "contextual",
                            "label": "Customer A",
                        },
                    },
                ),
            ),
        )
        await memory_store.remember(
            memory,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        memory_page, memory_total = await memory_store.query_page(
            offset=0,
            limit=25,
            newest_first=True,
            search="Customer A",
        )
        self.assertEqual(memory_total, 1)
        self.assertEqual(memory_page, [memory])

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

    async def test_sensory_evidence_round_trips_by_content_hash_and_capture_time(self) -> None:
        store = SurrealEvidenceStore(self.runtime.database)
        captured_at = datetime(2026, 9, 20, 3, 0, tzinfo=UTC)
        artifact = SensoryEvidenceArtifact(
            captured_at=captured_at,
            modality="vision",
            source="browser-camera",
            media_type="image/jpeg",
            sha256="a" * 64,
            byte_length=4,
            payload_base64="anBlZw==",
            metadata={"width": 320, "height": 240},
        )

        preserved = await store.preserve(artifact)
        loaded = await store.find_exact(
            sha256=artifact.sha256,
            captured_at=captured_at,
        )

        self.assertEqual(preserved, artifact)
        self.assertEqual(loaded, artifact)

    async def test_provider_factory_exposes_evidence_store(self) -> None:
        settings = Settings(
            storage_provider="surreal",
            surrealdb_uri="mem://",
            surrealdb_namespace="evidence_factory",
            surrealdb_database="cognitive_mind",
        )
        storage = await create_storage(settings)
        try:
            artifact = SensoryEvidenceArtifact(
                modality="audio",
                source="browser-microphone",
                media_type="audio/webm",
                sha256="b" * 64,
                byte_length=5,
                payload_base64="YXVkaW8=",
            )
            await storage.evidence.preserve(artifact)
            loaded = await storage.evidence.find_exact(
                sha256=artifact.sha256,
                captured_at=artifact.captured_at,
            )
            self.assertEqual(loaded, artifact)
        finally:
            await storage.runtime.close()

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


    async def test_two_surreal_minds_are_storage_isolated(self) -> None:
        alpha_mind = SurrealMindStore(self.runtime.database, "alpha")
        beta_mind = SurrealMindStore(self.runtime.database, "beta")
        alpha_memory = SurrealMemoryStore(self.runtime.database, "alpha")
        beta_memory = SurrealMemoryStore(self.runtime.database, "beta")
        alpha_journal = SurrealJournalStore(self.runtime.database, "alpha")
        beta_journal = SurrealJournalStore(self.runtime.database, "beta")
        alpha_evidence = SurrealEvidenceStore(self.runtime.database, "alpha")
        beta_evidence = SurrealEvidenceStore(self.runtime.database, "beta")
        alpha_diagnostics = SurrealDiagnosticStore(self.runtime.database, "alpha")
        beta_diagnostics = SurrealDiagnosticStore(self.runtime.database, "beta")

        await alpha_mind.initialize(
            CognitiveMind(identity=MindIdentity(self_name="Alpha"))
        )
        await beta_mind.initialize(
            CognitiveMind(identity=MindIdentity(self_name="Beta"))
        )
        await alpha_memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="alpha-memory",
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        await beta_memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="beta-memory",
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        await alpha_journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={"input": {"content": "alpha-journal"}},
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await beta_journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={"input": {"content": "beta-journal"}},
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await alpha_diagnostics.record(
            DiagnosticObservation(
                component="alpha",
                operation="test",
                implementation={},
            )
        )
        await beta_diagnostics.record(
            DiagnosticObservation(
                component="beta",
                operation="test",
                implementation={},
            )
        )
        alpha_artifact = SensoryEvidenceArtifact(
            modality="vision",
            source="alpha-camera",
            media_type="image/png",
            sha256="c" * 64,
            byte_length=1,
            payload_base64="YQ==",
        )
        beta_artifact = SensoryEvidenceArtifact(
            modality="vision",
            source="beta-camera",
            media_type="image/png",
            sha256="d" * 64,
            byte_length=1,
            payload_base64="Yg==",
        )
        await alpha_evidence.preserve(alpha_artifact)
        await beta_evidence.preserve(beta_artifact)

        self.assertEqual((await alpha_mind.load()).identity.self_name, "Alpha")
        self.assertEqual((await beta_mind.load()).identity.self_name, "Beta")
        self.assertEqual(
            [memory.content for memory in await alpha_memory.read()],
            ["alpha-memory"],
        )
        self.assertEqual(
            [memory.content for memory in await beta_memory.read()],
            ["beta-memory"],
        )
        self.assertEqual(
            [
                entry.experience["input"]["content"]
                for entry in await alpha_journal.read()
            ],
            ["alpha-journal"],
        )
        self.assertEqual(
            [
                entry.experience["input"]["content"]
                for entry in await beta_journal.read()
            ],
            ["beta-journal"],
        )
        self.assertEqual(
            [item.component for item in await alpha_diagnostics.read()],
            ["alpha"],
        )
        self.assertEqual(
            [item.component for item in await beta_diagnostics.read()],
            ["beta"],
        )
        self.assertEqual(
            [item.source for item in await alpha_evidence.read()],
            ["alpha-camera"],
        )
        self.assertEqual(
            [item.source for item in await beta_evidence.read()],
            ["beta-camera"],
        )

    async def test_runtime_records_allow_same_key_for_two_minds(self) -> None:
        alpha = RuntimeRecords(SurrealMindStore(self.runtime.database, "alpha"))
        beta = RuntimeRecords(SurrealMindStore(self.runtime.database, "beta"))

        await alpha.create("shared-key", {"value": "alpha"})
        await beta.create("shared-key", {"value": "beta"})

        self.assertEqual(await alpha.get("shared-key"), {"value": "alpha"})
        self.assertEqual(await beta.get("shared-key"), {"value": "beta"})

    async def test_runtime_records_read_legacy_unscoped_account_for_any_root_mind(self) -> None:
        records = RuntimeRecords(SurrealMindStore(self.runtime.database, "root-v2"))
        key = "account_legacyhash"
        await self.runtime.database.create(
            RecordID("runtime_records", key),
            {
                "key": key,
                "kind": "account",
                "username": "legacy",
                "active": True,
            },
        )

        self.assertEqual(
            await records.get(key),
            {
                "kind": "account",
                "username": "legacy",
                "active": True,
            },
        )

    async def test_provider_factory_can_open_two_surreal_minds(self) -> None:
        settings = Settings(
            storage_provider="surreal",
            surrealdb_uri="mem://",
            surrealdb_namespace="multi_factory",
            surrealdb_database="cognitive_mind",
            axiom_mind_id="alpha",
        )
        alpha = await create_storage(settings, mind_id="alpha")
        try:
            await alpha.mind.initialize(
                CognitiveMind(identity=MindIdentity(self_name="Alpha"))
            )
            beta = await create_storage(settings, mind_id="beta")
            try:
                await beta.mind.initialize(
                    CognitiveMind(identity=MindIdentity(self_name="Beta"))
                )
                self.assertEqual(
                    (await alpha.mind.load()).identity.self_name,
                    "Alpha",
                )
                self.assertEqual(
                    (await beta.mind.load()).identity.self_name,
                    "Beta",
                )
            finally:
                await beta.runtime.close()
        finally:
            await alpha.runtime.close()


if __name__ == "__main__":
    unittest.main()
