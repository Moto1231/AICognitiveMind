"""Evidence-grounded person identity and transient presence contracts.

A PersonIdentity is cognitive/social knowledge about a known person. It deliberately
has no database or application ID: storage identity is not person identity.

A Presence represents somebody currently perceived by the Body. Presence can remain
unresolved until evidence justifies associating it with a known person.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from aicognitive_mind.domain import SensoryEvidenceReference, utc_now


class PresenceResolution(StrEnum):
    UNKNOWN = "unknown"
    CANDIDATE = "candidate"
    RESOLVED = "resolved"


class PersonIdentity(BaseModel):
    """Evidence-backed social identity known by the Mind."""

    name: str = Field(min_length=1, max_length=120)
    aliases: tuple[str, ...] = ()
    relationship: str | None = Field(default=None, max_length=200)
    grounding: tuple[str, ...] = ()


class PresenceEvidence(BaseModel):
    """One sensory contribution to a presence resolution."""

    evidence: SensoryEvidenceReference
    observation: str = Field(min_length=1)
    modality: str = Field(min_length=1, max_length=40)


class Presence(BaseModel):
    """Transient state for a person currently perceived by the Body."""

    first_observed_at: datetime = Field(default_factory=utc_now)
    last_observed_at: datetime = Field(default_factory=utc_now)
    resolution: PresenceResolution = PresenceResolution.UNKNOWN
    person: PersonIdentity | None = None
    evidence: tuple[PresenceEvidence, ...] = ()

    def with_evidence(
        self,
        *,
        evidence: SensoryEvidenceReference,
        observation: str,
    ) -> "Presence":
        contribution = PresenceEvidence(
            evidence=evidence,
            observation=observation,
            modality=evidence.modality,
        )
        return self.model_copy(
            update={
                "last_observed_at": evidence.captured_at,
                "evidence": (*self.evidence, contribution),
            }
        )

    def candidate(self, person: PersonIdentity) -> "Presence":
        return self.model_copy(
            update={
                "resolution": PresenceResolution.CANDIDATE,
                "person": person,
            }
        )

    def resolve(self, person: PersonIdentity) -> "Presence":
        if not self.evidence:
            raise ValueError("Presence cannot resolve a person without sensory evidence")
        if not person.grounding:
            raise ValueError("Known person cannot resolve presence without identity grounding")
        return self.model_copy(
            update={
                "resolution": PresenceResolution.RESOLVED,
                "person": person,
            }
        )
