from __future__ import annotations

import re

from aicognitive_mind.domain import (
    CognitiveActor,
    InterlocutorContext,
    WorkingMemory,
    utc_now,
)
from aicognitive_mind.storage import WorkingMemoryStore


_NAME_TOKEN = r"[A-Za-z][A-Za-z'’-]*"
_EXPLICIT_IDENTITY_PATTERNS = (
    re.compile(
        rf"^\s*(?:i am|i'm|my name is)\s+"
        rf"({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,3}})"
        rf"(?=\s*(?:[,.!?]|$)|\s+(?:and|but)\b)",
        re.IGNORECASE,
    ),
    re.compile(
        rf"^\s*it'?s\s+({_NAME_TOKEN}(?:\s+{_NAME_TOKEN}){{0,3}})\s*[.!?]?\s*$",
        re.IGNORECASE,
    ),
)

_IDENTITY_REQUIRED_PATTERNS = (
    re.compile(r"\bwho\s+am\s+i\b", re.IGNORECASE),
    re.compile(
        r"\b(?:what|when|where|who|which)\s+(?:is|was|are|were)\s+my\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:do|did|can|could)\s+you\s+(?:know|remember|tell)\b[^?]*\bmy\b",
        re.IGNORECASE,
    ),
    re.compile(r"\btell\s+me\b[^?]*\bmy\b", re.IGNORECASE),
)


def explicit_interlocutor_identity(text: str) -> str | None:
    for pattern in _EXPLICIT_IDENTITY_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        name = " ".join(match.group(1).split()).strip(" .,!?:;")
        if name:
            return name
    return None


def requires_identified_interlocutor(text: str) -> bool:
    return any(pattern.search(text) is not None for pattern in _IDENTITY_REQUIRED_PATTERNS)


class WorkingMemoryManager:
    """Owns disposable present-tense context independently of the reasoning engine."""

    def __init__(self, store: WorkingMemoryStore) -> None:
        self._store = store

    async def observe_human_message(self, text: str) -> WorkingMemory:
        memory = await self._store.load()
        name = explicit_interlocutor_identity(text)
        if name is None:
            return memory

        updated = memory.model_copy(
            update={
                "current_interlocutor": InterlocutorContext(
                    name=name,
                    source="self_identification",
                    confidence=1.0,
                ),
                "updated_at": utc_now(),
            }
        )
        return await self._store.save(
            updated,
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )

    def needs_identity_resolution(self, text: str, memory: WorkingMemory) -> bool:
        return memory.current_interlocutor is None and requires_identified_interlocutor(text)

    def render_for_reasoning(self, memory: WorkingMemory) -> str:
        interlocutor = memory.current_interlocutor
        if interlocutor is None:
            return (
                "Current interlocutor: unknown. Do not attribute person-specific "
                "first-person facts to any known person."
            )
        return (
            f"Current interlocutor: {interlocutor.name}. "
            f"Identity source: {interlocutor.source}; "
            f"confidence: {interlocutor.confidence:.2f}. "
            "Resolve I/me/my from the human to this interlocutor for this working context only."
        )

    async def read(self) -> WorkingMemory:
        return await self._store.load()

    async def checkpoint(self) -> WorkingMemory:
        return await self._store.clear(
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
