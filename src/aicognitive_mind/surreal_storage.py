from __future__ import annotations

from typing import Any

from surrealdb import AsyncSurreal

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import (
    MindAlreadyInitializedError,
    _journal_matches,
    _memory_matches,
)


class SurrealRuntime:
    """SurrealDB runtime supporting embedded and remote database URLs."""

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


class SurrealJournalStore:
    """Append/read-only cognitive journal behind the provider-neutral contract."""

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

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: Any = None,
        occurred_to: Any = None,
    ) -> tuple[list[JournalEntry], int]:
        entries = await self.read()
        matching = [
            entry
            for entry in entries
            if _journal_matches(
                entry,
                kind=kind,
                search=search,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
        ]
        matching.sort(key=lambda entry: entry.occurred_at, reverse=newest_first)
        return matching[offset : offset + limit], len(matching)

    async def find_exact(
        self,
        *,
        kind: str,
        occurred_at: Any,
    ) -> JournalEntry | None:
        for entry in await self.read():
            if entry.kind.value == kind and entry.occurred_at == occurred_at:
                return entry
        return None


class SurrealDiagnosticStore:
    """Implementation observations isolated from cognitive documents."""

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
    """Whole durable memories curated by the Memory Steward without domain IDs."""

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

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        memory_class: str | None = None,
        search: str | None = None,
        association: str | None = None,
        grounding: str | None = None,
        formed_from: Any = None,
        formed_to: Any = None,
    ) -> tuple[list[DurableMemory], int]:
        memories = await self.read()
        matching = [
            memory
            for memory in memories
            if _memory_matches(
                memory,
                memory_class=memory_class,
                search=search,
                association=association,
                grounding=grounding,
                formed_from=formed_from,
                formed_to=formed_to,
            )
        ]
        matching.sort(key=lambda memory: memory.formed_at, reverse=newest_first)
        return matching[offset : offset + limit], len(matching)

    async def replace_exact(
        self,
        original: DurableMemory,
        replacement: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory | None:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        records = _records(await self._database.select("memory"))
        for record in records:
            existing = DurableMemory.model_validate(_document(record))
            if existing == original and "id" in record:
                await self._database.update(
                    record["id"],
                    replacement.model_dump(mode="json"),
                )
                return replacement
        return None
