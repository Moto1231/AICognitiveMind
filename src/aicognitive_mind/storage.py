from __future__ import annotations

from copy import deepcopy
from typing import Protocol
from uuid import UUID

from aicognitive_mind.domain import Being, CognitiveEvent
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy


class BeingStore(Protocol):
    async def create(self, being: Being) -> Being: ...

    async def get(self, being_id: UUID) -> Being | None: ...


class EventStore(Protocol):
    async def append(self, event: CognitiveEvent) -> CognitiveEvent: ...

    async def list_for_being(self, being_id: UUID) -> list[CognitiveEvent]: ...


class InMemoryBeingStore:
    def __init__(self) -> None:
        self._beings: dict[UUID, Being] = {}

    async def create(self, being: Being) -> Being:
        self._beings[being.being_id] = deepcopy(being)
        return deepcopy(being)

    async def get(self, being_id: UUID) -> Being | None:
        being = self._beings.get(being_id)
        return deepcopy(being) if being else None


class InMemoryEventStore:
    def __init__(self, policy: PermissionPolicy | None = None) -> None:
        self._events: list[CognitiveEvent] = []
        self._policy = policy or PermissionPolicy()

    async def append(self, event: CognitiveEvent) -> CognitiveEvent:
        self._policy.assert_allowed(event.recorded_by, CognitiveOperation.APPEND_EVENT)
        stored = deepcopy(event)
        self._events.append(stored)
        return deepcopy(stored)

    async def list_for_being(self, being_id: UUID) -> list[CognitiveEvent]:
        return [deepcopy(event) for event in self._events if event.being_id == being_id]

