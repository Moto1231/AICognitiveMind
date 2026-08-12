from __future__ import annotations

from copy import deepcopy
from typing import Protocol

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    JournalEntry,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy


class MindAlreadyInitializedError(RuntimeError):
    pass


class MindStore(Protocol):
    async def initialize(self, mind: CognitiveMind) -> CognitiveMind: ...

    async def load(self) -> CognitiveMind | None: ...


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

