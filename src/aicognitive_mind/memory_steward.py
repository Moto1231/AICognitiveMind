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
from aicognitive_mind.evidence import (
    EffectiveScorecardEvaluator,
    EvidenceProvenanceHop,
    EvidenceScorecard,
    PriorPreservingScorecardEvaluator,
    RecursiveRecallBudget,
    RecursiveRecallState,
    adjudicate_contradiction,
    assess_evidence,
)
from aicognitive_mind.knowledge import DirectKnowledgeSynthesizer, KnowledgeSynthesizer
from aicognitive_mind.propositions import (
    BirthdayPropositionDetector,
    ClarificationRequest,
    PropositionDetector,
    PropositionEvidence,
    clarification_request,
    clarification_resolution_for_conflict,
    first_conflict,
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
_CALL_ADAPTER: TypeAdapter[MemoryStewardCall] = TypeAdapter(MemoryStewardCall)


class MemoryBrief(BaseModel):
    focus: str
    identity_context: dict[str, Any]
    durable_memory: tuple[DurableMemory, ...] = ()
    prior_experience: tuple[JournalEntry, ...] = ()
    current_evidence: tuple[ResearchObservation, ...] = ()
    summary: str
    clarification_question: str | None = None
    clarification_request: ClarificationRequest | None = None
    supporting_recall_focus: str | None = None
    recursive_recall_depth: int = Field(default=0, ge=0)
    evidence_items_examined: int = Field(default=0, ge=0)


class MemoryRecallTrace(BaseModel):
    """Compact recall result safe to persist without recursively embedding history."""

    focus: str
    summary: str
    clarification_question: str | None = None
    clarification_request: ClarificationRequest | None = None
    recursive_recall_depth: int = Field(default=0, ge=0)
    evidence_items_examined: int = Field(default=0, ge=0)
    durable_memory_count: int = Field(ge=0)
    prior_experience_count: int = Field(ge=0)
    current_evidence_count: int = Field(ge=0)


class MemoryDecision(BaseModel):
    accepted: bool
    reason: str
    memory: DurableMemory | None = None


async def consolidate_explicit_resolutions(
    memory_store: MemoryStore,
    experiences: tuple[JournalEntry, ...],
    *,
    additional_existing: tuple[DurableMemory, ...] = (),
) -> tuple[MemoryDecision, ...]:
    """Consolidate explicit human resolutions under Memory Steward authority."""
    existing = [*await memory_store.read(), *additional_existing]
    known_content = {memory.content.casefold() for memory in existing}
    decisions: list[MemoryDecision] = []

    for entry in experiences:
        resolution = _experience_clarification_resolution(entry)
        if resolution is None:
            continue

        subject, attribute, value, proposition = resolution
        if proposition.casefold() in known_content:
            continue

        durable = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content=proposition,
            associations=(subject, attribute, value),
            grounding=(
                "Explicit human clarification resolved a prior contradiction.",
                f"Literal clarification: {_experience_input_text(entry)}",
            ),
        )
        await memory_store.remember(
            durable,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        decisions.append(
            MemoryDecision(
                accepted=True,
                reason=(
                    "Consolidated an explicit clarification resolution into "
                    "durable semantic memory."
                ),
                memory=durable,
            )
        )
        known_content.add(proposition.casefold())

    return tuple(decisions)


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
        current_context: dict[str, Any] | None = None,
        scorecard_evaluator: EffectiveScorecardEvaluator | None = None,
        proposition_detector: PropositionDetector | None = None,
        synthesizer: KnowledgeSynthesizer | None = None,
        synthesis_instructions: str = "",
        recall_limit: int = 6,
        recursive_recall_budget: RecursiveRecallBudget | None = None,
    ) -> None:
        self._mind = mind
        self._input_text = input_text
        self._memory = memory
        self._journal = journal
        self._current_speaker = current_speaker
        self._current_context = dict(current_context or {})
        self._scorecard_evaluator = scorecard_evaluator or PriorPreservingScorecardEvaluator()
        self._proposition_detector = proposition_detector or BirthdayPropositionDetector()
        self._synthesizer = synthesizer or DirectKnowledgeSynthesizer()
        self._synthesis_instructions = synthesis_instructions
        self._recall_limit = recall_limit
        self._recursive_recall_budget = recursive_recall_budget or RecursiveRecallBudget()
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
                recall_state=RecursiveRecallState(
                    depth=brief.recursive_recall_depth,
                    evidence_items_examined=brief.evidence_items_examined,
                ),
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

        consolidation_decisions = await consolidate_explicit_resolutions(
            self._memory,
            brief.prior_experience,
            additional_existing=tuple(self._pending),
        )
        self._decisions.extend(consolidation_decisions)

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
                clarification_question=brief.clarification_question,
                clarification_request=brief.clarification_request,
                recursive_recall_depth=brief.recursive_recall_depth,
                evidence_items_examined=brief.evidence_items_examined,
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
        initial_state = RecursiveRecallState(
            depth=0,
            evidence_items_examined=len(ranked_memories) + len(ranked_experiences),
        )
        initial_brief = await self._build_brief(
            focus=self._input_text,
            memories=tuple(ranked_memories),
            experiences=tuple(ranked_experiences),
            recall_state=initial_state,
        )

        support_focus = initial_brief.supporting_recall_focus
        if (
            support_focus is not None
            and initial_state.depth < self._recursive_recall_budget.max_depth
            and initial_state.evidence_items_examined
            < self._recursive_recall_budget.max_evidence_items
        ):
            support_tokens = _tokens(support_focus)
            remaining_experiences = [
                item for item in experiences if item not in ranked_experiences
            ]
            remaining_capacity = (
                self._recursive_recall_budget.max_evidence_items
                - initial_state.evidence_items_examined
            )
            additional_experiences = _rank_experiences(
                remaining_experiences,
                support_tokens,
                min(self._recall_limit, remaining_capacity),
            )
            if additional_experiences:
                expanded_experiences = (
                    *ranked_experiences,
                    *additional_experiences,
                )
                expanded_state = RecursiveRecallState(
                    depth=initial_state.depth + 1,
                    evidence_items_examined=(
                        initial_state.evidence_items_examined
                        + len(additional_experiences)
                    ),
                )
                self._brief = await self._build_brief(
                    focus=self._input_text,
                    memories=tuple(ranked_memories),
                    experiences=tuple(expanded_experiences),
                    recall_state=expanded_state,
                )
                return self._brief

        self._brief = initial_brief
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
        recall_state: RecursiveRecallState | None = None,
    ) -> MemoryBrief:
        # Individual memories and journal experiences remain evidence. The summary is
        # synthesized knowledge and is the only recalled content passed into the
        # Conscious Workspace system prompt.
        state = recall_state or RecursiveRecallState(
            evidence_items_examined=len(memories) + len(experiences)
        )
        recalled_evidence = tuple(
            [memory.content for memory in memories]
            + [
                knowledge
                for entry in experiences
                if (knowledge := _experience_knowledge(entry))
            ]
            + [observation.response for observation in self._evidence]
        )
        evaluation_context = dict(self._current_context)
        if recalled_evidence:
            evaluation_context["recalled_evidence"] = recalled_evidence

        evidence_items: list[str] = []
        propositions: list[PropositionEvidence] = []
        for memory in memories:
            prior = EvidenceScorecard(
                confidence=memory.confidence,
                weight=memory.weight,
            )
            grounding_context = "; ".join(memory.grounding) or None
            memory_provenance = (
                EvidenceProvenanceHop(
                    source="long-term memory",
                    condition="Recalled durable memory.",
                    context=grounding_context,
                    scorecard=prior,
                ),
            )
            assessment = assess_evidence(
                proposition=memory.content,
                prior=prior,
                provenance=memory_provenance,
                current_speaker=self._current_speaker,
                current_context=evaluation_context,
                evaluator=self._scorecard_evaluator,
            )
            evidence_items.append(memory.content)
            evidence_items.append(_durable_memory_assessment(memory))
            evidence_items.append(_effective_assessment(assessment))
            propositions.extend(
                self._proposition_detector.detect(
                    memory.content,
                    speaker=None,
                    resolved_subject=None,
                    assessment=assessment,
                )
            )

        for entry in experiences:
            knowledge = _experience_knowledge(entry)
            if knowledge:
                evidence_items.append(knowledge)
            provenance_text = _experience_provenance(entry)
            if provenance_text:
                evidence_items.append(provenance_text)
            if knowledge:
                prior = EvidenceScorecard(confidence=0.5, weight=0.5)
                source = _experience_speaker(entry) or "human"
                resolved_subject = _experience_resolved_subject(entry)
                assessment = assess_evidence(
                    proposition=knowledge,
                    prior=prior,
                    provenance=(
                        EvidenceProvenanceHop(
                            source=source,
                            condition="Recalled journal experience.",
                            context=(
                                f"resolved_subject={resolved_subject}"
                                if resolved_subject is not None
                                else None
                            ),
                            scorecard=prior,
                        ),
                    ),
                    current_speaker=self._current_speaker,
                    current_context=evaluation_context,
                    evaluator=self._scorecard_evaluator,
                )
                evidence_items.append(_effective_assessment(assessment))
                clarification_resolution = _experience_clarification_resolution(entry)
                if clarification_resolution is not None:
                    subject, attribute, value, _ = clarification_resolution
                    propositions.append(
                        PropositionEvidence(
                            subject=subject,
                            attribute=attribute,
                            value=value,
                            assessment=assessment,
                            evidence_role="clarification_resolution",
                        )
                    )
                else:
                    propositions.extend(
                        self._proposition_detector.detect(
                            knowledge,
                            speaker=source,
                            resolved_subject=resolved_subject,
                            assessment=assessment,
                        )
                    )

        evidence_items.extend(observation.response for observation in self._evidence)
        current_context = _current_context_evidence(
            self._current_speaker,
            self._current_context,
        )
        if current_context and evidence_items:
            evidence_items.append(current_context)

        clarification_response: str | None = None
        clarification_details: ClarificationRequest | None = None
        supporting_recall_focus: str | None = None
        preferred_proposition: str | None = None
        contradiction = first_conflict(propositions)
        if contradiction is not None:
            first, second = contradiction
            explicit_resolution = clarification_resolution_for_conflict(
                propositions,
                first,
                second,
            )
            if explicit_resolution is not None:
                preferred_proposition = explicit_resolution.assessment.proposition
                evidence_items.append(
                    "Prototype contradiction adjudication: "
                    f"preferred={preferred_proposition}; "
                    "resolved_by=explicit_clarification"
                )
            else:
                adjudication = adjudicate_contradiction(
                    first.assessment,
                    second.assessment,
                )
                if adjudication.resolved:
                    preferred_proposition = adjudication.preferred_proposition
                    evidence_items.append(
                        "Prototype contradiction adjudication: "
                        f"preferred={preferred_proposition}; "
                        f"support_delta={adjudication.support_delta:.3f}"
                    )
                else:
                    supporting_recall_focus = f"{first.subject} {first.attribute}"
                    clarification_details = clarification_request(
                        first,
                        second,
                        self._current_speaker,
                    )
                    clarification_response = clarification_details.question
                    evidence_items.append(
                        "Prototype contradiction adjudication: unresolved; "
                        f"support_delta={adjudication.support_delta:.3f}; "
                        "clarification_required=true"
                    )

        evidence = tuple(evidence_items)
        summary = await self._synthesizer.synthesize(
            mind=self._mind,
            focus=focus,
            evidence=tuple(item for item in evidence if item),
            instructions=self._synthesis_instructions,
        )
        if preferred_proposition is not None:
            summary = (
                f"Adjudicated current knowledge: {preferred_proposition}\n"
                f"Supporting synthesis: {summary}"
            )

        return MemoryBrief(
            focus=focus,
            identity_context=self._mind.identity.model_dump(mode="json"),
            durable_memory=memories,
            prior_experience=experiences,
            current_evidence=tuple(self._evidence),
            summary=summary,
            clarification_question=clarification_response,
            clarification_request=clarification_details,
            supporting_recall_focus=supporting_recall_focus,
            recursive_recall_depth=state.depth,
            evidence_items_examined=state.evidence_items_examined,
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


def _durable_memory_assessment(memory: DurableMemory) -> str:
    return (
        "Long-term prior scorecard: "
        f"confidence={memory.confidence:.3f}; weight={memory.weight:.3f}; "
        f"support={memory.confidence * memory.weight:.3f}; "
        f"content={memory.content}"
    )


def _effective_assessment(assessment: Any) -> str:
    return (
        "Current effective scorecard: "
        f"confidence={assessment.effective.confidence:.3f}; "
        f"weight={assessment.effective.weight:.3f}; "
        f"support={assessment.effective.support:.3f}; "
        f"content={assessment.proposition}"
    )


def _experience_clarification_resolution(
    entry: JournalEntry,
) -> tuple[str, str, str, str] | None:
    value = entry.experience.get("resolved_clarification")
    if not isinstance(value, dict):
        return None
    subject = value.get("subject")
    attribute = value.get("attribute")
    resolved_value = value.get("value")
    proposition = value.get("proposition")
    if not isinstance(subject, str) or not subject.strip():
        return None
    if not isinstance(attribute, str) or not attribute.strip():
        return None
    if not isinstance(resolved_value, str) or not resolved_value.strip():
        return None
    if not isinstance(proposition, str) or not proposition.strip():
        return None
    return (
        subject.strip(),
        attribute.strip(),
        resolved_value.strip(),
        proposition.strip(),
    )


def _experience_provenance(entry: JournalEntry) -> str:
    input_text = _experience_input_text(entry)
    if not input_text:
        return ""

    speaker = _experience_speaker(entry)
    subject = _experience_resolved_subject(entry)
    parts = ["Experience provenance"]
    if speaker is not None:
        parts.append(f"source={speaker}")
    if subject is not None:
        parts.append(f"resolved_subject={subject}")
    if _experience_clarification_resolution(entry) is not None:
        parts.append("clarification_resolution=true")
    parts.append(f"content={input_text}")
    return "; ".join(parts)


def _current_context_evidence(
    current_speaker: str | None,
    current_context: dict[str, Any],
) -> str:
    if not current_context and not current_speaker:
        return ""

    speaker = (current_speaker or "").strip() or "unknown"
    return (
        "Current conscious evidence context: "
        f"current_speaker={speaker}; context={current_context}"
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
        clarification = _experience_clarification_resolution(entry)
        if clarification is not None:
            parts.append(clarification[3])
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
    clarification = _experience_clarification_resolution(entry)
    if clarification is not None:
        return clarification[3]
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
