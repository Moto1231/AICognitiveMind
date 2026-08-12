from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

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
    HUMAN = "human"
    CONSCIOUS_WORKSPACE = "conscious_workspace"
    SUBCONSCIOUS_LAYER = "subconscious_layer"
    CONSCIOUS_MEMORY_STEWARD = "conscious_memory_steward"
    SUBCONSCIOUS_MEMORY_STEWARD = "subconscious_memory_steward"
    REFLECTION_STEWARD = "reflection_steward"
    VALUES_STEWARD = "values_steward"
    KNOWLEDGE_STEWARD = "knowledge_steward"
    REASONING_ENGINE = "reasoning_engine"


class JournalKind(StrEnum):
    INITIALIZATION = "initialization"
    INTERACTION = "interaction"
    REFLECTION = "reflection"
    TENSION = "tension"


class MindIdentity(BaseModel):
    self_name: str = Field(min_length=1, max_length=120)
    foundational_values: tuple[str, ...] = ()
    commitments: tuple[str, ...] = ()
    relationships: tuple[dict[str, Any], ...] = ()


class CognitiveMind(BaseModel):
    """The one persistent mind owned by this application instance."""

    identity: MindIdentity
    developmental_state: str = "genesis"
    created_at: datetime = Field(default_factory=utc_now)


class JournalEntry(BaseModel):
    """A whole cognitive document, stored without domain identifiers."""

    kind: JournalKind
    occurred_at: datetime = Field(default_factory=utc_now)
    experience: dict[str, Any]


class DiagnosticObservation(BaseModel):
    """Implementation provenance kept outside identity and cognitive history."""

    observed_at: datetime = Field(default_factory=utc_now)
    component: str
    operation: str
    implementation: dict[str, Any]


class ReasoningRequest(BaseModel):
    mind: CognitiveMind
    input_text: str = Field(min_length=1)


class ReasoningProposal(BaseModel):
    response_text: str
    diagnostic: DiagnosticObservation


class InteractionResult(BaseModel):
    response_text: str
    occurred_at: datetime

