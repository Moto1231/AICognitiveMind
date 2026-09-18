from enum import StrEnum

from pydantic import BaseModel, Field

PROTOTYPE_CONTRADICTION_EPSILON = 0.05


class EvidenceScorecard(BaseModel):
    """Independent confidence and weight at one cognitive boundary."""

    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)

    @property
    def support(self) -> float:
        """ADR 0008 prototype support; never replaces the stored inputs."""
        return self.confidence * self.weight


class EvidenceAssessment(BaseModel):
    """One proposition with preserved prior and current effective scorecards."""

    proposition: str = Field(min_length=1)
    prior: EvidenceScorecard
    effective: EvidenceScorecard

    @property
    def support(self) -> float:
        """Contradiction adjudication uses the current effective scorecard."""
        return self.effective.support


class ContradictionAdjudication(BaseModel):
    resolved: bool
    preferred_proposition: str | None = None
    support_delta: float = Field(ge=0.0)
    clarification_required: bool = False


class EvidenceResolutionAction(StrEnum):
    ACCEPT = "accept"
    EXPAND_RECALL = "expand_recall"
    CLARIFY = "clarify"


class RecursiveRecallBudget(BaseModel):
    """Prototype bound for a supporting-evidence rabbit hole."""

    max_depth: int = Field(default=3, ge=0)
    max_evidence_items: int = Field(default=12, ge=1)


class RecursiveRecallState(BaseModel):
    depth: int = Field(default=0, ge=0)
    evidence_items_examined: int = Field(default=0, ge=0)


class EvidenceResolutionPlan(BaseModel):
    action: EvidenceResolutionAction
    reason: str


def adjudicate_contradiction(
    first: EvidenceAssessment,
    second: EvidenceAssessment,
    epsilon: float = PROTOTYPE_CONTRADICTION_EPSILON,
) -> ContradictionAdjudication:
    """Compare effective evidence using the ADR 0008 prototype rule."""
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


def plan_evidence_resolution(
    adjudication: ContradictionAdjudication,
    *,
    supporting_evidence_available: bool,
    state: RecursiveRecallState,
    budget: RecursiveRecallBudget,
) -> EvidenceResolutionPlan:
    """Decide whether to conclude, follow support, or ask for clarification."""
    if adjudication.resolved:
        return EvidenceResolutionPlan(
            action=EvidenceResolutionAction.ACCEPT,
            reason="The current effective evidence materially favors one proposition.",
        )

    within_budget = (
        state.depth < budget.max_depth
        and state.evidence_items_examined < budget.max_evidence_items
    )
    if supporting_evidence_available and within_budget:
        return EvidenceResolutionPlan(
            action=EvidenceResolutionAction.EXPAND_RECALL,
            reason=(
                "The contradiction is unresolved and supporting evidence remains "
                "available within the recursive recall budget."
            ),
        )

    return EvidenceResolutionPlan(
        action=EvidenceResolutionAction.CLARIFY,
        reason=(
            "The contradiction remains unresolved and no useful bounded supporting "
            "evidence expansion remains."
        ),
    )
