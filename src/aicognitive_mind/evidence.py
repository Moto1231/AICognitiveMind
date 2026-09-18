from pydantic import BaseModel, Field


PROTOTYPE_CONTRADICTION_EPSILON = 0.05


class EvidenceAssessment(BaseModel):
    """Independent confidence and weight for one candidate proposition."""

    proposition: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0, le=1.0)

    @property
    def support(self) -> float:
        """ADR 0008 prototype support; not a stored replacement for either input."""
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
    """Compare competing propositions using the ADR 0008 prototype rule."""
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
