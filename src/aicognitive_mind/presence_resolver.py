"""Transient resolver for people currently perceived by Axiom's Body."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aicognitive_mind.domain import SensoryEvidenceReference
from aicognitive_mind.presence import PersonIdentity, Presence, PresenceResolution


class PresenceResolver:
    """Owns transient presence state; it does not own durable person identity."""

    def __init__(self) -> None:
        self._presences: dict[str, Presence] = {}

    def observe(
        self,
        presence_key: str,
        *,
        evidence: SensoryEvidenceReference,
        observation: str,
    ) -> Presence:
        """Attach sensory evidence to one transient presence track."""
        key = presence_key.strip()
        if not key:
            raise ValueError("presence_key must not be empty")

        current = self._presences.get(key)
        if current is None:
            current = Presence(
                first_observed_at=evidence.captured_at,
                last_observed_at=evidence.captured_at,
            )
        updated = current.with_evidence(evidence=evidence, observation=observation)
        self._presences[key] = updated
        return updated

    def mark_candidate(self, presence_key: str, person: PersonIdentity) -> Presence:
        current = self._require(presence_key)
        updated = current.candidate(person)
        self._presences[presence_key] = updated
        return updated

    def resolve(self, presence_key: str, person: PersonIdentity) -> Presence:
        current = self._require(presence_key)
        updated = current.resolve(person)
        self._presences[presence_key] = updated
        return updated

    def forget(self, presence_key: str) -> None:
        self._presences.pop(presence_key, None)

    def expire_before(self, cutoff: datetime) -> tuple[str, ...]:
        expired = tuple(
            key
            for key, presence in self._presences.items()
            if presence.last_observed_at < cutoff
        )
        for key in expired:
            del self._presences[key]
        return expired

    def active(self) -> dict[str, Presence]:
        return dict(self._presences)

    def context(self) -> dict[str, Any]:
        """Return bounded, raw-media-free context suitable for CognitiveCore."""
        present: list[dict[str, Any]] = []
        for key, presence in self._presences.items():
            item: dict[str, Any] = {
                "presence_key": key,
                "resolution": presence.resolution.value,
                "first_observed_at": presence.first_observed_at.isoformat(),
                "last_observed_at": presence.last_observed_at.isoformat(),
                "evidence_count": len(presence.evidence),
                "modalities": sorted({entry.modality for entry in presence.evidence}),
            }
            if presence.person is not None:
                item["person"] = {
                    "name": presence.person.name,
                    "aliases": list(presence.person.aliases),
                    "relationship": presence.person.relationship,
                }
            present.append(item)
        return {"present_people": present}

    def _require(self, presence_key: str) -> Presence:
        try:
            return self._presences[presence_key]
        except KeyError as exc:
            raise KeyError(f"Unknown presence: {presence_key}") from exc
