"""Live multi-mind isolation verification for the active storage backend."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from aicognitive_mind.commit import backend
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
    SensoryEvidenceArtifact,
)
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.surreal_storage import (
    SurrealDiagnosticStore,
    SurrealEvidenceStore,
    SurrealJournalStore,
    SurrealMemoryStore,
    SurrealMindStore,
)


async def verify_live_tenancy(storage: Any) -> dict[str, Any]:
    """Create a temporary second Surreal mind, prove isolation, then delete it.

    This is a startup diagnostic against the actual configured database, not a
    unit-test double. It never mutates the active mind's cognitive documents.
    """
    kind, database = backend({"mind": storage.mind})
    if kind != "surreal":
        return {
            "status": "not_applicable",
            "provider": kind,
            "primary_mind_id": str(getattr(storage.mind, "mind_id", "root")),
        }

    primary_mind_id = str(getattr(storage.mind, "mind_id", "axiom"))
    probe_id = "__tenancy_probe_" + uuid4().hex
    marker = "tenancy-probe-" + uuid4().hex
    captured_at = datetime.now(UTC)

    probe_mind = SurrealMindStore(database, probe_id)
    probe_journal = SurrealJournalStore(database, probe_id)
    probe_memory = SurrealMemoryStore(database, probe_id)
    probe_diagnostics = SurrealDiagnosticStore(database, probe_id)
    probe_evidence = SurrealEvidenceStore(database, probe_id)
    probe_records = RuntimeRecords(probe_mind)
    primary_records = RuntimeRecords(storage.mind)

    try:
        await probe_mind.initialize(
            CognitiveMind(identity=MindIdentity(self_name="Tenancy Probe"))
        )
        memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content=marker,
            grounding=("live-tenancy-probe",),
        )
        await probe_memory.remember(
            memory,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        journal = JournalEntry(
            kind=JournalKind.CHECKPOINT,
            experience={"tenancy_probe": marker},
        )
        await probe_journal.append(
            journal,
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        diagnostic = DiagnosticObservation(
            component="tenancy_probe",
            operation="isolation",
            implementation={"marker": marker},
        )
        await probe_diagnostics.record(diagnostic)
        evidence = SensoryEvidenceArtifact(
            captured_at=captured_at,
            modality="diagnostic",
            source="tenancy-probe",
            media_type="application/octet-stream",
            sha256="0" * 64,
            byte_length=1,
            payload_base64="AA==",
            metadata={"marker": marker},
        )
        await probe_evidence.preserve(evidence)
        await probe_records.create("tenancy_probe", {"marker": marker})

        primary_mind = await storage.mind.load()
        primary_checks = {
            "mind": (
                primary_mind is not None
                and primary_mind.identity.self_name != "Tenancy Probe"
            ),
            "memory": all(
                item.content != marker
                for item in await storage.memory.read()
            ),
            "journal": all(
                item.experience.get("tenancy_probe") != marker
                for item in await storage.journal.read()
            ),
            "diagnostics": all(
                item.implementation.get("marker") != marker
                for item in await storage.diagnostics.read()
            ),
            "evidence": all(
                item.metadata.get("marker") != marker
                for item in await storage.evidence.read()
            ),
            "runtime_records": (
                await primary_records.get("tenancy_probe") is None
            ),
        }
        probe_checks = {
            "mind": (await probe_mind.load()) is not None,
            "memory": any(
                item.content == marker
                for item in await probe_memory.read()
            ),
            "journal": any(
                item.experience.get("tenancy_probe") == marker
                for item in await probe_journal.read()
            ),
            "diagnostics": any(
                item.implementation.get("marker") == marker
                for item in await probe_diagnostics.read()
            ),
            "evidence": any(
                item.metadata.get("marker") == marker
                for item in await probe_evidence.read()
            ),
            "runtime_records": (
                (await probe_records.get("tenancy_probe") or {}).get("marker")
                == marker
            ),
        }

        failed_primary = [
            name for name, passed in primary_checks.items() if not passed
        ]
        failed_probe = [
            name for name, passed in probe_checks.items() if not passed
        ]
        if failed_primary or failed_probe:
            raise RuntimeError(
                "Live SurrealDB tenancy isolation verification failed: "
                f"primary={failed_primary}, probe={failed_probe}"
            )

        return {
            "status": "passed",
            "provider": "surreal",
            "primary_mind_id": primary_mind_id,
            "probe_mind_id": probe_id,
            "verified_collections": [
                "mind",
                "memory",
                "journal",
                "diagnostics",
                "evidence",
                "runtime_records",
            ],
        }
    finally:
        # The probe must leave no second Mind or test artifacts behind.
        for table in (
            "mind",
            "memory",
            "journal",
            "diagnostics",
            "evidence",
            "runtime_records",
            "commit_receipts",
            "commit_state",
        ):
            await database.query(
                f"DELETE FROM {table} WHERE mind_id = $mind_id;",
                {"mind_id": probe_id},
            )
