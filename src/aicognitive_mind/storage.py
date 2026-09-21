# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Protocol

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    SensoryEvidenceArtifact,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy


class MindAlreadyInitializedError(RuntimeError):
    pass


class MindStore(Protocol):
    async def initialize(self, mind: CognitiveMind) -> CognitiveMind: ...

    async def load(self) -> CognitiveMind | None: ...

    async def replace_exact(
        self,
        original: CognitiveMind,
        replacement: CognitiveMind,
        recorded_by: CognitiveActor,
    ) -> CognitiveMind | None: ...


class JournalStore(Protocol):
    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry: ...

    async def read(self) -> list[JournalEntry]: ...

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[list[JournalEntry], int]: ...

    async def find_exact(
        self,
        *,
        kind: str,
        occurred_at: datetime,
    ) -> JournalEntry | None: ...


class EvidenceStore(Protocol):
    async def preserve(self, artifact: SensoryEvidenceArtifact) -> SensoryEvidenceArtifact: ...

    async def read(self) -> list[SensoryEvidenceArtifact]: ...

    async def find_exact(
        self,
        *,
        sha256: str,
        captured_at: datetime,
    ) -> SensoryEvidenceArtifact | None: ...


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
        formed_from: datetime | None = None,
        formed_to: datetime | None = None,
    ) -> tuple[list[DurableMemory], int]: ...

    async def replace_exact(
        self,
        original: DurableMemory,
        replacement: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory | None: ...


def _searchable_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(
            f"{key} {_searchable_text(item)}" for key, item in value.items()
        )
    if isinstance(value, (list, tuple, set)):
        return " ".join(_searchable_text(item) for item in value)
    if hasattr(value, "model_dump"):
        return _searchable_text(value.model_dump(mode="json"))
    return str(value)


def _journal_search_text(entry: JournalEntry) -> str:
    experience = entry.experience
    values = [
        experience.get("input", {}).get("content", ""),
        experience.get("expression", {}).get("content", ""),
        experience.get("before", {}).get("content", ""),
        experience.get("after", {}).get("content", ""),
        experience.get("before", {}).get("self_name", ""),
        experience.get("after", {}).get("self_name", ""),
        experience.get("self_name", ""),
        experience.get("subject", ""),
        experience.get("attribute", ""),
        _searchable_text(experience.get("scope")),
        experience.get("phase", ""),
        experience.get("from_value", ""),
        experience.get("to_value", ""),
        experience.get("status", ""),
        experience.get("deliberation_revision", ""),
        experience.get("relationship", ""),
        experience.get("existing_value", ""),
        experience.get("existing_scope", ""),
        experience.get("proposed_value", ""),
        experience.get("proposed_scope", ""),
        _searchable_text(experience.get("basis", [])),
        _searchable_text(experience.get("existing_evidence", [])),
        _searchable_text(experience.get("proposed_evidence", [])),
        _searchable_text(experience.get("readiness_basis", [])),
        _searchable_text(experience.get("candidate_evidence", [])),
        _searchable_text(experience.get("superseded_evidence", [])),
        experience.get("competing_values", {}).get("existing", ""),
        experience.get("competing_values", {}).get("proposed", ""),
        experience.get("evidence", {}).get("existing", ""),
        experience.get("evidence", {}).get("proposed", ""),
        _searchable_text(experience.get("appraisals", {})),
        _searchable_text(experience.get("deliberation", {})),
        _searchable_text(experience.get("current_evidence", [])),
        _searchable_text(experience.get("evidence", {})),
        " ".join(str(value) for value in experience.get("foundational_values", [])),
    ]
    return " ".join(str(value) for value in values if value).lower()


def _journal_matches(
    entry: JournalEntry,
    *,
    kind: str | None,
    search: str | None,
    occurred_from: datetime | None,
    occurred_to: datetime | None,
) -> bool:
    if kind and entry.kind.value != kind:
        return False
    if search and search.lower() not in _journal_search_text(entry):
        return False
    if occurred_from and entry.occurred_at < occurred_from:
        return False
    if occurred_to and entry.occurred_at > occurred_to:
        return False
    return True


def _memory_matches(
    memory: DurableMemory,
    *,
    memory_class: str | None,
    search: str | None,
    association: str | None,
    grounding: str | None,
    formed_from: datetime | None,
    formed_to: datetime | None,
) -> bool:
    if memory_class and memory.memory_class.value != memory_class:
        return False
    if search:
        searchable = " ".join(
            [
                memory.content,
                *memory.associations,
                *memory.grounding,
                _searchable_text(memory.artifacts),
            ]
        ).lower()
        if search.lower() not in searchable:
            return False
    if association and not any(
        association.lower() in value.lower() for value in memory.associations
    ):
        return False
    if grounding and not any(
        grounding.lower() in value.lower() for value in memory.grounding
    ):
        return False
    if formed_from and memory.formed_at < formed_from:
        return False
    if formed_to and memory.formed_at > formed_to:
        return False
    return True


class InMemoryMindStore:
    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self._mind: CognitiveMind | None = None
        self._policy = policy or PermissionPolicy()

    async def initialize(self, mind: CognitiveMind) -> CognitiveMind:
        if self._mind is not None:
            raise MindAlreadyInitializedError("This instance already contains its mind")
        self._mind = deepcopy(mind)
        return deepcopy(mind)

    async def load(self) -> CognitiveMind | None:
        return deepcopy(self._mind)

    async def replace_exact(
        self,
        original: CognitiveMind,
        replacement: CognitiveMind,
        recorded_by: CognitiveActor,
    ) -> CognitiveMind | None:
        self._policy.assert_allowed(
            recorded_by,
            CognitiveOperation.APPROVE_IDENTITY_REVISION,
        )
        if self._mind != original:
            return None
        self._mind = deepcopy(replacement)
        return deepcopy(replacement)


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

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[list[JournalEntry], int]:
        matching = [
            entry
            for entry in self._entries
            if _journal_matches(
                entry,
                kind=kind,
                search=search,
                occurred_from=occurred_from,
                occurred_to=occurred_to,
            )
        ]
        matching.sort(key=lambda entry: entry.occurred_at, reverse=newest_first)
        return deepcopy(matching[offset : offset + limit]), len(matching)

    async def find_exact(
        self,
        *,
        kind: str,
        occurred_at: datetime,
    ) -> JournalEntry | None:
        for entry in self._entries:
            if entry.kind.value == kind and entry.occurred_at == occurred_at:
                return deepcopy(entry)
        return None


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
        formed_from: datetime | None = None,
        formed_to: datetime | None = None,
    ) -> tuple[list[DurableMemory], int]:
        matching = [
            memory
            for memory in self._memories
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
        return deepcopy(matching[offset : offset + limit]), len(matching)

    async def replace_exact(
        self,
        original: DurableMemory,
        replacement: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory | None:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        for index, existing in enumerate(self._memories):
            if existing == original:
                stored = deepcopy(replacement)
                self._memories[index] = stored
                return deepcopy(stored)
        return None


class InMemoryEvidenceStore:
    def __init__(self) -> None:
        self._artifacts: list[SensoryEvidenceArtifact] = []

    async def preserve(self, artifact: SensoryEvidenceArtifact) -> SensoryEvidenceArtifact:
        for existing in self._artifacts:
            if existing.sha256 == artifact.sha256 and existing.captured_at == artifact.captured_at:
                return deepcopy(existing)
        stored = deepcopy(artifact)
        self._artifacts.append(stored)
        return deepcopy(stored)

    async def read(self) -> list[SensoryEvidenceArtifact]:
        return deepcopy(self._artifacts)

    async def find_exact(
        self,
        *,
        sha256: str,
        captured_at: datetime,
    ) -> SensoryEvidenceArtifact | None:
        for artifact in self._artifacts:
            if artifact.sha256 == sha256 and artifact.captured_at == captured_at:
                return deepcopy(artifact)
        return None
