from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DurableMemory,
    JournalEntry,
    MemoryClass,
)
from aicognitive_mind.storage import JournalStore, MemoryStore


class ArticleReference(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    relevant_content: str = Field(min_length=1)


class ResearchObservation(BaseModel):
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    articles: tuple[ArticleReference, ...] = ()


class RecallCall(BaseModel):
    action: Literal["recall"]
    focus: str = Field(min_length=1)


class ConsiderEvidenceCall(BaseModel):
    action: Literal["consider_evidence"]
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    articles: tuple[ArticleReference, ...] = ()


class ProposeMemoryCall(BaseModel):
    action: Literal["propose_memory"]
    memory_class: MemoryClass
    content: str = Field(min_length=1)
    associations: tuple[str, ...] = ()
    grounding: tuple[str, ...] = Field(min_length=1)


MemoryStewardCall = Annotated[
    RecallCall | ConsiderEvidenceCall | ProposeMemoryCall,
    Field(discriminator="action"),
]
_CALL_ADAPTER = TypeAdapter(MemoryStewardCall)


class MemoryBrief(BaseModel):
    focus: str
    identity_context: dict[str, Any]
    durable_memory: tuple[DurableMemory, ...] = ()
    prior_experience: tuple[JournalEntry, ...] = ()
    current_evidence: tuple[ResearchObservation, ...] = ()
    summary: str


class MemoryDecision(BaseModel):
    accepted: bool
    reason: str
    memory: DurableMemory | None = None


class MemoryStewardTrace(BaseModel):
    recalled_context: MemoryBrief
    evidence_considered: tuple[ResearchObservation, ...] = ()
    memory_decisions: tuple[MemoryDecision, ...] = ()


class MemoryStewardNotConsultedError(RuntimeError):
    pass


class MemoryStewardTool:
    """Interaction-scoped doorway to an independent Conscious Memory Steward."""

    def __init__(
        self,
        mind: CognitiveMind,
        input_text: str,
        memory: MemoryStore,
        journal: JournalStore,
        recall_limit: int = 6,
    ) -> None:
        self._mind = mind
        self._input_text = input_text
        self._memory = memory
        self._journal = journal
        self._recall_limit = recall_limit
        self._brief: MemoryBrief | None = None
        self._evidence: list[ResearchObservation] = []
        self._decisions: list[MemoryDecision] = []
        self._pending: list[DurableMemory] = []
        self._completed = False

    @property
    def name(self) -> str:
        return "memory_steward"

    @property
    def description(self) -> str:
        return (
            "Consult the independent Conscious Memory Steward. Recall related memory before "
            "reasoning, submit material research evidence, or propose stable learning for the "
            "Steward to accept or reject. This tool does not expose storage identifiers."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return _CALL_ADAPTER.json_schema()

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self._completed:
            raise RuntimeError("This Memory Steward interaction is already complete")

        call = _CALL_ADAPTER.validate_python(arguments)
        if isinstance(call, RecallCall):
            brief = await self._recall(call.focus)
            return {"status": "recalled", "context": brief.model_dump(mode="json")}

        brief = self._require_recall()
        if isinstance(call, ConsiderEvidenceCall):
            observation = ResearchObservation(
                query=call.query,
                response=call.response,
                articles=call.articles,
            )
            self._evidence.append(observation)
            self._brief = self._build_brief(
                focus=brief.focus,
                memories=brief.durable_memory,
                experiences=brief.prior_experience,
            )
            return {
                "status": "evidence_considered",
                "context": self._brief.model_dump(mode="json"),
            }

        decision = await self._consider_memory(call)
        self._decisions.append(decision)
        return {"status": "memory_considered", **decision.model_dump(mode="json")}

    async def complete(self) -> MemoryStewardTrace:
        brief = self._require_recall()
        if self._completed:
            raise RuntimeError("This Memory Steward interaction is already complete")

        for memory in self._pending:
            await self._memory.remember(
                memory,
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
        self._completed = True
        return MemoryStewardTrace(
            recalled_context=brief,
            evidence_considered=tuple(self._evidence),
            memory_decisions=tuple(self._decisions),
        )

    async def _recall(self, requested_focus: str) -> MemoryBrief:
        memories = await self._memory.read()
        experiences = await self._journal.read()
        focus = f"{self._input_text}\n{requested_focus}"

        focus_tokens = _tokens(focus)
        directly_related = [
            memory
            for memory in memories
            if _score(focus_tokens, _as_text(memory)) > 0
        ]
        expanded_tokens = set(focus_tokens)
        for memory in directly_related:
            expanded_tokens.update(_tokens(" ".join(memory.associations)))

        ranked_memories = _rank(memories, expanded_tokens, self._recall_limit)
        ranked_experiences = _rank(experiences, expanded_tokens, self._recall_limit)
        self._brief = self._build_brief(
            focus=self._input_text,
            memories=tuple(ranked_memories),
            experiences=tuple(ranked_experiences),
        )
        return self._brief

    async def _consider_memory(self, call: ProposeMemoryCall) -> MemoryDecision:
        if call.memory_class not in {
            MemoryClass.SEMANTIC,
            MemoryClass.PROCEDURAL,
            MemoryClass.REFLECTIVE,
        }:
            return MemoryDecision(
                accepted=False,
                reason=(
                    f"{call.memory_class.value} memory is outside this V0.1 Steward's "
                    "authority; episodic experience is journaled automatically and identity "
                    "or values require constitutional governance."
                ),
            )

        existing = [*await self._memory.read(), *self._pending]
        if any(memory.content.casefold() == call.content.casefold() for memory in existing):
            return MemoryDecision(
                accepted=False,
                reason="An equivalent durable memory already exists.",
            )

        associations = call.associations or tuple(_derived_associations(call.content))
        memory = DurableMemory(
            memory_class=call.memory_class,
            content=call.content,
            associations=associations,
            grounding=call.grounding,
        )
        self._pending.append(memory)
        return MemoryDecision(
            accepted=True,
            reason="Accepted by the Conscious Memory Steward for commit with this experience.",
            memory=memory,
        )

    def _build_brief(
        self,
        focus: str,
        memories: tuple[DurableMemory, ...],
        experiences: tuple[JournalEntry, ...],
    ) -> MemoryBrief:
        parts: list[str] = []
        if memories:
            parts.append(
                "Established memory: " + " | ".join(memory.content for memory in memories)
            )
        if experiences:
            parts.append(
                "Related prior experience: "
                + " | ".join(_experience_excerpt(entry) for entry in experiences)
            )
        if self._evidence:
            parts.append(
                "Current research evidence: "
                + " | ".join(observation.response for observation in self._evidence)
            )
        if not parts:
            parts.append("No materially related durable memory or prior experience was found.")

        return MemoryBrief(
            focus=focus,
            identity_context=self._mind.identity.model_dump(mode="json"),
            durable_memory=memories,
            prior_experience=experiences,
            current_evidence=tuple(self._evidence),
            summary="\n".join(parts),
        )

    def _require_recall(self) -> MemoryBrief:
        if self._brief is None:
            raise MemoryStewardNotConsultedError(
                "The reasoning engine must consult memory before continuing"
            )
        return self._brief


_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "before",
    "but",
    "can",
    "could",
    "for",
    "from",
    "have",
    "how",
    "into",
    "its",
    "not",
    "our",
    "that",
    "the",
    "their",
    "them",
    "then",
    "this",
    "was",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "you",
    "your",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.casefold())
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _score(focus_tokens: set[str], value: object) -> int:
    return len(focus_tokens & _tokens(_as_text(value)))


def _rank[T](items: list[T], focus_tokens: set[str], limit: int) -> list[T]:
    scored = [(_score(focus_tokens, item), position, item) for position, item in enumerate(items)]
    ranked = sorted(scored, key=lambda row: (row[0], row[1]), reverse=True)
    related = [item for score, _, item in ranked if score > 0]
    return related[:limit]


def _as_text(value: object) -> str:
    if isinstance(value, BaseModel):
        return _as_text(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return " ".join(f"{key} {_as_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(item) for item in value)
    return str(value)


def _experience_excerpt(entry: JournalEntry) -> str:
    text = _as_text(entry.experience)
    return text if len(text) <= 280 else f"{text[:277]}..."


def _derived_associations(content: str) -> list[str]:
    return sorted(_tokens(content), key=lambda token: (-len(token), token))[:8]
