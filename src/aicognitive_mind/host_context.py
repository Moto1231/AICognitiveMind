"""Validated, volatile short-term context owned by an external reasoning host."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class HostParticipantContext(BaseModel):
    """Participant tracking that preserves uncertainty and its grounding."""

    participant_id: str = Field(min_length=1, max_length=80)
    name: str | None = Field(default=None, max_length=120)
    identity_status: Literal["unresolved", "candidate", "confirmed"] = "unresolved"
    presence_status: Literal["observed", "reported", "referenced", "unknown"] = "unknown"
    relationship: str | None = Field(default=None, max_length=200)
    grounding: tuple[str, ...] = Field(default=(), max_length=8)

    @model_validator(mode="after")
    def confirmed_identity_requires_grounding(self) -> HostParticipantContext:
        if self.identity_status == "confirmed" and (not self.name or not self.grounding):
            raise ValueError("Confirmed identity requires a name and explicit grounding")
        return self


class HostWorkingContext(BaseModel):
    """Session-local participant, topic, and reference state kept by the host."""

    summary: str = Field(default="", max_length=2000)
    participants: tuple[HostParticipantContext, ...] = Field(default=(), max_length=32)
    active_speaker: str | None = Field(default=None, max_length=80)
    addressee: str | None = Field(default=None, max_length=80)
    unresolved_references: tuple[str, ...] = Field(default=(), max_length=24)

    @model_validator(mode="after")
    def validate_participant_references(self) -> HostWorkingContext:
        participant_ids = [participant.participant_id for participant in self.participants]
        if len(participant_ids) != len(set(participant_ids)):
            raise ValueError("Participant IDs must be unique within a host session")
        known_ids = set(participant_ids)
        for reference in (self.active_speaker, self.addressee):
            if reference is not None and reference not in known_ids:
                raise ValueError("Speaker and addressee must reference a tracked participant")
        return self
