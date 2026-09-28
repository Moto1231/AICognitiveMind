"""Subconscious sleep-cycle consolidation for one persistent Cognitive Mind.

Sleep does not rewrite evidence. It reviews the accumulated journal and durable
memory, records recurring signals, and allows only the subconscious Memory
Steward to materialize grounded pattern memories.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
import re

from pydantic import BaseModel, Field

from aicognitive_mind.domain import (
    CognitiveActor,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
)
from aicognitive_mind.storage import JournalStore, MemoryStore


_STOP_WORDS = {
    "about", "after", "again", "also", "and", "are", "before", "but", "can",
    "could", "for", "from", "have", "into", "not", "our", "that", "the",
    "their", "then", "this", "was", "what", "when", "where", "which", "with",
    "would", "you", "your", "user", "human", "content", "source", "input",
    "response", "memory", "steward", "context",
}


class SleepPattern(BaseModel):
    association: str
    durable_memory_count: int = Field(ge=2)
    evidence: tuple[str, ...]


class SleepReport(BaseModel):
    started_at: datetime
    journal_entries_reviewed: int
    durable_memories_reviewed: int
    recurring_journal_signals: tuple[str, ...] = ()
    patterns: tuple[SleepPattern, ...] = ()
    consolidated_memories: tuple[str, ...] = ()


class SleepConsolidator:
    """Bounded, deterministic subconscious consolidation.

    V1 deliberately discovers only patterns supported by repeated evidence.
    It never changes identity, deletes raw experience, or promotes a one-off
    observation into durable knowledge.
    """

    def __init__(
        self,
        *,
        journal: JournalStore,
        memory: MemoryStore,
        minimum_pattern_memories: int = 2,
        minimum_journal_occurrences: int = 3,
        max_patterns: int = 12,
    ) -> None:
        self._journal = journal
        self._memory = memory
        self._minimum_pattern_memories = minimum_pattern_memories
        self._minimum_journal_occurrences = minimum_journal_occurrences
        self._max_patterns = max_patterns

    async def sleep(self, *, started_at: datetime | None = None) -> SleepReport:
        timestamp = started_at or datetime.now(UTC)
        journal = await self._journal.read()
        memories = await self._memory.read()

        association_evidence: dict[str, list[DurableMemory]] = {}
        # Consolidation products are outputs, not fresh evidence for the next
        # sleep pass. Excluding them prevents recursive self-reinforcement.
        source_memories = [
            item
            for item in memories
            if "sleep consolidation" not in {
                association.casefold() for association in item.associations
            }
        ]
        for item in source_memories:
            for association in item.associations:
                key = association.strip().casefold()
                if key:
                    association_evidence.setdefault(key, []).append(item)

        patterns: list[SleepPattern] = []
        for association, evidence in association_evidence.items():
            distinct = _distinct_memories(evidence)
            if len(distinct) < self._minimum_pattern_memories:
                continue
            patterns.append(
                SleepPattern(
                    association=association,
                    durable_memory_count=len(distinct),
                    evidence=tuple(item.content for item in distinct[:6]),
                )
            )
        patterns.sort(key=lambda p: (-p.durable_memory_count, p.association))
        patterns = patterns[: self._max_patterns]

        journal_signals = _recurring_journal_signals(
            journal,
            minimum_occurrences=self._minimum_journal_occurrences,
            limit=self._max_patterns,
        )

        existing = {item.content.casefold() for item in memories}
        consolidated: list[str] = []
        for pattern in patterns:
            content = (
                f"Sleep consolidation recognized a recurring association: "
                f"{pattern.association} appears across "
                f"{pattern.durable_memory_count} distinct durable memories."
            )
            if content.casefold() in existing:
                continue
            await self._memory.remember(
                DurableMemory(
                    memory_class=MemoryClass.REFLECTIVE,
                    content=content,
                    associations=(
                        "sleep consolidation",
                        "pattern recognition",
                        pattern.association,
                    ),
                    grounding=pattern.evidence,
                ),
                recorded_by=CognitiveActor.SUBCONSCIOUS_MEMORY_STEWARD,
            )
            existing.add(content.casefold())
            consolidated.append(content)

        report = SleepReport(
            started_at=timestamp,
            journal_entries_reviewed=len(journal),
            durable_memories_reviewed=len(memories),
            recurring_journal_signals=journal_signals,
            patterns=tuple(patterns),
            consolidated_memories=tuple(consolidated),
        )
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                occurred_at=timestamp,
                experience={
                    "source": CognitiveActor.SUBCONSCIOUS_LAYER.value,
                    "phase": "sleep_consolidation",
                    "report": report.model_dump(mode="json"),
                },
            ),
            recorded_by=CognitiveActor.SUBCONSCIOUS_MEMORY_STEWARD,
        )
        return report


def _distinct_memories(items: list[DurableMemory]) -> list[DurableMemory]:
    seen: set[tuple[str, datetime]] = set()
    result: list[DurableMemory] = []
    for item in items:
        key = (item.content.casefold(), item.formed_at)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _recurring_journal_signals(
    entries: list[JournalEntry],
    *,
    minimum_occurrences: int,
    limit: int,
) -> tuple[str, ...]:
    per_entry: Counter[str] = Counter()
    for entry in entries:
        text = _journal_text(entry)
        per_entry.update(set(_tokens(text)))
    return tuple(
        token
        for token, count in sorted(
            per_entry.items(),
            key=lambda item: (-item[1], item[0]),
        )
        if count >= minimum_occurrences
    )[:limit]


def _journal_text(entry: JournalEntry) -> str:
    experience = entry.experience
    parts = [
        experience.get("input", {}).get("content", ""),
        experience.get("expression", {}).get("content", ""),
        experience.get("before", {}).get("content", ""),
        experience.get("after", {}).get("content", ""),
    ]
    return " ".join(str(part) for part in parts if part)


def _tokens(text: str) -> tuple[str, ...]:
    return tuple(
        token
        for token in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.casefold())
        if len(token) > 3 and token not in _STOP_WORDS
    )
