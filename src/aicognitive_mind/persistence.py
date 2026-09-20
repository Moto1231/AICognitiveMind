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
    runtime: StorageRuntime
    mind: MindStore
    journal: JournalStore
    memory: MemoryStore
    diagnostics: DiagnosticStore
    evidence: EvidenceStore


async def create_storage(settings: Settings) -> StorageBundle:
    provider = settings.storage_provider.lower()

    if provider == "mongo":
        if (
            os.getenv("RENDER", "").lower() == "true"
            and settings.mongodb_uri == "mongodb://mongodb:27017"
        ):
            raise RuntimeError(
                "MONGODB_URI is not configured for Render. "
                "Set the Atlas connection string in the Render service Environment."
            )
        runtime = MongoRuntime(settings.mongodb_uri, settings.mongodb_database)
        await runtime.initialize()
        return StorageBundle(
            runtime=runtime,
            mind=MongoMindStore(runtime.database),
            journal=MongoJournalStore(runtime.database),
            memory=MongoMemoryStore(runtime.database),
            diagnostics=MongoDiagnosticStore(runtime.database),
            evidence=MongoEvidenceStore(runtime.database),
        )

    if provider == "surreal":
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
        )
        await runtime.initialize()
        return StorageBundle(
            runtime=runtime,
            mind=SurrealMindStore(runtime.database),
            journal=SurrealJournalStore(runtime.database),
            memory=SurrealMemoryStore(runtime.database),
            diagnostics=SurrealDiagnosticStore(runtime.database),
            evidence=SurrealEvidenceStore(runtime.database),
        )

    raise RuntimeError("STORAGE_PROVIDER must be one of: mongo, surreal")
