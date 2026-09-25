from __future__ import annotations

from dataclasses import dataclass
import os
from typing import Protocol

from aicognitive_mind.config import Settings
from aicognitive_mind.mongo_storage import (
    MongoDiagnosticStore,
    MongoEvidenceStore,
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
    MongoRuntime,
)
from aicognitive_mind.storage import (
    DiagnosticStore,
    EvidenceStore,
    JournalStore,
    MemoryStore,
    MindStore,
)
class StorageRuntime(Protocol):
    async def initialize(self) -> None: ...
    async def ping(self) -> None: ...
    async def close(self) -> None: ...


@dataclass
class StorageBundle:
    mind_id: str
    runtime: StorageRuntime
    mind: MindStore
    journal: JournalStore
    memory: MemoryStore
    diagnostics: DiagnosticStore
    evidence: EvidenceStore


async def create_storage(
    settings: Settings,
    *,
    mind_id: str | None = None,
) -> StorageBundle:
    provider = settings.storage_provider.lower()
    resolved_mind_id = (mind_id or settings.axiom_mind_id).strip()
    if not resolved_mind_id:
        raise ValueError("mind_id must not be empty")

    if provider == "mongo":
        if (
            os.getenv("RENDER", "").lower() == "true"
            and settings.mongodb_uri == "mongodb://mongodb:27017"
        ):
            raise RuntimeError(
                "MONGODB_URI is not configured for Render. "
                "Set the Atlas connection string in the Render service Environment."
            )
        runtime = MongoRuntime(
            settings.mongodb_uri,
            settings.mongodb_database,
            legacy_mind_id=resolved_mind_id,
        )
        await runtime.initialize()
        return StorageBundle(
            mind_id=resolved_mind_id,
            runtime=runtime,
            mind=MongoMindStore(runtime.database, resolved_mind_id),
            journal=MongoJournalStore(runtime.database, resolved_mind_id),
            memory=MongoMemoryStore(runtime.database, resolved_mind_id),
            diagnostics=MongoDiagnosticStore(runtime.database, resolved_mind_id),
            evidence=MongoEvidenceStore(runtime.database, resolved_mind_id),
        )

    if provider == "surreal":
        if (
            os.getenv("RENDER", "").lower() == "true"
            and settings.surrealdb_uri == "surrealkv://.surreal/cognitive_mind"
        ):
            raise RuntimeError(
                "SURREALDB_URI is not configured for Render. "
                "Set the remote SurrealDB connection string in the Render service Environment."
            )

        from aicognitive_mind.surreal_storage import (
            SurrealDiagnosticStore,
            SurrealEvidenceStore,
            SurrealJournalStore,
            SurrealMemoryStore,
            SurrealMindStore,
            SurrealRuntime,
        )

        runtime = SurrealRuntime(
            settings.surrealdb_uri,
            settings.surrealdb_namespace,
            settings.surrealdb_database,
            settings.surrealdb_username,
            settings.surrealdb_password,
            settings.surrealdb_auth_level,
            legacy_mind_id=resolved_mind_id,
        )
        await runtime.initialize()
        return StorageBundle(
            mind_id=resolved_mind_id,
            runtime=runtime,
            mind=SurrealMindStore(runtime.database, resolved_mind_id),
            journal=SurrealJournalStore(runtime.database, resolved_mind_id),
            memory=SurrealMemoryStore(runtime.database, resolved_mind_id),
            diagnostics=SurrealDiagnosticStore(runtime.database, resolved_mind_id),
            evidence=SurrealEvidenceStore(runtime.database, resolved_mind_id),
        )

    raise RuntimeError("STORAGE_PROVIDER must be one of: mongo, surreal")
