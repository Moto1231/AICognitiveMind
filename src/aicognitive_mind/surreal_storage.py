from __future__ import annotations

from typing import Any

from surrealdb import AsyncSurreal

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    FoundationalMemory,
    JournalEntry,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import MindAlreadyInitializedError


class SurrealRuntime:
    """SurrealDB runtime supporting remote and embedded database URLs."""

    def __init__(
        self,
        uri: str,
        namespace: str,
        database_name: str,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        resolved_username = username.strip() if username and username.strip() else None
        resolved_password = password if password else None
        if (resolved_username is None) != (resolved_password is None):
            raise ValueError("SurrealDB username and password must be supplied together")
        self.database: Any = AsyncSurreal(uri)
        self._namespace = namespace
        self._database_name = database_name
        self._username = resolved_username
        self._password = resolved_password

    async def initialize(self) -> None:
        await self.database.connect()
        if self._username is not None and self._password is not None:
            await self.database.signin(
                {"username": self._username, "password": self._password}
            )
        await self.database.use(self._namespace, self._database_name)
        await self.ping()

    async def ping(self) -> None:
        await self.database.version()

    async def close(self) -> None:
        await self.database.close()


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise RuntimeError(f"Unexpected SurrealDB record result: {type(value).__name__}")


def _document(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "id"}


class SurrealMindStore:
    """Stores exactly one root cognitive document for this deployment."""

    def __init__(self, database: Any) -> None:
        self._database = database

    async def initialize(self, mind: CognitiveMind) -> CognitiveMind:
        records = _records(await self._database.select("mind"))
        if records:
            raise MindAlreadyInitializedError("This instance already contains its mind")
        await self._database.create("mind", mind.model_dump(mode="json"))
        return mind

    async def load(self) -> CognitiveMind | None:
        records = _records(await self._database.select("mind"))
        if not records:
            return None
        return CognitiveMind.model_validate(_document(records[0]))


class SurrealFoundationStore:
    """Governed foundational memory with append-only version history."""

    def __init__(self, database: Any) -> None:
        self._database = database

    async def seed(self, key: str, content: str) -> FoundationalMemory:
        history = await self.read_history(key)
        if history:
            return history[-1]
        record = FoundationalMemory(
            key=key,
            version=1,
            content=content,
            changed_by="bootstrap",
        )
        await self._database.create("foundation", record.model_dump(mode="json"))
        return record

    async def revise(
        self,
        key: str,
        content: str,
        changed_by: str,
    ) -> FoundationalMemory:
        records = _records(await self._database.select("foundation"))
        matching = [record for record in records if record.get("key") == key]
        next_version = max((int(record.get("version", 0)) for record in matching), default=0) + 1

        for record in matching:
            if record.get("active") is True and "id" in record:
                updated = _document(record)
                updated["active"] = False
                await self._database.update(record["id"], updated)

        revised = FoundationalMemory(
            key=key,
            version=next_version,
            content=content,
            changed_by=changed_by,
        )
        await self._database.create("foundation", revised.model_dump(mode="json"))
        return revised

    async def load_active(self, key: str) -> FoundationalMemory | None:
        history = await self.read_history(key)
        active = [record for record in history if record.active]
        return active[-1] if active else None

    async def read_history(self, key: str) -> list[FoundationalMemory]:
        records = _records(await self._database.select("foundation"))
        matching = [
            FoundationalMemory.model_validate(_document(record))
            for record in records
            if record.get("key") == key
        ]
        return sorted(matching, key=lambda record: record.version)


class SurrealJournalStore:
    """Append/read-only cognitive journal with no domain keys or references."""

    def __init__(
        self,
        database: Any,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._database = database
        self._policy = policy or PermissionPolicy()

    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        await self._database.create("journal", entry.model_dump(mode="json"))
        return entry

    async def read(self) -> list[JournalEntry]:
        records = _records(await self._database.select("journal"))
        entries = [JournalEntry.model_validate(_document(record)) for record in records]
        return sorted(entries, key=lambda entry: entry.occurred_at)


class SurrealDiagnosticStore:
    """Implementation observations deliberately isolated from cognitive documents."""

    def __init__(self, database: Any) -> None:
        self._database = database

    async def record(self, observation: DiagnosticObservation) -> None:
        await self._database.create("diagnostics", observation.model_dump(mode="json"))

    async def read(self) -> list[DiagnosticObservation]:
        records = _records(await self._database.select("diagnostics"))
        observations = [
            DiagnosticObservation.model_validate(_document(record)) for record in records
        ]
        return sorted(observations, key=lambda observation: observation.observed_at)


class SurrealMemoryStore:
    """Whole durable memories, curated by a Memory Steward without domain keys."""

    def __init__(
        self,
        database: Any,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._database = database
        self._policy = policy or PermissionPolicy()

    async def remember(
        self,
        memory: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        await self._database.create("memory", memory.model_dump(mode="json"))
        return memory

    async def read(self) -> list[DurableMemory]:
        records = _records(await self._database.select("memory"))
        memories = [DurableMemory.model_validate(_document(record)) for record in records]
        return sorted(memories, key=lambda memory: memory.formed_at)
