from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryArtifact,
    MemoryClass,
)
from aicognitive_mind.storage import JournalStore, MemoryStore


class ArticleReference(BaseModel):
    title: str = Field(min_length=1)
    url: str = Field(min_length=1)
    relevant_content: str = Field(min_length=1)


class ProvenanceHop(BaseModel):
    """One link in the evidence source chain, ordered immediate source outward."""

    source: str = Field(min_length=1)
    context: str | None = None
    condition: str | None = None


class EvidenceAppraisal(BaseModel):
    """Separate evidence dimensions; intentionally no combined credibility score."""

    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)
    provenance: tuple[ProvenanceHop, ...] = Field(min_length=1)
    basis: tuple[str, ...] = ()


class ResearchObservation(BaseModel):
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    articles: tuple[ArticleReference, ...] = ()
    appraisal: EvidenceAppraisal | None = None


class RecallCall(BaseModel):
    action: Literal["recall"]
    focus: str = Field(min_length=1)


class ConsiderEvidenceCall(BaseModel):
    action: Literal["consider_evidence"]
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    articles: tuple[ArticleReference, ...] = ()
    appraisal: EvidenceAppraisal | None = None


class MemoryArtifactProposal(BaseModel):
    kind: str = Field(min_length=1, max_length=120)
    payload: dict[str, Any] = Field(default_factory=dict)


class ProposeMemoryCall(BaseModel):
    action: Literal["propose_memory"]
    memory_class: MemoryClass
    content: str = Field(min_length=1)
    associations: tuple[str, ...] = ()
    grounding: tuple[str, ...] = Field(min_length=1)
    artifacts: tuple[MemoryArtifactProposal, ...] = ()


MemoryStewardCall = Annotated[
    RecallCall | ConsiderEvidenceCall | ProposeMemoryCall,
    Field(discriminator="action"),
]
_CALL_ADAPTER = TypeAdapter(MemoryStewardCall)


class RecalledExperience(BaseModel):
    kind: str
    occurred_at: str
    excerpt: str


class MemoryBrief(BaseModel):
    focus: str
    identity_context: dict[str, Any]
    durable_memory: tuple[DurableMemory, ...] = ()
    prior_experience: tuple[RecalledExperience, ...] = ()
    current_evidence: tuple[ResearchObservation, ...] = ()
    summary: str


class EvidenceDeliberation(BaseModel):
    """Structured investigation guidance; it does not select an authoritative value."""

    existing_support_count: int = Field(ge=1)
    proposed_support_count: int = Field(ge=1)
    provenance_relationship: Literal[
        "overlap_detected",
        "no_overlap_observed",
        "unknown",
    ]
    existing_provenance_depth: int = Field(ge=0)
    proposed_provenance_depth: int = Field(ge=0)
    appraisal_gaps: tuple[str, ...] = ()
    context_observations: tuple[str, ...] = ()
    investigation_questions: tuple[str, ...] = ()


class SemanticTension(BaseModel):
    subject: str
    attribute: str
    proposed_value: Any
    existing_value: Any
    proposed_evidence_content: str
    existing_evidence_content: str
    proposed_appraisal: EvidenceAppraisal | None = None
    existing_appraisal: EvidenceAppraisal | None = None
    deliberation: EvidenceDeliberation | None = None
    status: Literal["unresolved"] = "unresolved"


class MemoryDecision(BaseModel):
    accepted: bool
    reason: str
    memory: DurableMemory | None = None
    tensions: tuple[SemanticTension, ...] = ()


class MemoryStewardTrace(BaseModel):
    recalled_context: MemoryBrief
    evidence_considered: tuple[ResearchObservation, ...] = ()
    memory_decisions: tuple[MemoryDecision, ...] = ()


class MemoryStewardNotConsultedError(RuntimeError):
    pass


_SEMANTIC_INTERPRETATION_KIND = "semantic_interpretation"
_SEMANTIC_EQUIVALENCE_KIND = "semantic_equivalence"
_SEMANTIC_TENSION_KIND = "semantic_tension"
_EVIDENCE_APPRAISAL_KIND = "evidence_appraisal"
_EVIDENCE_DELIBERATION_KIND = "evidence_deliberation"


def _normalized_semantic_value(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if isinstance(value, (int, float, bool)) or value is None:
        return str(value).casefold()
    if isinstance(value, list):
        return "[" + ",".join(_normalized_semantic_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            f"{str(key).casefold()}:{_normalized_semantic_value(value[key])}"
            for key in sorted(value, key=lambda item: str(item).casefold())
        ) + "}"
    return " ".join(str(value).casefold().split())


def _semantic_signature_from_payload(payload: dict[str, Any]) -> tuple[str, str, str] | None:
    subject = payload.get("subject")
    attribute = payload.get("attribute")
    if not isinstance(subject, str) or not subject.strip():
        return None
    if not isinstance(attribute, str) or not attribute.strip():
        return None
    if "value" not in payload:
        return None
    return (
        _normalized_semantic_value(subject),
        _normalized_semantic_value(attribute),
        _normalized_semantic_value(payload["value"]),
    )


def _semantic_key_from_payload(payload: dict[str, Any]) -> tuple[str, str] | None:
    subject = payload.get("subject")
    attribute = payload.get("attribute")
    if not isinstance(subject, str) or not subject.strip():
        return None
    if not isinstance(attribute, str) or not attribute.strip():
        return None
    return (
        _normalized_semantic_value(subject),
        _normalized_semantic_value(attribute),
    )


def _semantic_interpretations(
    artifacts: tuple[MemoryArtifact, ...] | tuple[MemoryArtifactProposal, ...],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    interpretations: dict[tuple[str, str, str], dict[str, Any]] = {}
    for artifact in artifacts:
        if artifact.kind != _SEMANTIC_INTERPRETATION_KIND:
            continue
        signature = _semantic_signature_from_payload(artifact.payload)
        if signature is not None:
            interpretations[signature] = artifact.payload
    return interpretations


def _evidence_appraisal_from_artifacts(
    artifacts: tuple[MemoryArtifact, ...] | tuple[MemoryArtifactProposal, ...],
) -> EvidenceAppraisal | None:
    for artifact in artifacts:
        if artifact.kind == _EVIDENCE_APPRAISAL_KIND:
            return EvidenceAppraisal.model_validate(artifact.payload)
    return None


def _provenance_sources(appraisal: EvidenceAppraisal | None) -> set[str]:
    if appraisal is None:
        return set()
    return {
        _normalized_semantic_value(hop.source)
        for hop in appraisal.provenance
        if hop.source.strip()
    }


def _deliberate_tension(
    *,
    tension: SemanticTension,
    existing_memories: list[DurableMemory],
) -> EvidenceDeliberation:
    semantic_key = (
        _normalized_semantic_value(tension.subject),
        _normalized_semantic_value(tension.attribute),
    )
    existing_value = _normalized_semantic_value(tension.existing_value)
    proposed_value = _normalized_semantic_value(tension.proposed_value)

    existing_support_count = 0
    proposed_support_count = 1  # The current proposal is itself one evidence item.
    for memory in existing_memories:
        for signature in _semantic_interpretations(memory.artifacts):
            if signature[:2] != semantic_key:
                continue
            if signature[2] == existing_value:
                existing_support_count += 1
            elif signature[2] == proposed_value:
                proposed_support_count += 1

    # The tension can only exist because at least one competing existing memory was found.
    existing_support_count = max(existing_support_count, 1)

    existing_appraisal = tension.existing_appraisal
    proposed_appraisal = tension.proposed_appraisal
    existing_sources = _provenance_sources(existing_appraisal)
    proposed_sources = _provenance_sources(proposed_appraisal)

    if not existing_sources or not proposed_sources:
        provenance_relationship = "unknown"
    elif existing_sources & proposed_sources:
        provenance_relationship = "overlap_detected"
    else:
        provenance_relationship = "no_overlap_observed"

    appraisal_gaps: list[str] = []
    if existing_appraisal is None:
        appraisal_gaps.append("existing evidence has no appraisal")
    if proposed_appraisal is None:
        appraisal_gaps.append("proposed evidence has no appraisal")

    context_observations: list[str] = []
    if existing_appraisal and proposed_appraisal:
        existing_immediate = existing_appraisal.provenance[0]
        proposed_immediate = proposed_appraisal.provenance[0]
        if existing_immediate.context != proposed_immediate.context:
            context_observations.append(
                "Immediate-source contexts differ; determine whether context explains the competing values."
            )
        if existing_immediate.condition != proposed_immediate.condition:
            context_observations.append(
                "Immediate-source conditions differ; determine whether source condition affects applicability."
            )

    questions: list[str] = []
    if appraisal_gaps:
        questions.append(
            "Appraise missing evidence for provenance, Confidence, and Weight before attempting resolution."
        )
    if provenance_relationship == "overlap_detected":
        questions.append(
            "Trace the shared provenance upstream to determine whether the evidence is independent or repeated reporting."
        )
    elif provenance_relationship == "no_overlap_observed":
        questions.append(
            "Verify whether the apparently separate provenance chains are genuinely independent."
        )
    else:
        questions.append(
            "Establish enough provenance to compare the competing evidence responsibly."
        )
    if context_observations:
        questions.append(
            "Determine whether the competing values apply to different contexts or conditions."
        )
    if existing_support_count <= 1:
        questions.append("Seek independent corroboration for the existing value.")
    if proposed_support_count <= 1:
        questions.append("Seek independent corroboration for the proposed value.")
    questions.append(
        "Check whether the competing values can both be valid at different times before treating the tension as contradiction."
    )

    # Preserve order while removing duplicate guidance.
    unique_questions = tuple(dict.fromkeys(questions))
    return EvidenceDeliberation(
        existing_support_count=existing_support_count,
        proposed_support_count=proposed_support_count,
        provenance_relationship=provenance_relationship,
        existing_provenance_depth=(
            len(existing_appraisal.provenance) if existing_appraisal else 0
        ),
        proposed_provenance_depth=(
            len(proposed_appraisal.provenance) if proposed_appraisal else 0
        ),
        appraisal_gaps=tuple(appraisal_gaps),
        context_observations=tuple(context_observations),
        investigation_questions=unique_questions,
    )


def _materialize_artifact(proposal: MemoryArtifactProposal) -> MemoryArtifact:
    payload = proposal.payload
    if proposal.kind == _EVIDENCE_APPRAISAL_KIND:
        payload = EvidenceAppraisal.model_validate(payload).model_dump(mode="json")
    return MemoryArtifact(kind=proposal.kind, payload=payload)


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
        self._pending_tensions: list[SemanticTension] = []
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
                appraisal=call.appraisal,
            )
            self._evidence.append(observation)
            self._brief = self._refresh_brief_with_evidence(brief)
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
        for tension in self._pending_tensions:
            await self._journal.append(
                JournalEntry(
                    kind=JournalKind.TENSION,
                    experience={
                        "source": "conscious_memory_steward",
                        "status": tension.status,
                        "subject": tension.subject,
                        "attribute": tension.attribute,
                        "competing_values": {
                            "existing": tension.existing_value,
                            "proposed": tension.proposed_value,
                        },
                        "evidence": {
                            "existing": tension.existing_evidence_content,
                            "proposed": tension.proposed_evidence_content,
                        },
                        "appraisals": {
                            "existing": (
                                tension.existing_appraisal.model_dump(mode="json")
                                if tension.existing_appraisal
                                else None
                            ),
                            "proposed": (
                                tension.proposed_appraisal.model_dump(mode="json")
                                if tension.proposed_appraisal
                                else None
                            ),
                        },
                        "deliberation": (
                            tension.deliberation.model_dump(mode="json")
                            if tension.deliberation
                            else None
                        ),
                    },
                ),
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
                reason="An exact durable memory already exists; the repeated experience remains in the journal.",
            )

        proposed_interpretations = _semantic_interpretations(call.artifacts)
        equivalent_evidence: list[tuple[DurableMemory, dict[str, Any]]] = []
        tensions: list[SemanticTension] = []
        for memory in existing:
            existing_interpretations = _semantic_interpretations(memory.artifacts)
            for proposed_signature, proposed_payload in proposed_interpretations.items():
                if proposed_signature in existing_interpretations:
                    equivalent_evidence.append((memory, proposed_payload))
                    continue

                proposed_key = proposed_signature[:2]
                for existing_signature, existing_payload in existing_interpretations.items():
                    if existing_signature[:2] != proposed_key:
                        continue
                    tension = SemanticTension(
                        subject=str(proposed_payload["subject"]),
                        attribute=str(proposed_payload["attribute"]),
                        proposed_value=proposed_payload["value"],
                        existing_value=existing_payload["value"],
                        proposed_evidence_content=call.content,
                        existing_evidence_content=memory.content,
                        proposed_appraisal=_evidence_appraisal_from_artifacts(call.artifacts),
                        existing_appraisal=_evidence_appraisal_from_artifacts(memory.artifacts),
                    )
                    if tension not in tensions:
                        tensions.append(tension)

        tensions = [
            tension.model_copy(
                update={
                    "deliberation": _deliberate_tension(
                        tension=tension,
                        existing_memories=existing,
                    )
                }
            )
            for tension in tensions
        ]

        associations = call.associations or tuple(_derived_associations(call.content))
        artifacts = [_materialize_artifact(artifact) for artifact in call.artifacts]
        if equivalent_evidence:
            matched_memory, matched_meaning = equivalent_evidence[0]
            artifacts.append(
                MemoryArtifact(
                    kind=_SEMANTIC_EQUIVALENCE_KIND,
                    payload={
                        "meaning": matched_meaning,
                        "equivalent_evidence_content": matched_memory.content,
                    },
                )
            )
        for tension in tensions:
            artifacts.append(
                MemoryArtifact(
                    kind=_SEMANTIC_TENSION_KIND,
                    payload={
                        "status": tension.status,
                        "subject": tension.subject,
                        "attribute": tension.attribute,
                        "proposed_value": tension.proposed_value,
                        "existing_value": tension.existing_value,
                        "existing_evidence_content": tension.existing_evidence_content,
                        "proposed_appraisal": (
                            tension.proposed_appraisal.model_dump(mode="json")
                            if tension.proposed_appraisal
                            else None
                        ),
                        "existing_appraisal": (
                            tension.existing_appraisal.model_dump(mode="json")
                            if tension.existing_appraisal
                            else None
                        ),
                    },
                )
            )
            if tension.deliberation:
                artifacts.append(
                    MemoryArtifact(
                        kind=_EVIDENCE_DELIBERATION_KIND,
                        payload=tension.deliberation.model_dump(mode="json"),
                    )
                )

        memory = DurableMemory(
            memory_class=call.memory_class,
            content=call.content,
            associations=associations,
            grounding=call.grounding,
            artifacts=tuple(artifacts),
        )
        self._pending.append(memory)
        self._pending_tensions.extend(tensions)
        if tensions:
            reason = (
                "Accepted as distinct evidence with unresolved semantic tension; no competing value "
                "was selected as authoritative."
            )
        elif equivalent_evidence:
            reason = "Accepted as distinct corroborating evidence for an already interpreted proposition."
        else:
            reason = "Accepted by the Conscious Memory Steward for commit with this experience."
        return MemoryDecision(
            accepted=True,
            reason=reason,
            memory=memory,
            tensions=tuple(tensions),
        )

    def _build_brief(
        self,
        focus: str,
        memories: tuple[DurableMemory, ...],
        experiences: tuple[JournalEntry, ...],
    ) -> MemoryBrief:
        recalled_experiences = tuple(
            RecalledExperience(
                kind=entry.kind.value,
                occurred_at=entry.occurred_at.isoformat(),
                excerpt=_experience_excerpt(entry),
            )
            for entry in experiences
        )
        return MemoryBrief(
            focus=focus,
            identity_context=self._mind.identity.model_dump(mode="json"),
            durable_memory=memories,
            prior_experience=recalled_experiences,
            current_evidence=tuple(self._evidence),
            summary=self._summary(memories, recalled_experiences),
        )

    def _refresh_brief_with_evidence(self, brief: MemoryBrief) -> MemoryBrief:
        return brief.model_copy(
            update={
                "current_evidence": tuple(self._evidence),
                "summary": self._summary(brief.durable_memory, brief.prior_experience),
            }
        )

    def _summary(
        self,
        memories: tuple[DurableMemory, ...],
        experiences: tuple[RecalledExperience, ...],
    ) -> str:
        parts: list[str] = []
        if memories:
            parts.append(
                "Established memory: " + " | ".join(memory.content for memory in memories)
            )
        if experiences:
            parts.append(
                "Related prior experience: "
                + " | ".join(experience.excerpt for experience in experiences)
            )
        if self._evidence:
            parts.append(
                "Current research evidence: "
                + " | ".join(observation.response for observation in self._evidence)
            )
        investigation_questions: list[str] = []
        for memory in memories:
            for artifact in memory.artifacts:
                if artifact.kind != _EVIDENCE_DELIBERATION_KIND:
                    continue
                for question in artifact.payload.get("investigation_questions", []):
                    if isinstance(question, str) and question not in investigation_questions:
                        investigation_questions.append(question)
        if investigation_questions:
            parts.append(
                "Investigation guidance: " + " | ".join(investigation_questions)
            )
        if not parts:
            parts.append("No materially related durable memory or prior experience was found.")
        return "\n".join(parts)

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
