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
from aicognitive_mind.knowledge import DirectKnowledgeSynthesizer, KnowledgeSynthesizer
from aicognitive_mind.storage import JournalStore, MemoryStore


PROTOTYPE_CONTRADICTION_EPSILON = 0.05


class EvidenceAssessment(BaseModel):
    proposition: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)

    @property
    def support(self) -> float:
        return self.confidence * self.weight


class ContradictionAdjudication(BaseModel):
    resolved: bool
    preferred_proposition: str | None = None
    support_delta: float = Field(ge=0.0)
    clarification_required: bool = False


def adjudicate_contradiction(
    first: EvidenceAssessment,
    second: EvidenceAssessment,
    epsilon: float = PROTOTYPE_CONTRADICTION_EPSILON,
) -> ContradictionAdjudication:
    """Apply ADR 0008 without collapsing confidence and weight in storage."""
    if epsilon < 0.0:
        raise ValueError("epsilon must be non-negative")

    delta = abs(first.support - second.support)
    if delta <= epsilon:
        return ContradictionAdjudication(
            resolved=False,
            support_delta=delta,
            clarification_required=True,
        )

    preferred = first if first.support > second.support else second
    return ContradictionAdjudication(
        resolved=True,
        preferred_proposition=preferred.proposition,
        support_delta=delta,
        clarification_required=False,
    )


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
_CALL_ADAPTER: TypeAdapter[MemoryStewardCall] = TypeAdapter(MemoryStewardCall)


class MemoryBrief(BaseModel):
    focus: str
    identity_context: dict[str, Any]
    durable_memory: tuple[DurableMemory, ...] = ()
    prior_experience: tuple[JournalEntry, ...] = ()
    current_evidence: tuple[ResearchObservation, ...] = ()
    summary: str


class MemoryRecallTrace(BaseModel):
    """Compact recall result safe to persist without recursively embedding history."""

    focus: str
    summary: str
    durable_memory_count: int = Field(ge=0)
    prior_experience_count: int = Field(ge=0)
    current_evidence_count: int = Field(ge=0)


class MemoryDecision(BaseModel):
    accepted: bool
    reason: str
    memory: DurableMemory | None = None


class MemoryStewardTrace(BaseModel):
    recalled_context: MemoryRecallTrace
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
        current_speaker: str | None = None,
        synthesizer: KnowledgeSynthesizer | None = None,
        synthesis_instructions: str = "",
        recall_limit: int = 6,
    ) -> None:
        self._mind = mind
        self._input_text = input_text
        self._memory = memory
        self._journal = journal
        self._current_speaker = current_speaker
        self._synthesizer = synthesizer or DirectKnowledgeSynthesizer()
        self._synthesis_instructions = synthesis_instructions
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
        # Keep the model-facing contract flat. Small local models commonly fail to
        # call tools whose schemas use Pydantic's nested $defs/oneOf representation.
        # The discriminated Pydantic adapter below remains the authority that
        # validates each action and its required fields.
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["recall", "consider_evidence", "propose_memory"],
                    "description": "The Memory Steward operation to perform.",
                },
                "focus": {
                    "type": "string",
                    "description": "Required for recall: what related memory to retrieve.",
                },
                "query": {
                    "type": "string",
                    "description": "Required for consider_evidence: the research question.",
                },
                "response": {
                    "type": "string",
                    "description": "Required for consider_evidence: the research result.",
                },
                "articles": {
                    "type": "array",
                    "description": "Optional supporting article references.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "relevant_content": {"type": "string"},
                        },
                        "required": ["title", "url", "relevant_content"],
                    },
                },
                "memory_class": {
                    "type": "string",
                    "enum": [
                        "working",
                        "episodic",
                        "semantic",
                        "procedural",
                        "identity",
                        "reflective",
                    ],
                    "description": "Required for propose_memory.",
                },
                "content": {
                    "type": "string",
                    "description": "Required for propose_memory: the stable learning.",
                },
                "associations": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional concepts associated with the memory.",
                },
                "grounding": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Required for propose_memory: evidence supporting it.",
                },
            },
            "required": ["action"],
        }

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
            self._brief = await self._build_brief(
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
            recalled_context=MemoryRecallTrace(
                focus=brief.focus,
                summary=brief.summary,
                durable_memory_count=len(brief.durable_memory),
                prior_experience_count=len(brief.prior_experience),
                current_evidence_count=len(brief.current_evidence),
            ),
            evidence_considered=tuple(self._evidence),
            memory_decisions=tuple(self._decisions),
        )

    async def _recall(self, requested_focus: str) -> MemoryBrief:
        memories = await self._memory.read()
        experiences = _scope_experiences_to_speaker(
            await self._journal.read(),
            self._input_text,
            self._current_speaker,
        )
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
        ranked_experiences = _rank_experiences(
            experiences,
            expanded_tokens,
            self._recall_limit,
        )
        self._brief = await self._build_brief(
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

    async def _build_brief(
        self,
        focus: str,
        memories: tuple[DurableMemory, ...],
        experiences: tuple[JournalEntry, ...],
    ) -> MemoryBrief:
        # Individual memories and journal experiences remain evidence. The summary is
        # synthesized knowledge and is the only recalled content passed into the
        # Conscious Workspace system prompt.
        evidence = tuple(
            [memory.content for memory in memories]
            + [_experience_knowledge(entry) for entry in experiences]
            + [observation.response for observation in self._evidence]
        )
        summary = await self._synthesizer.synthesize(
            mind=self._mind,
            focus=focus,
            evidence=tuple(item for item in evidence if item),
            instructions=self._synthesis_instructions,
        )

        return MemoryBrief(
            focus=focus,
            identity_context=self._mind.identity.model_dump(mode="json"),
            durable_memory=memories,
            prior_experience=experiences,
            current_evidence=tuple(self._evidence),
            summary=summary,
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

_QUESTION_PREFIXES = (
    "am ",
    "are ",
    "can ",
    "could ",
    "did ",
    "do ",
    "does ",
    "has ",
    "have ",
    "how ",
    "is ",
    "should ",
    "was ",
    "were ",
    "what ",
    "when ",
    "where ",
    "which ",
    "who ",
    "why ",
    "will ",
    "would ",
)


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+(?:[.-][a-z0-9]+)*", text.casefold())
        if len(token) > 2 and token not in _STOP_WORDS
    }


def _score(focus_tokens: set[str], value: object) -> int:
    text = _experience_search_text(value) if isinstance(value, JournalEntry) else _as_text(value)
    return len(focus_tokens & _tokens(text))


def _rank[T](items: list[T], focus_tokens: set[str], limit: int) -> list[T]:
    scored = [(_score(focus_tokens, item), position, item) for position, item in enumerate(items)]
    ranked = sorted(scored, key=lambda row: (row[0], row[1]), reverse=True)
    related = [item for score, _, item in ranked if score > 0]
    return related[:limit]


def _has_first_person_reference(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return bool({"i", "me", "my", "mine"}.intersection(normalized.split()))


def _has_unresolved_third_person_reference(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return bool(
        {
            "he",
            "him",
            "his",
            "she",
            "her",
            "hers",
            "they",
            "them",
            "their",
            "theirs",
        }.intersection(normalized.split())
    )


def _experience_speaker(entry: JournalEntry) -> str | None:
    input_value = entry.experience.get("input")
    if not isinstance(input_value, dict):
        return None
    speaker = input_value.get("speaker")
    if not isinstance(speaker, str):
        return None
    normalized = speaker.strip()
    return normalized or None


def _experience_resolved_subject(entry: JournalEntry) -> str | None:
    input_value = entry.experience.get("input")
    if not isinstance(input_value, dict):
        return None
    subject = input_value.get("resolved_subject")
    if not isinstance(subject, str):
        return None
    normalized = subject.strip()
    return normalized or None


def _scope_experiences_to_speaker(
    items: list[JournalEntry],
    focus: str,
    current_speaker: str | None,
) -> list[JournalEntry]:
    """Prevent first-person evidence from one speaker being applied to another."""
    speaker = (current_speaker or "").strip().casefold()
    if (
        not speaker
        or speaker == "unknown"
        or not _has_first_person_reference(focus)
    ):
        return items

    scoped: list[JournalEntry] = []
    for item in items:
        input_text = _experience_input_text(item)

        # A third-person pronoun is not an identity by itself. It becomes admissible
        # person-specific evidence only when the originating experience preserved the
        # subject that working context had already resolved at that moment.
        if _has_unresolved_third_person_reference(input_text):
            resolved_subject = _experience_resolved_subject(item)
            if resolved_subject is None or resolved_subject.casefold() != speaker:
                continue

        if not _has_first_person_reference(input_text):
            scoped.append(item)
            continue

        evidence_speaker = _experience_speaker(item)
        if evidence_speaker is not None and evidence_speaker.casefold() == speaker:
            scoped.append(item)
    return scoped


def _rank_experiences(
    items: list[JournalEntry],
    focus_tokens: set[str],
    limit: int,
) -> list[JournalEntry]:
    """Rank fact-bearing experiences; prior questions have zero evidence weight."""
    scored = [
        (_score(focus_tokens, item), position, item)
        for position, item in enumerate(items)
        if _experience_evidence_weight(item) > 0
    ]
    ranked = sorted(scored, key=lambda row: (row[0], row[1]), reverse=True)
    related: list[JournalEntry] = []
    seen_inputs: set[str] = set()
    for score, _, item in ranked:
        if score <= 0:
            continue
        dedupe_key = _normalized_experience_input(item)
        if dedupe_key and dedupe_key in seen_inputs:
            continue
        if dedupe_key:
            seen_inputs.add(dedupe_key)
        related.append(item)
        if len(related) >= limit:
            break
    return related


def _as_text(value: object) -> str:
    if isinstance(value, BaseModel):
        return _as_text(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return " ".join(f"{key} {_as_text(item)}" for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return " ".join(_as_text(item) for item in value)
    return str(value)


def _experience_input_text(entry: JournalEntry) -> str:
    experience = entry.experience
    if isinstance(experience, dict):
        input_value = experience.get("input")
        if isinstance(input_value, dict):
            content = input_value.get("content")
            if isinstance(content, str):
                return content.strip()
    return ""


def _experience_search_text(entry: JournalEntry) -> str:
    """Return only human-visible interaction content for associative recall scoring."""
    experience = entry.experience
    parts: list[str] = []
    if isinstance(experience, dict):
        for key in ("input", "expression"):
            value = experience.get(key)
            if isinstance(value, dict):
                content = value.get("content")
                if isinstance(content, str):
                    parts.append(content)
    return " ".join(parts) or entry.kind.value


def _experience_evidence_weight(entry: JournalEntry) -> int:
    """Questions guide retrieval but provide no evidence for knowledge synthesis."""
    input_text = _experience_input_text(entry)
    return 0 if _looks_like_question(input_text) else 1


def _looks_like_question(text: str) -> bool:
    normalized = " ".join(text.casefold().split())
    return normalized.endswith("?") or normalized.startswith(_QUESTION_PREFIXES)


def _normalized_experience_input(entry: JournalEntry) -> str:
    input_text = _experience_input_text(entry).casefold()
    return re.sub(r"[^a-z0-9]+", " ", input_text).strip()


def _experience_knowledge(entry: JournalEntry) -> str:
    """Extract human-provided evidence while preserving any resolved person reference."""
    input_text = _experience_input_text(entry)
    resolved_subject = _experience_resolved_subject(entry)
    if (
        input_text
        and resolved_subject is not None
        and _has_unresolved_third_person_reference(input_text)
    ):
        return f"Resolved subject: {resolved_subject}. {input_text}"
    return input_text or _experience_search_text(entry)


def _derived_associations(content: str) -> list[str]:
    return sorted(_tokens(content), key=lambda token: (-len(token), token))[:8]
