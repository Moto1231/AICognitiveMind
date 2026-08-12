from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


class MemoryClass(StrEnum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    IDENTITY = "identity"
    REFLECTIVE = "reflective"


class CognitiveActor(StrEnum):
    HOST = "host"
    CONSCIOUS_WORKSPACE = "conscious_workspace"
    SUBCONSCIOUS_LAYER = "subconscious_layer"
    CONSCIOUS_MEMORY_STEWARD = "conscious_memory_steward"
    SUBCONSCIOUS_MEMORY_STEWARD = "subconscious_memory_steward"
    REFLECTION_STEWARD = "reflection_steward"
    VALUES_STEWARD = "values_steward"
    KNOWLEDGE_STEWARD = "knowledge_steward"
    REASONING_ENGINE = "reasoning_engine"


class EventType(StrEnum):
    BEING_CREATED = "being_created"
    HOST_MESSAGE_RECEIVED = "host_message_received"
    REASONING_PROPOSED = "reasoning_proposed"
    RESPONSE_EXPRESSED = "response_expressed"
    MEMORY_PROPOSED = "memory_proposed"
    REFLECTION_PROPOSED = "reflection_proposed"
    IDENTITY_REVISION_PROPOSED = "identity_revision_proposed"


class Being(BaseModel):
    being_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=120)
    host_id: str = Field(min_length=1, max_length=200)
    identity_version: int = Field(default=1, ge=1)
    values: tuple[str, ...] = ()
    created_at: datetime = Field(default_factory=utc_now)


class CognitiveEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    being_id: UUID
    event_type: EventType
    source: CognitiveActor
    recorded_by: CognitiveActor
    payload: dict[str, Any]
    occurred_at: datetime = Field(default_factory=utc_now)
    correlation_id: UUID = Field(default_factory=uuid4)
    causation_id: UUID | None = None
    schema_version: int = Field(default=1, ge=1)


class ReasoningRequest(BaseModel):
    being: Being
    host_message: str = Field(min_length=1)
    correlation_id: UUID


class ReasoningProposal(BaseModel):
    engine_id: str
    response_text: str
    model_name: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class InteractionResult(BaseModel):
    being_id: UUID
    response_text: str
    engine_id: str
    correlation_id: UUID
    event_ids: tuple[UUID, ...]

