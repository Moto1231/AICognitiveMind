"""Transient resolver for people currently perceived by Axiom's Body."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from aicognitive_mind.domain import SensoryEvidenceReference
from aicognitive_mind.presence import PersonIdentity, Presence


class PresenceResolver:
    """Owns transient presence state per Mind and Body session.

    It does not own durable person identity. Scope is supplied by the request
    boundary so two sessions (or Minds) cannot share a transient presence track.
    """

    def __init__(self) -> None:
        self._presences: dict[tuple[str, str, str], Presence] = {}

    @staticmethod
    def _key(scope: tuple[str, str], presence_key: str) -> tuple[str, str, str]:
        mind_id, session_id = (part.strip() for part in scope)
        if not mind_id or not session_id:
            raise ValueError("Presence scope requires a Mind and session")
        key = presence_key.strip()
        if not key:
            raise ValueError("presence_key must not be empty")
        return mind_id, session_id, key

    def observe(
        self,
        presence_key: str,
        *,
        evidence: SensoryEvidenceReference,
        observation: str,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> Presence:
        """Attach sensory evidence to one transient presence track."""
        key = self._key(scope, presence_key)
        current = self._presences.get(key)
        if current is None:
            current = Presence(
                first_observed_at=evidence.captured_at,
                last_observed_at=evidence.captured_at,
            )
        updated = current.with_evidence(evidence=evidence, observation=observation)
        self._presences[key] = updated
        return updated

    def mark_candidate(
        self,
        presence_key: str,
        person: PersonIdentity,
        *,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> Presence:
        key = self._key(scope, presence_key)
        current = self._require(key)
        updated = current.candidate(person)
        self._presences[key] = updated
        return updated

    def resolve(
        self,
        presence_key: str,
        person: PersonIdentity,
        *,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> Presence:
        key = self._key(scope, presence_key)
        current = self._require(key)
        updated = current.resolve(person)
        self._presences[key] = updated
        return updated

    def forget(
        self,
        presence_key: str,
        *,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> None:
        self._presences.pop(self._key(scope, presence_key), None)

    def expire_before(
        self,
        cutoff: datetime,
        *,
        scope: tuple[str, str] | None = None,
    ) -> tuple[str, ...]:
        expired = tuple(
            key
            for key, presence in self._presences.items()
            if presence.last_observed_at < cutoff
            and (scope is None or key[:2] == scope)
        )
        for key in expired:
            del self._presences[key]
        return tuple(key[2] for key in expired)

    def active(
        self,
        *,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> dict[str, Presence]:
        return {
            key[2]: presence
            for key, presence in self._presences.items()
            if key[:2] == scope
        }

    def context(
        self,
        *,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> dict[str, Any]:
        """Return bounded, raw-media-free context suitable for CognitiveCore."""
        present: list[dict[str, Any]] = []
        for (mind_id, session_id, key), presence in self._presences.items():
            if (mind_id, session_id) != scope:
                continue
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

    def _require(self, key: tuple[str, str, str]) -> Presence:
        try:
            return self._presences[key]
        except KeyError as exc:
            raise KeyError(f"Unknown presence: {key[2]}") from exc
