import unittest

from aicognitive_mind.evidence import (
    EvidenceAssessment,
    EvidenceProvenanceHop,
    EvidenceResolutionAction,
    EvidenceScorecard,
    RecursiveRecallBudget,
    RecursiveRecallState,
    adjudicate_contradiction,
    plan_evidence_resolution,
)


class EvidenceAssessmentTests(unittest.TestCase):
    def test_effective_scorecard_drives_support_without_overwriting_prior(self) -> None:
        prior = EvidenceScorecard(confidence=0.9, weight=0.4)
        effective = EvidenceScorecard(confidence=0.6, weight=0.8)
        assessment = EvidenceAssessment(
            proposition="Michael's birthday is January 4.",
            prior=prior,
            effective=effective,
        )

        self.assertAlmostEqual(assessment.support, 0.48)
        self.assertEqual(assessment.prior.confidence, 0.9)
        self.assertEqual(assessment.prior.weight, 0.4)

    def test_provenance_preserves_source_chain_conditions_and_context(self) -> None:
        assessment = EvidenceAssessment(
            proposition="Michael's birthday is January 3.",
            prior=EvidenceScorecard(confidence=0.72, weight=0.55),
            effective=EvidenceScorecard(confidence=0.81, weight=0.60),
            provenance=(
                EvidenceProvenanceHop(
                    source="William",
                    obtained_from="Michael",
                    condition="William is relaying an earlier conversation.",
                    context="William reports Michael's birthday.",
                    scorecard=EvidenceScorecard(confidence=0.72, weight=0.55),
                ),
                EvidenceProvenanceHop(
                    source="Michael",
                    condition="Michael was speaking about his own birthday.",
                    context="Original first-person source.",
                    scorecard=EvidenceScorecard(confidence=0.90, weight=0.50),
                ),
            ),
            current_condition="Michael is now present and discussing his birthday.",
            current_context="Current conscious workspace is resolving a birthday contradiction.",
        )

        self.assertTrue(assessment.has_upstream_provenance)
        self.assertEqual(assessment.provenance[0].source, "William")
        self.assertEqual(assessment.provenance[0].obtained_from, "Michael")
        self.assertEqual(assessment.provenance[1].source, "Michael")
        self.assertEqual(assessment.prior.confidence, 0.72)
        self.assertEqual(assessment.effective.confidence, 0.81)

    def test_direct_evidence_can_have_single_source_without_upstream_chain(self) -> None:
        assessment = EvidenceAssessment(
            proposition="My birthday is January 4.",
            prior=EvidenceScorecard(confidence=0.85, weight=0.50),
            effective=EvidenceScorecard(confidence=0.90, weight=0.60),
            provenance=(
                EvidenceProvenanceHop(
                    source="Michael",
                    condition="Direct first-person statement.",
                    context="Michael is speaking about himself.",
                ),
            ),
        )

        self.assertFalse(assessment.has_upstream_provenance)
        self.assertEqual(len(assessment.provenance), 1)

    def test_materially_stronger_effective_support_is_preferred(self) -> None:
        first = EvidenceAssessment(
            proposition="Michael's birthday is January 3.",
            prior=EvidenceScorecard(confidence=0.9, weight=0.8),
            effective=EvidenceScorecard(confidence=0.6, weight=0.6),
        )
        second = EvidenceAssessment(
            proposition="Michael's birthday is January 4.",
            prior=EvidenceScorecard(confidence=0.5, weight=0.5),
            effective=EvidenceScorecard(confidence=0.9, weight=0.8),
        )

        decision = adjudicate_contradiction(first, second)

        self.assertTrue(decision.resolved)
        self.assertEqual(
            decision.preferred_proposition,
            "Michael's birthday is January 4.",
        )

    def test_tied_support_expands_recall_before_clarification_when_support_exists(self) -> None:
        tied = adjudicate_contradiction(
            EvidenceAssessment(
                proposition="January 3",
                prior=EvidenceScorecard(confidence=0.8, weight=0.5),
                effective=EvidenceScorecard(confidence=0.8, weight=0.5),
            ),
            EvidenceAssessment(
                proposition="January 4",
                prior=EvidenceScorecard(confidence=0.5, weight=0.8),
                effective=EvidenceScorecard(confidence=0.5, weight=0.8),
            ),
        )

        plan = plan_evidence_resolution(
            tied,
            supporting_evidence_available=True,
            state=RecursiveRecallState(depth=0, evidence_items_examined=2),
            budget=RecursiveRecallBudget(max_depth=3, max_evidence_items=12),
        )

        self.assertEqual(plan.action, EvidenceResolutionAction.EXPAND_RECALL)

    def test_tied_support_clarifies_when_no_supporting_evidence_remains(self) -> None:
        tied = adjudicate_contradiction(
            EvidenceAssessment(
                proposition="January 3",
                prior=EvidenceScorecard(confidence=0.8, weight=0.5),
                effective=EvidenceScorecard(confidence=0.8, weight=0.5),
            ),
            EvidenceAssessment(
                proposition="January 4",
                prior=EvidenceScorecard(confidence=0.5, weight=0.8),
                effective=EvidenceScorecard(confidence=0.5, weight=0.8),
            ),
        )

        plan = plan_evidence_resolution(
            tied,
            supporting_evidence_available=False,
            state=RecursiveRecallState(),
            budget=RecursiveRecallBudget(),
        )

        self.assertEqual(plan.action, EvidenceResolutionAction.CLARIFY)

    def test_tied_support_clarifies_when_recall_budget_is_exhausted(self) -> None:
        tied = adjudicate_contradiction(
            EvidenceAssessment(
                proposition="January 3",
                prior=EvidenceScorecard(confidence=0.8, weight=0.5),
                effective=EvidenceScorecard(confidence=0.8, weight=0.5),
            ),
            EvidenceAssessment(
                proposition="January 4",
                prior=EvidenceScorecard(confidence=0.5, weight=0.8),
                effective=EvidenceScorecard(confidence=0.5, weight=0.8),
            ),
        )

        plan = plan_evidence_resolution(
            tied,
            supporting_evidence_available=True,
            state=RecursiveRecallState(depth=3, evidence_items_examined=5),
            budget=RecursiveRecallBudget(max_depth=3, max_evidence_items=12),
        )

        self.assertEqual(plan.action, EvidenceResolutionAction.CLARIFY)


if __name__ == "__main__":
    unittest.main()
