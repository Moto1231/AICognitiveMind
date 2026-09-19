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


class SemanticInterpretation(BaseModel):
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    value: Any


class TensionInvestigationFinding(BaseModel):
    """Evidence-backed finding about how two competing values relate."""

    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    existing_value: Any
    proposed_value: Any
    provenance_independence: Literal[
        "verified_independent",
        "shared_provenance",
        "unknown",
    ] = "unknown"
    temporal_relationship: Literal[
        "same_timeframe",
        "changed_over_time",
        "unknown",
    ] = "unknown"
    contextual_relationship: Literal[
        "same_context",
        "different_contexts",
        "unknown",
    ] = "unknown"
    basis: tuple[str, ...] = Field(min_length=1)
    existing_scope: str | None = None
    proposed_scope: str | None = None


class ResearchObservation(BaseModel):
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    articles: tuple[ArticleReference, ...] = ()
    appraisal: EvidenceAppraisal | None = None
    semantic_interpretation: SemanticInterpretation | None = None
    tension_finding: TensionInvestigationFinding | None = None


class RecallCall(BaseModel):
    action: Literal["recall"]
    focus: str = Field(min_length=1)


class ConsiderEvidenceCall(BaseModel):
    action: Literal["consider_evidence"]
    query: str = Field(min_length=1)
    response: str = Field(min_length=1)
    articles: tuple[ArticleReference, ...] = ()
    appraisal: EvidenceAppraisal | None = None
    semantic_interpretation: SemanticInterpretation | None = None
    tension_finding: TensionInvestigationFinding | None = None


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


class TransitionBeliefCall(BaseModel):
    action: Literal["transition_belief"]
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    candidate_value: Any


class ReframeBeliefCall(BaseModel):
    action: Literal["reframe_belief"]
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    existing_value: Any
    proposed_value: Any


MemoryStewardCall = Annotated[
    RecallCall
    | ConsiderEvidenceCall
    | ProposeMemoryCall
    | TransitionBeliefCall
    | ReframeBeliefCall,
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


class DeliberationEvidence(BaseModel):
    """Compact current-evidence contribution retained with deliberation history."""

    query: str = Field(min_length=1)
    response_excerpt: str = Field(min_length=1, max_length=500)
    appraisal: EvidenceAppraisal | None = None
    semantic_interpretation: SemanticInterpretation


class EvidenceSideProfile(BaseModel):
    value: Any
    support_count: int = Field(ge=1)
    appraised_support_count: int = Field(ge=0)
    distinct_immediate_sources: int = Field(ge=0)
    confidence_floor: float | None = None
    confidence_ceiling: float | None = None
    weight_floor: float | None = None
    weight_ceiling: float | None = None


class ResolutionReadiness(BaseModel):
    """Gate for a later belief transition; never performs the transition itself."""

    status: Literal["blocked", "candidate_ready", "reframe_required"]
    candidate_side: Literal["existing", "proposed"] | None = None
    candidate_value: Any = None
    existing: EvidenceSideProfile
    proposed: EvidenceSideProfile
    blockers: tuple[str, ...] = ()
    basis: tuple[str, ...] = ()


class EvidenceDeliberation(BaseModel):
    """Structured investigation guidance; it does not select an authoritative value."""

    subject: str | None = None
    attribute: str | None = None
    existing_value: Any = None
    proposed_value: Any = None
    revision: int = Field(default=1, ge=1)
    trigger: Literal["tension_detected", "current_evidence_reassessment"] = "tension_detected"
    current_evidence_considered: int = Field(default=0, ge=0)
    current_existing_support_count: int = Field(default=0, ge=0)
    current_proposed_support_count: int = Field(default=0, ge=0)
    current_evidence_history: tuple[DeliberationEvidence, ...] = ()
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
    tension_finding: TensionInvestigationFinding | None = None
    resolution_readiness: ResolutionReadiness | None = None


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


class BeliefTransitionDecision(BaseModel):
    accepted: bool
    reason: str
    subject: str
    attribute: str
    from_value: Any = None
    to_value: Any = None
    deliberation_revision: int | None = None


class BeliefReframeDecision(BaseModel):
    accepted: bool
    reason: str
    subject: str
    attribute: str
    relationship: Literal["temporal", "contextual", "temporal_contextual"] | None = None
    existing_value: Any = None
    proposed_value: Any = None
    existing_scope: str | None = None
    proposed_scope: str | None = None
    deliberation_revision: int | None = None


class MemoryStewardTrace(BaseModel):
    recalled_context: MemoryBrief
    evidence_considered: tuple[ResearchObservation, ...] = ()
    memory_decisions: tuple[MemoryDecision, ...] = ()
    tension_reassessments: tuple[SemanticTension, ...] = ()
    belief_transitions: tuple[BeliefTransitionDecision, ...] = ()
    belief_reframes: tuple[BeliefReframeDecision, ...] = ()


class MemoryStewardNotConsultedError(RuntimeError):
    pass


_SEMANTIC_INTERPRETATION_KIND = "semantic_interpretation"
_SEMANTIC_EQUIVALENCE_KIND = "semantic_equivalence"
_SEMANTIC_TENSION_KIND = "semantic_tension"
_EVIDENCE_APPRAISAL_KIND = "evidence_appraisal"
_EVIDENCE_DELIBERATION_KIND = "evidence_deliberation"
_BELIEF_TRANSITION_KIND = "belief_transition"
_BELIEF_STATUS_KIND = "belief_status"
_BELIEF_REFRAME_KIND = "belief_reframe"
_SCOPED_BELIEF_KIND = "scoped_belief"


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


def _semantic_signature_from_interpretation(
    interpretation: SemanticInterpretation | None,
) -> tuple[str, str, str] | None:
    if interpretation is None:
        return None
    return (
        _normalized_semantic_value(interpretation.subject),
        _normalized_semantic_value(interpretation.attribute),
        _normalized_semantic_value(interpretation.value),
    )


def _deliberation_matches_tension(
    deliberation: EvidenceDeliberation,
    tension: SemanticTension,
) -> bool:
    if deliberation.subject is None or deliberation.attribute is None:
        return False
    return (
        _normalized_semantic_value(deliberation.subject)
        == _normalized_semantic_value(tension.subject)
        and _normalized_semantic_value(deliberation.attribute)
        == _normalized_semantic_value(tension.attribute)
        and _normalized_semantic_value(deliberation.existing_value)
        == _normalized_semantic_value(tension.existing_value)
        and _normalized_semantic_value(deliberation.proposed_value)
        == _normalized_semantic_value(tension.proposed_value)
    )


def _latest_deliberation(
    memory: DurableMemory,
    tension: SemanticTension,
) -> EvidenceDeliberation | None:
    legacy: EvidenceDeliberation | None = None
    for artifact in reversed(memory.artifacts):
        if artifact.kind != _EVIDENCE_DELIBERATION_KIND:
            continue
        deliberation = EvidenceDeliberation.model_validate(artifact.payload)
        if _deliberation_matches_tension(deliberation, tension):
            return deliberation
        if legacy is None and deliberation.subject is None:
            legacy = deliberation
    return legacy


def _provenance_sources(appraisal: EvidenceAppraisal | None) -> set[str]:
    if appraisal is None:
        return set()
    return {
        _normalized_semantic_value(hop.source)
        for hop in appraisal.provenance
        if hop.source.strip()
    }


def _compact_deliberation_evidence(
    observation: ResearchObservation,
) -> DeliberationEvidence | None:
    if observation.semantic_interpretation is None:
        return None
    excerpt = observation.response
    if len(excerpt) > 500:
        excerpt = f"{excerpt[:497]}..."
    return DeliberationEvidence(
        query=observation.query,
        response_excerpt=excerpt,
        appraisal=observation.appraisal,
        semantic_interpretation=observation.semantic_interpretation,
    )


def _deliberation_evidence_key(
    evidence: DeliberationEvidence,
) -> tuple[str, str, str, str, tuple[str, ...]]:
    interpretation = evidence.semantic_interpretation
    return (
        _normalized_semantic_value(interpretation.subject),
        _normalized_semantic_value(interpretation.attribute),
        _normalized_semantic_value(interpretation.value),
        _normalized_semantic_value(evidence.response_excerpt),
        tuple(sorted(_provenance_sources(evidence.appraisal))),
    )


def _finding_matches_tension(
    finding: TensionInvestigationFinding,
    tension: SemanticTension,
) -> bool:
    return (
        _normalized_semantic_value(finding.subject)
        == _normalized_semantic_value(tension.subject)
        and _normalized_semantic_value(finding.attribute)
        == _normalized_semantic_value(tension.attribute)
        and _normalized_semantic_value(finding.existing_value)
        == _normalized_semantic_value(tension.existing_value)
        and _normalized_semantic_value(finding.proposed_value)
        == _normalized_semantic_value(tension.proposed_value)
    )


def _latest_tension_finding(
    tension: SemanticTension,
    current_evidence: tuple[ResearchObservation, ...],
) -> TensionInvestigationFinding | None:
    for observation in reversed(current_evidence):
        finding = observation.tension_finding
        if finding and _finding_matches_tension(finding, tension):
            return finding
    return None


def _side_profile(
    *,
    value: Any,
    support_count: int,
    appraisals: list[EvidenceAppraisal | None],
) -> EvidenceSideProfile:
    known = [appraisal for appraisal in appraisals if appraisal is not None]
    immediate_sources = {
        _normalized_semantic_value(appraisal.provenance[0].source)
        for appraisal in known
        if appraisal.provenance and appraisal.provenance[0].source.strip()
    }
    confidences = [appraisal.confidence for appraisal in known]
    weights = [appraisal.weight for appraisal in known]
    return EvidenceSideProfile(
        value=value,
        support_count=support_count,
        appraised_support_count=len(known),
        distinct_immediate_sources=len(immediate_sources),
        confidence_floor=min(confidences) if confidences else None,
        confidence_ceiling=max(confidences) if confidences else None,
        weight_floor=min(weights) if weights else None,
        weight_ceiling=max(weights) if weights else None,
    )


def _strictly_dominates(
    candidate: EvidenceSideProfile,
    competitor: EvidenceSideProfile,
) -> bool:
    if None in {
        candidate.confidence_floor,
        candidate.weight_floor,
        competitor.confidence_ceiling,
        competitor.weight_ceiling,
    }:
        return False
    confidence_at_least = (
        candidate.confidence_floor >= competitor.confidence_ceiling
    )
    weight_at_least = candidate.weight_floor >= competitor.weight_ceiling
    one_strict = (
        candidate.confidence_floor > competitor.confidence_ceiling
        or candidate.weight_floor > competitor.weight_ceiling
    )
    return confidence_at_least and weight_at_least and one_strict


def _resolution_readiness(
    *,
    tension: SemanticTension,
    existing_profile: EvidenceSideProfile,
    proposed_profile: EvidenceSideProfile,
    appraisal_gaps: tuple[str, ...],
    finding: TensionInvestigationFinding | None,
) -> ResolutionReadiness:
    blockers: list[str] = []
    basis: list[str] = []

    if appraisal_gaps:
        blockers.append("Competing evidence is not fully appraised.")
    else:
        basis.append("Competing evidence has provenance, Confidence, and Weight appraisals.")

    if finding is None:
        blockers.append(
            "No evidence-backed tension finding establishes provenance independence and applicability."
        )
    else:
        basis.extend(finding.basis)
        if finding.temporal_relationship == "changed_over_time":
            return ResolutionReadiness(
                status="reframe_required",
                existing=existing_profile,
                proposed=proposed_profile,
                blockers=(),
                basis=(
                    *basis,
                    "The competing values apply at different times; model temporal change instead of selecting one timeless value.",
                ),
            )
        if finding.contextual_relationship == "different_contexts":
            return ResolutionReadiness(
                status="reframe_required",
                existing=existing_profile,
                proposed=proposed_profile,
                blockers=(),
                basis=(
                    *basis,
                    "The competing values apply in different contexts; model contextual scope instead of selecting one universal value.",
                ),
            )
        if finding.temporal_relationship != "same_timeframe":
            blockers.append("Temporal applicability remains unresolved.")
        if finding.contextual_relationship != "same_context":
            blockers.append("Contextual applicability remains unresolved.")
        if finding.provenance_independence != "verified_independent":
            blockers.append("Evidence independence has not been verified.")

    candidates: list[tuple[str, EvidenceSideProfile, EvidenceSideProfile]] = []
    if (
        existing_profile.support_count >= 2
        and existing_profile.distinct_immediate_sources >= 2
        and _strictly_dominates(existing_profile, proposed_profile)
    ):
        candidates.append(("existing", existing_profile, proposed_profile))
    if (
        proposed_profile.support_count >= 2
        and proposed_profile.distinct_immediate_sources >= 2
        and _strictly_dominates(proposed_profile, existing_profile)
    ):
        candidates.append(("proposed", proposed_profile, existing_profile))

    if not candidates:
        blockers.append(
            "Neither side has independently corroborated evidence that strictly dominates the competing side on both separate Confidence and Weight dimensions."
        )

    if blockers or len(candidates) != 1:
        return ResolutionReadiness(
            status="blocked",
            existing=existing_profile,
            proposed=proposed_profile,
            blockers=tuple(dict.fromkeys(blockers)),
            basis=tuple(dict.fromkeys(basis)),
        )

    side, candidate, _ = candidates[0]
    return ResolutionReadiness(
        status="candidate_ready",
        candidate_side=side,
        candidate_value=candidate.value,
        existing=existing_profile,
        proposed=proposed_profile,
        blockers=(),
        basis=tuple(
            dict.fromkeys(
                [
                    *basis,
                    "Candidate evidence has at least two supporting items from at least two distinct immediate sources.",
                    "Candidate evidence strictly dominates the competing evidence on separate Confidence and Weight dimensions without combining them into one score.",
                ]
            )
        ),
    )


def _deliberate_tension(
    *,
    tension: SemanticTension,
    existing_memories: list[DurableMemory],
    current_evidence: tuple[ResearchObservation, ...] = (),
    include_pending_proposed: bool = False,
    prior_deliberation: EvidenceDeliberation | None = None,
) -> EvidenceDeliberation:
    semantic_key = (
        _normalized_semantic_value(tension.subject),
        _normalized_semantic_value(tension.attribute),
    )
    existing_value = _normalized_semantic_value(tension.existing_value)
    proposed_value = _normalized_semantic_value(tension.proposed_value)

    existing_support_count = 0
    proposed_support_count = 1 if include_pending_proposed else 0
    existing_appraisals: list[EvidenceAppraisal | None] = []
    proposed_appraisals: list[EvidenceAppraisal | None] = []

    for memory in existing_memories:
        appraisal = _evidence_appraisal_from_artifacts(memory.artifacts)
        for signature in _semantic_interpretations(memory.artifacts):
            if signature[:2] != semantic_key:
                continue
            if signature[2] == existing_value:
                existing_support_count += 1
                existing_appraisals.append(appraisal)
            elif signature[2] == proposed_value:
                proposed_support_count += 1
                proposed_appraisals.append(appraisal)

    if include_pending_proposed:
        proposed_appraisals.append(tension.proposed_appraisal)

    relevant_current_evidence: list[ResearchObservation] = []
    for observation in current_evidence:
        signature = _semantic_signature_from_interpretation(
            observation.semantic_interpretation
        )
        if signature is None or signature[:2] != semantic_key:
            continue
        if signature[2] not in {existing_value, proposed_value}:
            continue
        relevant_current_evidence.append(observation)

    prior_evidence = list(
        prior_deliberation.current_evidence_history
        if prior_deliberation
        else ()
    )
    merged_evidence: list[DeliberationEvidence] = []
    seen_evidence: set[tuple[str, str, str, str, tuple[str, ...]]] = set()
    for evidence in [
        *prior_evidence,
        *(
            compact
            for observation in relevant_current_evidence
            if (compact := _compact_deliberation_evidence(observation)) is not None
        ),
    ]:
        key = _deliberation_evidence_key(evidence)
        if key in seen_evidence:
            continue
        seen_evidence.add(key)
        merged_evidence.append(evidence)

    for evidence in merged_evidence:
        signature = _semantic_signature_from_interpretation(
            evidence.semantic_interpretation
        )
        if signature is None:
            continue
        if signature[2] == existing_value:
            existing_support_count += 1
            existing_appraisals.append(evidence.appraisal)
        elif signature[2] == proposed_value:
            proposed_support_count += 1
            proposed_appraisals.append(evidence.appraisal)

    current_existing_support_count = 0
    current_proposed_support_count = 0
    for observation in relevant_current_evidence:
        signature = _semantic_signature_from_interpretation(
            observation.semantic_interpretation
        )
        if signature is None:
            continue
        if signature[2] == existing_value:
            current_existing_support_count += 1
        elif signature[2] == proposed_value:
            current_proposed_support_count += 1

    # A tension requires at least one item on each side.
    existing_support_count = max(existing_support_count, 1)
    proposed_support_count = max(proposed_support_count, 1)

    appraisal_gaps: list[str] = []
    if any(appraisal is None for appraisal in existing_appraisals) or not existing_appraisals:
        appraisal_gaps.append("existing evidence has incomplete appraisal")
    if any(appraisal is None for appraisal in proposed_appraisals) or not proposed_appraisals:
        appraisal_gaps.append("proposed evidence has incomplete appraisal")

    existing_sources = set().union(
        *(_provenance_sources(appraisal) for appraisal in existing_appraisals)
    ) if existing_appraisals else set()
    proposed_sources = set().union(
        *(_provenance_sources(appraisal) for appraisal in proposed_appraisals)
    ) if proposed_appraisals else set()

    provenance_complete = bool(existing_sources and proposed_sources) and not appraisal_gaps
    if existing_sources & proposed_sources:
        provenance_relationship = "overlap_detected"
    elif provenance_complete:
        provenance_relationship = "no_overlap_observed"
    else:
        provenance_relationship = "unknown"

    context_observations: list[str] = []
    known_existing = [appraisal for appraisal in existing_appraisals if appraisal]
    known_proposed = [appraisal for appraisal in proposed_appraisals if appraisal]
    if known_existing and known_proposed:
        existing_contexts = {
            appraisal.provenance[0].context for appraisal in known_existing
        }
        proposed_contexts = {
            appraisal.provenance[0].context for appraisal in known_proposed
        }
        existing_conditions = {
            appraisal.provenance[0].condition for appraisal in known_existing
        }
        proposed_conditions = {
            appraisal.provenance[0].condition for appraisal in known_proposed
        }
        if existing_contexts != proposed_contexts:
            context_observations.append(
                "Immediate-source contexts differ; determine whether context explains the competing values."
            )
        if existing_conditions != proposed_conditions:
            context_observations.append(
                "Immediate-source conditions differ; determine whether source condition affects applicability."
            )

    finding = (
        _latest_tension_finding(tension, tuple(relevant_current_evidence))
        or (prior_deliberation.tension_finding if prior_deliberation else None)
    )
    questions: list[str] = []
    if appraisal_gaps:
        questions.append(
            "Appraise missing evidence for provenance, Confidence, and Weight before attempting resolution."
        )

    if finding is None or finding.provenance_independence == "unknown":
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
    elif finding.provenance_independence == "shared_provenance":
        questions.append(
            "Determine whether shared provenance prevents treating the evidence as independent corroboration."
        )

    if finding is None or finding.contextual_relationship == "unknown":
        if context_observations:
            questions.append(
                "Determine whether the competing values apply to different contexts or conditions."
            )

    if existing_support_count <= 1:
        questions.append("Seek independent corroboration for the existing value.")
    if proposed_support_count <= 1:
        questions.append("Seek independent corroboration for the proposed value.")

    if finding is None or finding.temporal_relationship == "unknown":
        questions.append(
            "Check whether the competing values can both be valid at different times before treating the tension as contradiction."
        )

    revision = (prior_deliberation.revision + 1) if prior_deliberation else 1
    trigger = (
        "current_evidence_reassessment"
        if prior_deliberation is not None and relevant_current_evidence
        else "tension_detected"
    )
    unique_questions = tuple(dict.fromkeys(questions))
    existing_profile = _side_profile(
        value=tension.existing_value,
        support_count=existing_support_count,
        appraisals=existing_appraisals,
    )
    proposed_profile = _side_profile(
        value=tension.proposed_value,
        support_count=proposed_support_count,
        appraisals=proposed_appraisals,
    )
    readiness = _resolution_readiness(
        tension=tension,
        existing_profile=existing_profile,
        proposed_profile=proposed_profile,
        appraisal_gaps=tuple(appraisal_gaps),
        finding=finding,
    )
    return EvidenceDeliberation(
        subject=tension.subject,
        attribute=tension.attribute,
        existing_value=tension.existing_value,
        proposed_value=tension.proposed_value,
        revision=revision,
        trigger=trigger,
        current_evidence_considered=len(relevant_current_evidence),
        current_existing_support_count=current_existing_support_count,
        current_proposed_support_count=current_proposed_support_count,
        current_evidence_history=tuple(merged_evidence),
        existing_support_count=existing_support_count,
        proposed_support_count=proposed_support_count,
        provenance_relationship=provenance_relationship,
        existing_provenance_depth=max(
            (len(appraisal.provenance) for appraisal in known_existing),
            default=0,
        ),
        proposed_provenance_depth=max(
            (len(appraisal.provenance) for appraisal in known_proposed),
            default=0,
        ),
        appraisal_gaps=tuple(appraisal_gaps),
        context_observations=tuple(context_observations),
        investigation_questions=unique_questions,
        tension_finding=finding,
        resolution_readiness=readiness,
    )


def _belief_status_for_signature(
    memory: DurableMemory,
    signature: tuple[str, str, str],
) -> str | None:
    for artifact in reversed(memory.artifacts):
        if artifact.kind != _BELIEF_STATUS_KIND:
            continue
        payload = artifact.payload
        candidate = (
            _normalized_semantic_value(payload.get("subject")),
            _normalized_semantic_value(payload.get("attribute")),
            _normalized_semantic_value(payload.get("value")),
        )
        if candidate == signature:
            status = payload.get("status")
            return str(status) if status is not None else None
    return None


def _transition_matches_tension(
    payload: dict[str, Any],
    tension: SemanticTension,
) -> bool:
    if payload.get("status") != "committed":
        return False
    if (
        _normalized_semantic_value(payload.get("subject"))
        != _normalized_semantic_value(tension.subject)
        or _normalized_semantic_value(payload.get("attribute"))
        != _normalized_semantic_value(tension.attribute)
    ):
        return False
    transitioned = {
        _normalized_semantic_value(payload.get("from_value")),
        _normalized_semantic_value(payload.get("to_value")),
    }
    competing = {
        _normalized_semantic_value(tension.existing_value),
        _normalized_semantic_value(tension.proposed_value),
    }
    return transitioned == competing


def _tension_has_committed_transition(
    memory: DurableMemory,
    tension: SemanticTension,
) -> bool:
    return any(
        artifact.kind == _BELIEF_TRANSITION_KIND
        and _transition_matches_tension(artifact.payload, tension)
        for artifact in memory.artifacts
    )


def _latest_current_beliefs(
    memories: tuple[DurableMemory, ...] | list[DurableMemory],
) -> dict[tuple[str, str], dict[str, Any]]:
    beliefs: dict[tuple[str, str], tuple[Any, dict[str, Any]]] = {}
    for memory in memories:
        for artifact in memory.artifacts:
            if artifact.kind != _BELIEF_TRANSITION_KIND:
                continue
            payload = artifact.payload
            if payload.get("status") != "committed":
                continue
            key = (
                _normalized_semantic_value(payload.get("subject")),
                _normalized_semantic_value(payload.get("attribute")),
            )
            previous = beliefs.get(key)
            if previous is None or artifact.formed_at > previous[0]:
                beliefs[key] = (artifact.formed_at, payload)
    return {key: payload for key, (_, payload) in beliefs.items()}


def _deliberation_closed_by_transition(
    deliberation: EvidenceDeliberation,
    beliefs: dict[tuple[str, str], dict[str, Any]],
) -> bool:
    if deliberation.subject is None or deliberation.attribute is None:
        return False
    key = (
        _normalized_semantic_value(deliberation.subject),
        _normalized_semantic_value(deliberation.attribute),
    )
    transition = beliefs.get(key)
    if transition is None:
        return False
    transitioned = {
        _normalized_semantic_value(transition.get("from_value")),
        _normalized_semantic_value(transition.get("to_value")),
    }
    competing = {
        _normalized_semantic_value(deliberation.existing_value),
        _normalized_semantic_value(deliberation.proposed_value),
    }
    return (
        transitioned == competing
        and int(transition.get("deliberation_revision", 0)) >= deliberation.revision
    )


def _reframe_matches_tension(
    payload: dict[str, Any],
    tension: SemanticTension,
) -> bool:
    if payload.get("status") != "committed":
        return False
    if (
        _normalized_semantic_value(payload.get("subject"))
        != _normalized_semantic_value(tension.subject)
        or _normalized_semantic_value(payload.get("attribute"))
        != _normalized_semantic_value(tension.attribute)
    ):
        return False
    reframed = {
        _normalized_semantic_value(payload.get("existing_value")),
        _normalized_semantic_value(payload.get("proposed_value")),
    }
    competing = {
        _normalized_semantic_value(tension.existing_value),
        _normalized_semantic_value(tension.proposed_value),
    }
    return reframed == competing


def _tension_has_committed_reframe(
    memory: DurableMemory,
    tension: SemanticTension,
) -> bool:
    return any(
        artifact.kind == _BELIEF_REFRAME_KIND
        and _reframe_matches_tension(artifact.payload, tension)
        for artifact in memory.artifacts
    )


def _latest_belief_reframes(
    memories: tuple[DurableMemory, ...] | list[DurableMemory],
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    reframes: dict[tuple[str, str, str, str], tuple[Any, dict[str, Any]]] = {}
    for memory in memories:
        for artifact in memory.artifacts:
            if artifact.kind != _BELIEF_REFRAME_KIND:
                continue
            payload = artifact.payload
            if payload.get("status") != "committed":
                continue
            key = (
                _normalized_semantic_value(payload.get("subject")),
                _normalized_semantic_value(payload.get("attribute")),
                _normalized_semantic_value(payload.get("existing_value")),
                _normalized_semantic_value(payload.get("proposed_value")),
            )
            previous = reframes.get(key)
            if previous is None or artifact.formed_at > previous[0]:
                reframes[key] = (artifact.formed_at, payload)
    return {key: payload for key, (_, payload) in reframes.items()}


def _deliberation_closed_by_reframe(
    deliberation: EvidenceDeliberation,
    reframes: dict[tuple[str, str, str, str], dict[str, Any]],
) -> bool:
    if deliberation.subject is None or deliberation.attribute is None:
        return False
    key = (
        _normalized_semantic_value(deliberation.subject),
        _normalized_semantic_value(deliberation.attribute),
        _normalized_semantic_value(deliberation.existing_value),
        _normalized_semantic_value(deliberation.proposed_value),
    )
    reframe = reframes.get(key)
    return (
        reframe is not None
        and int(reframe.get("deliberation_revision", 0)) >= deliberation.revision
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
        self._pending_replacements: list[tuple[DurableMemory, DurableMemory]] = []
        self._tension_reassessments: list[SemanticTension] = []
        self._reassessment_events: list[
            tuple[SemanticTension, tuple[ResearchObservation, ...]]
        ] = []
        self._belief_transitions: list[BeliefTransitionDecision] = []
        self._transition_events: list[dict[str, Any]] = []
        self._belief_reframes: list[BeliefReframeDecision] = []
        self._reframe_events: list[dict[str, Any]] = []
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
                semantic_interpretation=call.semantic_interpretation,
                tension_finding=call.tension_finding,
            )
            self._evidence.append(observation)
            reassessments = await self._reassess_tensions()
            self._brief = self._refresh_brief_with_evidence(brief)
            return {
                "status": "evidence_considered",
                "context": self._brief.model_dump(mode="json"),
                "tension_reassessments": [
                    tension.model_dump(mode="json") for tension in reassessments
                ],
            }

        if isinstance(call, TransitionBeliefCall):
            transition = await self._consider_belief_transition(call)
            self._belief_transitions.append(transition)
            return {
                "status": "belief_transition_considered",
                **transition.model_dump(mode="json"),
            }

        if isinstance(call, ReframeBeliefCall):
            reframe = await self._consider_belief_reframe(call)
            self._belief_reframes.append(reframe)
            return {
                "status": "belief_reframe_considered",
                **reframe.model_dump(mode="json"),
            }

        decision = await self._consider_memory(call)
        self._decisions.append(decision)
        return {"status": "memory_considered", **decision.model_dump(mode="json")}

    async def complete(self) -> MemoryStewardTrace:
        brief = self._require_recall()
        if self._completed:
            raise RuntimeError("This Memory Steward interaction is already complete")

        for original, replacement in self._pending_replacements:
            revised = await self._memory.replace_exact(
                original,
                replacement,
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
            if revised is None:
                raise RuntimeError(
                    "Durable memory changed before evidence reassessment could be committed"
                )
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
                        "phase": "detected",
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
        for tension, evidence_snapshot in self._reassessment_events:
            relevant_evidence = [
                observation.model_dump(mode="json")
                for observation in evidence_snapshot
            ]
            await self._journal.append(
                JournalEntry(
                    kind=JournalKind.TENSION,
                    experience={
                        "source": "conscious_memory_steward",
                        "phase": "reassessment",
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
                        "current_evidence": relevant_evidence,
                        "deliberation": (
                            tension.deliberation.model_dump(mode="json")
                            if tension.deliberation
                            else None
                        ),
                    },
                ),
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
        for event in self._transition_events:
            await self._journal.append(
                JournalEntry(
                    kind=JournalKind.BELIEF_TRANSITION,
                    experience=event,
                ),
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
        for event in self._reframe_events:
            await self._journal.append(
                JournalEntry(
                    kind=JournalKind.BELIEF_REFRAME,
                    experience=event,
                ),
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
        self._completed = True
        return MemoryStewardTrace(
            recalled_context=brief,
            evidence_considered=tuple(self._evidence),
            memory_decisions=tuple(self._decisions),
            tension_reassessments=tuple(self._tension_reassessments),
            belief_transitions=tuple(self._belief_transitions),
            belief_reframes=tuple(self._belief_reframes),
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

    async def _working_memories(self) -> list[DurableMemory]:
        memories = await self._memory.read()
        for original, replacement in self._pending_replacements:
            memories = [
                replacement if memory == original else memory
                for memory in memories
            ]
        return [*memories, *self._pending]

    def _stage_replacement(
        self,
        original: DurableMemory,
        replacement: DurableMemory,
    ) -> None:
        for index, (persisted, current) in enumerate(self._pending_replacements):
            if current == original or persisted == original:
                self._pending_replacements[index] = (persisted, replacement)
                return
        self._pending_replacements.append((original, replacement))

    async def _reassess_tensions(self) -> list[SemanticTension]:
        if not self._evidence:
            return []

        memories = await self._working_memories()
        reassessed: list[SemanticTension] = []
        for memory in memories:
            tension_payloads = [
                artifact.payload
                for artifact in memory.artifacts
                if artifact.kind == _SEMANTIC_TENSION_KIND
                and artifact.payload.get("status", "unresolved") == "unresolved"
            ]
            if not tension_payloads:
                continue

            replacement = memory
            changed = False
            for payload in tension_payloads:
                tension = SemanticTension(
                    subject=str(payload["subject"]),
                    attribute=str(payload["attribute"]),
                    proposed_value=payload["proposed_value"],
                    existing_value=payload["existing_value"],
                    proposed_evidence_content=memory.content,
                    existing_evidence_content=str(
                        payload.get("existing_evidence_content", "")
                    ),
                    proposed_appraisal=(
                        EvidenceAppraisal.model_validate(payload["proposed_appraisal"])
                        if payload.get("proposed_appraisal")
                        else _evidence_appraisal_from_artifacts(memory.artifacts)
                    ),
                    existing_appraisal=(
                        EvidenceAppraisal.model_validate(payload["existing_appraisal"])
                        if payload.get("existing_appraisal")
                        else None
                    ),
                )
                if (
                    _tension_has_committed_transition(replacement, tension)
                    or _tension_has_committed_reframe(replacement, tension)
                ):
                    continue

                semantic_key = (
                    _normalized_semantic_value(tension.subject),
                    _normalized_semantic_value(tension.attribute),
                )
                relevant = tuple(
                    observation
                    for observation in self._evidence
                    if (
                        (signature := _semantic_signature_from_interpretation(
                            observation.semantic_interpretation
                        ))
                        is not None
                        and signature[:2] == semantic_key
                        and signature[2]
                        in {
                            _normalized_semantic_value(tension.existing_value),
                            _normalized_semantic_value(tension.proposed_value),
                        }
                    )
                )
                if not relevant:
                    continue

                prior = _latest_deliberation(replacement, tension)
                updated = tension.model_copy(
                    update={
                        "deliberation": _deliberate_tension(
                            tension=tension,
                            existing_memories=memories,
                            current_evidence=relevant,
                            include_pending_proposed=False,
                            prior_deliberation=prior,
                        )
                    }
                )
                replacement = replacement.model_copy(
                    update={
                        "artifacts": (
                            *replacement.artifacts,
                            MemoryArtifact(
                                kind=_EVIDENCE_DELIBERATION_KIND,
                                payload=updated.deliberation.model_dump(mode="json"),
                            ),
                        )
                    }
                )
                reassessed.append(updated)
                changed = True

            if changed:
                if memory in self._pending:
                    self._pending = [
                        replacement if pending == memory else pending
                        for pending in self._pending
                    ]
                else:
                    self._stage_replacement(memory, replacement)

        for tension in reassessed:
            semantic_key = (
                _normalized_semantic_value(tension.subject),
                _normalized_semantic_value(tension.attribute),
            )
            evidence_snapshot = tuple(
                observation
                for observation in self._evidence
                if (
                    (signature := _semantic_signature_from_interpretation(
                        observation.semantic_interpretation
                    ))
                    is not None
                    and signature[:2] == semantic_key
                    and signature[2]
                    in {
                        _normalized_semantic_value(tension.existing_value),
                        _normalized_semantic_value(tension.proposed_value),
                    }
                )
            )
            self._reassessment_events.append((tension, evidence_snapshot))
        self._tension_reassessments.extend(reassessed)
        return reassessed

    async def _consider_belief_reframe(
        self,
        call: ReframeBeliefCall,
    ) -> BeliefReframeDecision:
        memories = await self._working_memories()
        semantic_key = (
            _normalized_semantic_value(call.subject),
            _normalized_semantic_value(call.attribute),
        )
        requested_existing = _normalized_semantic_value(call.existing_value)
        requested_proposed = _normalized_semantic_value(call.proposed_value)

        latest: tuple[int, DurableMemory, EvidenceDeliberation] | None = None
        for memory in memories:
            for artifact in memory.artifacts:
                if artifact.kind != _EVIDENCE_DELIBERATION_KIND:
                    continue
                deliberation = EvidenceDeliberation.model_validate(artifact.payload)
                if deliberation.subject is None or deliberation.attribute is None:
                    continue
                if (
                    _normalized_semantic_value(deliberation.subject),
                    _normalized_semantic_value(deliberation.attribute),
                ) != semantic_key:
                    continue
                if (
                    _normalized_semantic_value(deliberation.existing_value)
                    != requested_existing
                    or _normalized_semantic_value(deliberation.proposed_value)
                    != requested_proposed
                ):
                    continue
                if latest is None or deliberation.revision > latest[0]:
                    latest = (deliberation.revision, memory, deliberation)

        if latest is None:
            return BeliefReframeDecision(
                accepted=False,
                reason="No matching deliberation exists for this belief reframe.",
                subject=call.subject,
                attribute=call.attribute,
                existing_value=call.existing_value,
                proposed_value=call.proposed_value,
            )

        revision, reframe_memory, deliberation = latest
        readiness = deliberation.resolution_readiness
        finding = deliberation.tension_finding
        if readiness is None or readiness.status != "reframe_required" or finding is None:
            return BeliefReframeDecision(
                accepted=False,
                reason=(
                    "The latest matching deliberation does not require a belief reframe."
                ),
                subject=call.subject,
                attribute=call.attribute,
                existing_value=call.existing_value,
                proposed_value=call.proposed_value,
                deliberation_revision=revision,
            )

        existing_scope = finding.existing_scope
        proposed_scope = finding.proposed_scope
        if not existing_scope or not proposed_scope:
            return BeliefReframeDecision(
                accepted=False,
                reason=(
                    "The evidence establishes that reframing is required but does not yet provide explicit scopes for both values."
                ),
                subject=call.subject,
                attribute=call.attribute,
                existing_value=call.existing_value,
                proposed_value=call.proposed_value,
                deliberation_revision=revision,
            )

        temporal = finding.temporal_relationship == "changed_over_time"
        contextual = finding.contextual_relationship == "different_contexts"
        if temporal and contextual:
            relationship = "temporal_contextual"
        elif temporal:
            relationship = "temporal"
        elif contextual:
            relationship = "contextual"
        else:
            return BeliefReframeDecision(
                accepted=False,
                reason="The evidence no longer supports temporal or contextual reframing.",
                subject=call.subject,
                attribute=call.attribute,
                existing_value=call.existing_value,
                proposed_value=call.proposed_value,
                deliberation_revision=revision,
            )

        existing_reframes = _latest_belief_reframes(memories)
        reframe_key = (
            semantic_key[0],
            semantic_key[1],
            requested_existing,
            requested_proposed,
        )
        committed = existing_reframes.get(reframe_key)
        if (
            committed is not None
            and int(committed.get("deliberation_revision", 0)) >= revision
        ):
            return BeliefReframeDecision(
                accepted=False,
                reason="This tension has already been reframed at this deliberation revision.",
                subject=call.subject,
                attribute=call.attribute,
                relationship=relationship,
                existing_value=call.existing_value,
                proposed_value=call.proposed_value,
                existing_scope=str(committed.get("existing_scope", existing_scope)),
                proposed_scope=str(committed.get("proposed_scope", proposed_scope)),
                deliberation_revision=int(
                    committed.get("deliberation_revision", revision)
                ),
            )

        existing_evidence: list[str] = []
        proposed_evidence: list[str] = []
        staged_replacements: list[tuple[DurableMemory, DurableMemory]] = []

        for memory in memories:
            interpretations = _semantic_interpretations(memory.artifacts)
            scoped_payload: dict[str, Any] | None = None
            for signature, payload in interpretations.items():
                if signature[:2] != semantic_key:
                    continue
                if signature[2] == requested_existing:
                    existing_evidence.append(memory.content)
                    scoped_payload = {
                        "subject": call.subject,
                        "attribute": call.attribute,
                        "value": payload.get("value"),
                        "scope": existing_scope,
                        "relationship": relationship,
                        "status": "valid_in_scope",
                        "deliberation_revision": revision,
                    }
                    break
                if signature[2] == requested_proposed:
                    proposed_evidence.append(memory.content)
                    scoped_payload = {
                        "subject": call.subject,
                        "attribute": call.attribute,
                        "value": payload.get("value"),
                        "scope": proposed_scope,
                        "relationship": relationship,
                        "status": "valid_in_scope",
                        "deliberation_revision": revision,
                    }
                    break

            artifacts = list(memory.artifacts)
            if scoped_payload is not None:
                artifacts.append(
                    MemoryArtifact(
                        kind=_SCOPED_BELIEF_KIND,
                        payload=scoped_payload,
                    )
                )

            if memory == reframe_memory:
                artifacts.append(
                    MemoryArtifact(
                        kind=_BELIEF_REFRAME_KIND,
                        payload={
                            "status": "committed",
                            "subject": call.subject,
                            "attribute": call.attribute,
                            "relationship": relationship,
                            "existing_value": call.existing_value,
                            "existing_scope": existing_scope,
                            "proposed_value": call.proposed_value,
                            "proposed_scope": proposed_scope,
                            "deliberation_revision": revision,
                            "basis": list(finding.basis),
                        },
                    )
                )

            if tuple(artifacts) != memory.artifacts:
                staged_replacements.append(
                    (
                        memory,
                        memory.model_copy(update={"artifacts": tuple(artifacts)}),
                    )
                )

        if not existing_evidence or not proposed_evidence:
            return BeliefReframeDecision(
                accepted=False,
                reason=(
                    "Reframe-required deliberation could not be mapped back to both durable evidence sets."
                ),
                subject=call.subject,
                attribute=call.attribute,
                relationship=relationship,
                existing_value=call.existing_value,
                proposed_value=call.proposed_value,
                existing_scope=existing_scope,
                proposed_scope=proposed_scope,
                deliberation_revision=revision,
            )

        for original, replacement in staged_replacements:
            self._stage_replacement(original, replacement)

        decision = BeliefReframeDecision(
            accepted=True,
            reason=(
                "Belief reframe accepted; both values remain valid within their evidence-backed scopes."
            ),
            subject=call.subject,
            attribute=call.attribute,
            relationship=relationship,
            existing_value=call.existing_value,
            proposed_value=call.proposed_value,
            existing_scope=existing_scope,
            proposed_scope=proposed_scope,
            deliberation_revision=revision,
        )
        self._reframe_events.append(
            {
                "source": "conscious_memory_steward",
                "status": "committed",
                "subject": call.subject,
                "attribute": call.attribute,
                "relationship": relationship,
                "existing_value": call.existing_value,
                "existing_scope": existing_scope,
                "proposed_value": call.proposed_value,
                "proposed_scope": proposed_scope,
                "deliberation_revision": revision,
                "basis": list(finding.basis),
                "existing_evidence": existing_evidence,
                "proposed_evidence": proposed_evidence,
            }
        )
        return decision


    async def _consider_belief_transition(
        self,
        call: TransitionBeliefCall,
    ) -> BeliefTransitionDecision:
        memories = await self._working_memories()
        semantic_key = (
            _normalized_semantic_value(call.subject),
            _normalized_semantic_value(call.attribute),
        )
        requested_value = _normalized_semantic_value(call.candidate_value)

        latest_by_pair: dict[
            tuple[str, str, str, str],
            tuple[int, DurableMemory, EvidenceDeliberation],
        ] = {}
        for memory in memories:
            for artifact in memory.artifacts:
                if artifact.kind != _EVIDENCE_DELIBERATION_KIND:
                    continue
                deliberation = EvidenceDeliberation.model_validate(artifact.payload)
                if deliberation.subject is None or deliberation.attribute is None:
                    continue
                if (
                    _normalized_semantic_value(deliberation.subject),
                    _normalized_semantic_value(deliberation.attribute),
                ) != semantic_key:
                    continue
                pair = (
                    semantic_key[0],
                    semantic_key[1],
                    _normalized_semantic_value(deliberation.existing_value),
                    _normalized_semantic_value(deliberation.proposed_value),
                )
                prior = latest_by_pair.get(pair)
                if prior is None or deliberation.revision > prior[0]:
                    latest_by_pair[pair] = (
                        deliberation.revision,
                        memory,
                        deliberation,
                    )

        eligible: list[tuple[int, DurableMemory, EvidenceDeliberation]] = []
        for revision, memory, deliberation in latest_by_pair.values():
            readiness = deliberation.resolution_readiness
            if readiness is None or readiness.status != "candidate_ready":
                continue
            if _normalized_semantic_value(readiness.candidate_value) != requested_value:
                continue
            eligible.append((revision, memory, deliberation))

        if not eligible:
            return BeliefTransitionDecision(
                accepted=False,
                reason=(
                    "No latest candidate-ready deliberation authorizes this belief transition."
                ),
                subject=call.subject,
                attribute=call.attribute,
                to_value=call.candidate_value,
            )

        revision, transition_memory, deliberation = max(
            eligible,
            key=lambda item: item[0],
        )
        readiness = deliberation.resolution_readiness
        if readiness is None:
            raise RuntimeError("Candidate-ready deliberation lost its readiness assessment")

        current_beliefs = _latest_current_beliefs(memories)
        current = current_beliefs.get(semantic_key)
        if (
            current is not None
            and _normalized_semantic_value(current.get("to_value")) == requested_value
            and int(current.get("deliberation_revision", 0)) >= revision
        ):
            return BeliefTransitionDecision(
                accepted=False,
                reason="This candidate is already the current belief.",
                subject=call.subject,
                attribute=call.attribute,
                from_value=current.get("from_value"),
                to_value=current.get("to_value"),
                deliberation_revision=int(current.get("deliberation_revision", revision)),
            )

        if readiness.candidate_side == "existing":
            from_value = deliberation.proposed_value
        elif readiness.candidate_side == "proposed":
            from_value = deliberation.existing_value
        else:
            return BeliefTransitionDecision(
                accepted=False,
                reason="Candidate-ready deliberation does not identify a transition side.",
                subject=call.subject,
                attribute=call.attribute,
                to_value=call.candidate_value,
            )

        from_normalized = _normalized_semantic_value(from_value)
        candidate_evidence: list[str] = []
        superseded_evidence: list[str] = []
        staged_replacements: list[tuple[DurableMemory, DurableMemory]] = []

        for memory in memories:
            interpretations = _semantic_interpretations(memory.artifacts)
            status: str | None = None
            matched_value: Any = None
            for signature, payload in interpretations.items():
                if signature[:2] != semantic_key:
                    continue
                if signature[2] == requested_value:
                    status = "current"
                    matched_value = payload.get("value")
                    candidate_evidence.append(memory.content)
                    break
                if signature[2] == from_normalized:
                    status = "superseded"
                    matched_value = payload.get("value")
                    superseded_evidence.append(memory.content)
                    break

            artifacts = list(memory.artifacts)
            if status is not None:
                artifacts.append(
                    MemoryArtifact(
                        kind=_BELIEF_STATUS_KIND,
                        payload={
                            "subject": call.subject,
                            "attribute": call.attribute,
                            "value": matched_value,
                            "status": status,
                            "current_value": call.candidate_value,
                            "deliberation_revision": revision,
                        },
                    )
                )

            if memory == transition_memory:
                artifacts.append(
                    MemoryArtifact(
                        kind=_BELIEF_TRANSITION_KIND,
                        payload={
                            "status": "committed",
                            "subject": call.subject,
                            "attribute": call.attribute,
                            "from_value": from_value,
                            "to_value": call.candidate_value,
                            "deliberation_revision": revision,
                            "readiness_basis": list(readiness.basis),
                        },
                    )
                )

            if tuple(artifacts) != memory.artifacts:
                staged_replacements.append(
                    (
                        memory,
                        memory.model_copy(update={"artifacts": tuple(artifacts)}),
                    )
                )

        if not candidate_evidence or not superseded_evidence:
            return BeliefTransitionDecision(
                accepted=False,
                reason=(
                    "Candidate-ready deliberation could not be mapped back to both competing durable evidence sets."
                ),
                subject=call.subject,
                attribute=call.attribute,
                from_value=from_value,
                to_value=call.candidate_value,
                deliberation_revision=revision,
            )

        for original, replacement in staged_replacements:
            self._stage_replacement(original, replacement)

        decision = BeliefTransitionDecision(
            accepted=True,
            reason=(
                "Candidate-ready belief transition accepted; evidence is preserved and the prior value is superseded rather than deleted."
            ),
            subject=call.subject,
            attribute=call.attribute,
            from_value=from_value,
            to_value=call.candidate_value,
            deliberation_revision=revision,
        )
        self._transition_events.append(
            {
                "source": "conscious_memory_steward",
                "subject": call.subject,
                "attribute": call.attribute,
                "from_value": from_value,
                "to_value": call.candidate_value,
                "deliberation_revision": revision,
                "readiness_basis": list(readiness.basis),
                "candidate_evidence": candidate_evidence,
                "superseded_evidence": superseded_evidence,
                "status": "committed",
            }
        )
        return decision


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

        existing = await self._working_memories()
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
                    if _belief_status_for_signature(memory, existing_signature) == "superseded":
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
                        current_evidence=tuple(self._evidence),
                        include_pending_proposed=True,
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
        current_beliefs = _latest_current_beliefs(memories)
        current_reframes = _latest_belief_reframes(memories)
        if memories:
            parts.append(
                "Established memory: " + " | ".join(memory.content for memory in memories)
            )
        if current_beliefs:
            parts.append(
                "Current belief: "
                + " | ".join(
                    f"{payload.get('subject')} · {payload.get('attribute')} = {payload.get('to_value')} "
                    f"(superseded {payload.get('from_value')})"
                    for payload in current_beliefs.values()
                )
            )
        if current_reframes:
            parts.append(
                "Scoped belief: "
                + " | ".join(
                    f"{payload.get('subject')} · {payload.get('attribute')} = "
                    f"{payload.get('existing_value')} [{payload.get('existing_scope')}] ; "
                    f"{payload.get('proposed_value')} [{payload.get('proposed_scope')}]"
                    for payload in current_reframes.values()
                )
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
            seen_deliberations: set[tuple[str, str, str, str]] = set()
            for artifact in reversed(memory.artifacts):
                if artifact.kind != _EVIDENCE_DELIBERATION_KIND:
                    continue
                payload = artifact.payload
                deliberation = EvidenceDeliberation.model_validate(payload)
                if (
                    _deliberation_closed_by_transition(deliberation, current_beliefs)
                    or _deliberation_closed_by_reframe(deliberation, current_reframes)
                ):
                    continue
                key = (
                    _normalized_semantic_value(payload.get("subject")),
                    _normalized_semantic_value(payload.get("attribute")),
                    _normalized_semantic_value(payload.get("existing_value")),
                    _normalized_semantic_value(payload.get("proposed_value")),
                )
                if key in seen_deliberations:
                    continue
                seen_deliberations.add(key)
                for question in payload.get("investigation_questions", []):
                    if isinstance(question, str) and question not in investigation_questions:
                        investigation_questions.append(question)
        if investigation_questions:
            parts.append(
                "Investigation guidance: " + " | ".join(investigation_questions)
            )

        readiness_notes: list[str] = []
        for memory in memories:
            seen_readiness: set[tuple[str, str, str, str]] = set()
            for artifact in reversed(memory.artifacts):
                if artifact.kind != _EVIDENCE_DELIBERATION_KIND:
                    continue
                payload = artifact.payload
                deliberation = EvidenceDeliberation.model_validate(payload)
                if (
                    _deliberation_closed_by_transition(deliberation, current_beliefs)
                    or _deliberation_closed_by_reframe(deliberation, current_reframes)
                ):
                    continue
                key = (
                    _normalized_semantic_value(payload.get("subject")),
                    _normalized_semantic_value(payload.get("attribute")),
                    _normalized_semantic_value(payload.get("existing_value")),
                    _normalized_semantic_value(payload.get("proposed_value")),
                )
                if key in seen_readiness:
                    continue
                seen_readiness.add(key)
                readiness = payload.get("resolution_readiness")
                if not isinstance(readiness, dict):
                    continue
                status = str(readiness.get("status", "blocked"))
                candidate = readiness.get("candidate_value")
                if status == "candidate_ready":
                    readiness_notes.append(
                        f"Candidate ready for later belief transition: {candidate}"
                    )
                elif status == "reframe_required":
                    readiness_notes.append(
                        "Belief reframe required: competing values apply to different time/context."
                    )
                else:
                    blockers = readiness.get("blockers", [])
                    if blockers:
                        readiness_notes.append(
                            "Resolution blocked: " + "; ".join(str(item) for item in blockers)
                        )
        if readiness_notes:
            parts.append("Resolution readiness: " + " | ".join(readiness_notes))

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
