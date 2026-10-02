"""Durable, per-Mind person records linked to evidence-backed encounters.

Storage is injected: RuntimeRecords supplies the existing tenant-scoped persistence.
A presence key is ephemeral and never becomes a person's durable identity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from aicognitive_mind.domain import SensoryEvidenceReference
from aicognitive_mind.presence import PersonIdentity, Presence, PresenceResolution


class PersonEncounter(BaseModel):
    observed_at: datetime
    evidence: tuple[SensoryEvidenceReference, ...] = ()
    observations: tuple[str, ...] = ()


class KnownPerson(BaseModel):
    person_id: str = Field(min_length=1)
    identity: PersonIdentity
    encounters: tuple[PersonEncounter, ...] = ()


class PersonRegistry:
    """Persist known people using the Mind's existing scoped RuntimeRecords."""

    def __init__(self, records) -> None:
        self.records = records

    async def get(self, person_id: str) -> KnownPerson | None:
        record = await self.records.get("person_" + person_id)
        return KnownPerson.model_validate(record) if record else None

    async def remember(self, identity: PersonIdentity) -> KnownPerson:
        if not identity.grounding:
            raise ValueError("Persistent identity requires grounding")
        person = KnownPerson(person_id=uuid4().hex, identity=identity)
        await self.records.create("person_" + person.person_id, person.model_dump(mode="json"))
        return person

    async def link(self, person_id: str, presence: Presence) -> KnownPerson:
        """Commit a resolved encounter without discarding exact sensory references."""
        if presence.resolution != PresenceResolution.RESOLVED or presence.person is None:
            raise ValueError("Only resolved presences can be linked")
        if not presence.evidence:
            raise ValueError("Encounter requires sensory evidence")
        key = "person_" + person_id
        current = await self.records.get(key)
        if current is None:
            raise KeyError(f"Unknown person: {person_id}")
        person = KnownPerson.model_validate(current)
        # Explicit matching prevents accidental cross-person links based on a name.
        if presence.person != person.identity:
            raise ValueError("Resolved presence does not match stored identity")
        encounter = PersonEncounter(
            observed_at=presence.last_observed_at,
            evidence=tuple(item.evidence for item in presence.evidence),
            observations=tuple(item.observation for item in presence.evidence),
        )
        updated = person.model_copy(update={"encounters": (*person.encounters, encounter)})
        if not await self.records.replace(key, current, updated.model_dump(mode="json")):
            raise RuntimeError("Person record changed; retry with fresh state")
        return updated
