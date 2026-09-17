from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    FoundationalMemory,
    JournalEntry,
    WorkingMemory,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy


class MindAlreadyInitializedError(RuntimeError):
    pass


class MindStore(Protocol):
    async def initialize(self, mind: CognitiveMind) -> CognitiveMind: ...

    async def load(self) -> CognitiveMind | None: ...


class FoundationReader(Protocol):
    async def load_active(self, key: str) -> FoundationalMemory | None: ...


class FoundationStore(FoundationReader, Protocol):
    async def seed(self, key: str, content: str) -> FoundationalMemory: ...

    async def revise(
        self,
        key: str,
        content: str,
        changed_by: str,
    ) -> FoundationalMemory: ...

    async def read_history(self, key: str) -> list[FoundationalMemory]: ...


class JournalStore(Protocol):
    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry: ...

    async def read(self) -> list[JournalEntry]: ...


class DiagnosticStore(Protocol):
    async def record(self, observation: DiagnosticObservation) -> None: ...

    async def read(self) -> list[DiagnosticObservation]: ...


class MemoryStore(Protocol):
    async def remember(
        self,
        memory: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory: ...

    async def read(self) -> list[DurableMemory]: ...


class WorkingMemoryStore(Protocol):
    async def load(self) -> WorkingMemory: ...

    async def save(
        self,
        memory: WorkingMemory,
        recorded_by: CognitiveActor,
    ) -> WorkingMemory: ...

    async def clear(self, recorded_by: CognitiveActor) -> WorkingMemory: ...


class InMemoryMindStore:
    def __init__(self) -> None:
        self._mind: CognitiveMind | None = None

    async def initialize(self, mind: CognitiveMind) -> CognitiveMind:
        if self._mind is not None:
            raise MindAlreadyInitializedError("This instance already contains its mind")
        self._mind = deepcopy(mind)
        return deepcopy(mind)

    async def load(self) -> CognitiveMind | None:
        return deepcopy(self._mind)


class InMemoryFoundationStore:
    def __init__(self) -> None:
        self._records: list[FoundationalMemory] = []

    async def seed(self, key: str, content: str) -> FoundationalMemory:
        existing = await self.load_active(key)
        if existing is not None:
            return existing
        record = FoundationalMemory(
            key=key,
            version=1,
            content=content,
            changed_by="bootstrap",
        )
        self._records.append(record)
        return deepcopy(record)

    async def revise(
        self,
        key: str,
        content: str,
        changed_by: str,
    ) -> FoundationalMemory:
        history = await self.read_history(key)
        next_version = history[-1].version + 1 if history else 1
        for index, record in enumerate(self._records):
            if record.key == key and record.active:
                self._records[index] = record.model_copy(update={"active": False})
        revised = FoundationalMemory(
            key=key,
            version=next_version,
            content=content,
            changed_by=changed_by,
        )
        self._records.append(revised)
        return deepcopy(revised)

    async def load_active(self, key: str) -> FoundationalMemory | None:
        active = [record for record in self._records if record.key == key and record.active]
        if not active:
            return None
        return deepcopy(max(active, key=lambda record: record.version))

    async def read_history(self, key: str) -> list[FoundationalMemory]:
        records = sorted(
            (record for record in self._records if record.key == key),
            key=lambda record: record.version,
        )
        return deepcopy(records)


class InMemoryJournalStore:
    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self._entries: list[JournalEntry] = []
        self._policy = policy or PermissionPolicy()

    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        stored = deepcopy(entry)
        self._entries.append(stored)
        return deepcopy(stored)

    async def read(self) -> list[JournalEntry]:
        return deepcopy(self._entries)


class InMemoryDiagnosticStore:
    def __init__(self) -> None:
        self._observations: list[DiagnosticObservation] = []

    async def record(self, observation: DiagnosticObservation) -> None:
        self._observations.append(deepcopy(observation))

    async def read(self) -> list[DiagnosticObservation]:
        return deepcopy(self._observations)


class InMemoryMemoryStore:
    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self._memories: list[DurableMemory] = []
        self._policy = policy or PermissionPolicy()

    async def remember(
        self,
        memory: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        stored = deepcopy(memory)
        self._memories.append(stored)
        return deepcopy(stored)

    async def read(self) -> list[DurableMemory]:
        return deepcopy(self._memories)


class InMemoryWorkingMemoryStore:
    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self._memory = WorkingMemory()
        self._policy = policy or PermissionPolicy()

    async def load(self) -> WorkingMemory:
        return deepcopy(self._memory)

    async def save(
        self,
        memory: WorkingMemory,
        recorded_by: CognitiveActor,
    ) -> WorkingMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_WORKING_MEMORY)
        self._memory = deepcopy(memory)
        return deepcopy(self._memory)

    async def clear(self, recorded_by: CognitiveActor) -> WorkingMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.CLEAR_WORKING_MEMORY)
        self._memory = WorkingMemory()
        return deepcopy(self._memory)
