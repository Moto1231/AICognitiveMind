import json
import unittest

from aicognitive_mind.mcp_service import (
    BeliefReframeProposal,
    BeliefTransitionProposal,
    CognitiveMcpService,
    MemoryProposal,
)
from aicognitive_mind.memory_steward import (
    EvidenceAppraisal,
    MemoryArtifactProposal,
    ProvenanceHop,
    ResearchObservation,
    SemanticInterpretation,
    SemanticScope,
    TensionInvestigationFinding,
)
from aicognitive_mind.domain import MemoryClass
from aicognitive_mind.storage import (
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class CognitiveMcpServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.journal = InMemoryJournalStore()
        self.memory = InMemoryMemoryStore()
        self.service = CognitiveMcpService(
            mind=InMemoryMindStore(),
            journal=self.journal,
            memory=self.memory,
        )
        await self.service.initialize(
            "Genesis",
            ("Understanding before Recommending", "Preserve continuity of identity"),
        )

    async def test_memory_survives_between_host_driven_interactions(self) -> None:
        first = await self.service.begin_interaction(
            "My birthday is February 7. Remember that."
        )
        self.assertEqual(first["status"], "ready_to_reason")

        completed = await self.service.complete_interaction(
            user_message="My birthday is February 7. Remember that.",
            response_text="I'll remember that your birthday is February 7.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Will's birthday is February 7.",
                    associations=("Will", "birthday", "February 7"),
                    grounding=("Will directly stated his birthday.",),
                ),
            ),
        )
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertTrue(completed["memory_decisions"][0]["accepted"])

        later = await self.service.begin_interaction("When is Will's birthday?")
        recalled = later["recalled_context"]
        durable = recalled["durable_memory"]

        self.assertEqual(len(durable), 1)
        self.assertEqual(durable[0]["content"], "Will's birthday is February 7.")


    async def test_memory_artifacts_are_materialized_by_steward_and_recalled(self) -> None:
        completed = await self.service.complete_interaction(
            user_message="My birthday is February 7.",
            response_text="I'll remember your birthday.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The user's birthday is February 7.",
                    associations=("birthday", "February 7"),
                    grounding=("direct-user-statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "current_human",
                                "attribute": "birthday",
                                "value": "February 7",
                            },
                        ),
                    ),
                ),
            ),
        )

        decision = completed["memory_decisions"][0]
        self.assertTrue(decision["accepted"])
        artifact = decision["memory"]["artifacts"][0]
        self.assertEqual(artifact["kind"], "semantic_interpretation")
        self.assertEqual(artifact["formed_by"], "conscious_memory_steward")
        self.assertEqual(artifact["payload"]["attribute"], "birthday")

        later = await self.service.begin_interaction("What birthday do you remember?")
        recalled = later["recalled_context"]["durable_memory"]
        self.assertEqual(recalled[0]["artifacts"][0]["payload"]["value"], "February 7")



    async def test_mcp_completion_accepts_appraised_current_evidence(self) -> None:
        completed = await self.service.complete_interaction(
            user_message="What does the current evidence say?",
            response_text="The current evidence is recorded separately from durable memory.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="current source",
                    response="A source reports a material update.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.75,
                        weight=0.5,
                        provenance=(
                            ProvenanceHop(
                                source="current source",
                                context="active interaction",
                                condition="externally supplied",
                            ),
                        ),
                        basis=("source identity is known",),
                    ),
                ),
            ),
        )

        self.assertEqual(completed["status"], "interaction_committed")
        journal = await self.journal.read()
        interaction = journal[-1]
        considered = interaction.experience["memory_steward"]["evidence_considered"]
        self.assertEqual(len(considered), 1)
        appraisal = considered[0]["appraisal"]
        self.assertEqual(appraisal["confidence"], 0.75)
        self.assertEqual(appraisal["weight"], 0.5)
        self.assertEqual(appraisal["provenance"][0]["source"], "current source")
        self.assertNotIn("combined_score", appraisal)

    async def test_mcp_interaction_surfaces_and_journals_semantic_tension(self) -> None:
        await self.service.complete_interaction(
            user_message="My birthday is February 7.",
            response_text="I'll remember that.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The user's birthday is February 7.",
                    grounding=("direct-user-statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "current_human",
                                "attribute": "birthday",
                                "value": "February 7",
                            },
                        ),
                    ),
                ),
            ),
        )

        completed = await self.service.complete_interaction(
            user_message="Actually, my birthday is February 8.",
            response_text="I have conflicting birthday evidence and will preserve both.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The user's birthday is February 8.",
                    grounding=("direct-user-statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "current_human",
                                "attribute": "birthday",
                                "value": "February 8",
                            },
                        ),
                    ),
                ),
            ),
        )

        decision = completed["memory_decisions"][0]
        self.assertTrue(decision["accepted"])
        self.assertEqual(len(decision["tensions"]), 1)
        self.assertEqual(decision["tensions"][0]["status"], "unresolved")
        deliberation = decision["tensions"][0]["deliberation"]
        self.assertEqual(deliberation["provenance_relationship"], "unknown")
        self.assertTrue(deliberation["investigation_questions"])

        later = await self.service.begin_interaction("What birthday should I rely on?")
        self.assertIn("Investigation guidance:", later["recalled_context"]["summary"])
        self.assertIn("investigation guidance", later["next_step"])

        journal = await self.journal.read()
        tension_entries = [entry for entry in journal if entry.kind.value == "tension"]
        self.assertEqual(len(tension_entries), 1)
        self.assertEqual(
            tension_entries[0].experience["competing_values"]["existing"],
            "February 7",
        )
        self.assertEqual(journal[-1].kind.value, "interaction")

    async def test_current_evidence_participates_when_tension_is_first_detected(self) -> None:
        await self.service.complete_interaction(
            user_message="The deployment date is October 1.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 1.",
                    grounding=("approved plan",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.8,
                                "weight": 0.7,
                                "provenance": [
                                    {
                                        "source": "approved plan",
                                        "context": "release planning",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )

        completed = await self.service.complete_interaction(
            user_message="The deployment date may be October 8.",
            response_text="I have competing evidence and will keep it unresolved.",
            current_evidence=(
                ResearchObservation(
                    query="latest deployment status",
                    response="The release board lists October 8.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.85,
                        weight=0.65,
                        provenance=(
                            ProvenanceHop(
                                source="release board",
                                context="current status",
                                condition="published",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="deployment",
                        attribute="date",
                        value="October 8",
                    ),
                ),
            ),
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 8.",
                    grounding=("status statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 8",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.75,
                                "weight": 0.6,
                                "provenance": [
                                    {
                                        "source": "project lead",
                                        "context": "status meeting",
                                        "condition": "verbal update",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )

        tension = completed["memory_decisions"][0]["tensions"][0]
        deliberation = tension["deliberation"]
        self.assertEqual(deliberation["revision"], 1)
        self.assertEqual(deliberation["trigger"], "tension_detected")
        self.assertEqual(deliberation["proposed_support_count"], 2)
        self.assertEqual(deliberation["current_proposed_support_count"], 1)
        self.assertEqual(completed["tension_reassessments"], [])

    async def test_later_current_evidence_reassesses_and_persists_tension_history(self) -> None:
        await self.service.complete_interaction(
            user_message="The deployment date is October 1.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 1.",
                    grounding=("approved plan",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.8,
                                "weight": 0.7,
                                "provenance": [
                                    {
                                        "source": "approved plan",
                                        "context": "release planning",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The deployment date is October 8.",
            response_text="That creates an unresolved tension.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 8.",
                    grounding=("status statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 8",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.75,
                                "weight": 0.6,
                                "provenance": [
                                    {
                                        "source": "project lead",
                                        "context": "status meeting",
                                        "condition": "verbal update",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )

        completed = await self.service.complete_interaction(
            user_message="I found more evidence about the deployment date.",
            response_text="The tension has been re-deliberated but remains unresolved.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="release calendar",
                    response="The release board independently lists October 8.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.9,
                        weight=0.55,
                        provenance=(
                            ProvenanceHop(
                                source="release board",
                                context="current release calendar",
                                condition="published",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="deployment",
                        attribute="date",
                        value="October 8",
                    ),
                ),
            ),
        )

        self.assertEqual(len(completed["tension_reassessments"]), 1)
        reassessment = completed["tension_reassessments"][0]
        self.assertEqual(reassessment["status"], "unresolved")
        deliberation = reassessment["deliberation"]
        self.assertEqual(deliberation["revision"], 2)
        self.assertEqual(deliberation["trigger"], "current_evidence_reassessment")
        self.assertEqual(deliberation["existing_support_count"], 1)
        self.assertEqual(deliberation["proposed_support_count"], 2)
        self.assertEqual(deliberation["current_evidence_considered"], 1)
        self.assertEqual(deliberation["current_proposed_support_count"], 1)
        self.assertEqual(deliberation["resolution_readiness"]["status"], "blocked")
        self.assertIsNone(deliberation["resolution_readiness"]["candidate_value"])

        memories = await self.memory.read()
        self.assertEqual(len(memories), 2)
        tension_memory = next(
            memory for memory in memories if memory.content.endswith("October 8.")
        )
        deliberations = [
            artifact
            for artifact in tension_memory.artifacts
            if artifact.kind == "evidence_deliberation"
        ]
        self.assertEqual([artifact.payload["revision"] for artifact in deliberations], [1, 2])

        tension_entries = [
            entry for entry in await self.journal.read() if entry.kind.value == "tension"
        ]
        self.assertEqual(len(tension_entries), 2)
        self.assertEqual(tension_entries[0].experience["phase"], "detected")
        self.assertEqual(tension_entries[1].experience["phase"], "reassessment")
        self.assertEqual(
            tension_entries[1].experience["current_evidence"][0]["response"],
            "The release board independently lists October 8.",
        )

        later = await self.service.begin_interaction("What is the deployment date?")
        self.assertIn("Investigation guidance:", later["recalled_context"]["summary"])
        self.assertNotIn(
            "Seek independent corroboration for the proposed value.",
            later["recalled_context"]["summary"],
        )

    async def test_resolution_readiness_marks_candidate_without_changing_belief(self) -> None:
        await self.service.complete_interaction(
            user_message="The deployment date is October 1.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 1.",
                    grounding=("approved plan",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.55,
                                "weight": 0.4,
                                "provenance": [
                                    {
                                        "source": "approved plan",
                                        "context": "release decision",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The deployment date is October 8.",
            response_text="That creates an unresolved tension.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 8.",
                    grounding=("project lead update",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 8",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.8,
                                "weight": 0.7,
                                "provenance": [
                                    {
                                        "source": "project lead",
                                        "context": "release decision",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )

        completed = await self.service.complete_interaction(
            user_message="I verified the deployment evidence.",
            response_text="October 8 is ready as a candidate for a later belief transition.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="release board",
                    response="The independently maintained release board lists October 8.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.9,
                        weight=0.75,
                        provenance=(
                            ProvenanceHop(
                                source="release board",
                                context="release decision",
                                condition="published",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="deployment",
                        attribute="date",
                        value="October 8",
                    ),
                    tension_finding=TensionInvestigationFinding(
                        subject="deployment",
                        attribute="date",
                        existing_value="October 1",
                        proposed_value="October 8",
                        provenance_independence="verified_independent",
                        temporal_relationship="same_timeframe",
                        contextual_relationship="same_context",
                        basis=(
                            "The release board is maintained independently of the approved-plan source.",
                            "Both values purport to describe the same release decision and timeframe.",
                        ),
                    ),
                ),
            ),
        )

        reassessment = completed["tension_reassessments"][0]
        readiness = reassessment["deliberation"]["resolution_readiness"]
        self.assertEqual(reassessment["status"], "unresolved")
        self.assertEqual(readiness["status"], "candidate_ready")
        self.assertEqual(readiness["candidate_side"], "proposed")
        self.assertEqual(readiness["candidate_value"], "October 8")
        self.assertEqual(readiness["blockers"], [])
        self.assertEqual(readiness["proposed"]["support_count"], 2)
        self.assertEqual(readiness["proposed"]["distinct_immediate_sources"], 2)
        self.assertGreater(
            readiness["proposed"]["confidence_floor"],
            readiness["existing"]["confidence_ceiling"],
        )
        self.assertGreater(
            readiness["proposed"]["weight_floor"],
            readiness["existing"]["weight_ceiling"],
        )

        refined = await self.service.complete_interaction(
            user_message="A second independent source also confirms October 8.",
            response_text="The readiness assessment remains candidate-ready.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="change log",
                    response="The change log also records October 8.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.88,
                        weight=0.72,
                        provenance=(
                            ProvenanceHop(
                                source="change log",
                                context="release decision",
                                condition="approved",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="deployment",
                        attribute="date",
                        value="October 8",
                    ),
                ),
            ),
        )
        refined_deliberation = refined["tension_reassessments"][0]["deliberation"]
        self.assertEqual(refined_deliberation["revision"], 3)
        self.assertEqual(
            refined_deliberation["resolution_readiness"]["status"],
            "candidate_ready",
        )
        self.assertEqual(
            refined_deliberation["tension_finding"]["provenance_independence"],
            "verified_independent",
        )
        self.assertEqual(
            refined_deliberation["resolution_readiness"]["proposed"]["support_count"],
            3,
        )
        self.assertEqual(len(refined_deliberation["current_evidence_history"]), 2)
        self.assertEqual(
            refined_deliberation["current_evidence_history"][0]["response_excerpt"],
            "The independently maintained release board lists October 8.",
        )

        memories = await self.memory.read()
        self.assertEqual(len(memories), 2)
        self.assertEqual(
            {memory.content for memory in memories},
            {
                "The deployment date is October 1.",
                "The deployment date is October 8.",
            },
        )
        later = await self.service.begin_interaction("What is the deployment date?")
        self.assertIn(
            "Candidate ready for later belief transition: October 8",
            later["recalled_context"]["summary"],
        )

    async def test_resolution_readiness_requires_reframe_for_temporal_change(self) -> None:
        await self.service.complete_interaction(
            user_message="The service owner is Alice.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The service owner is Alice.",
                    grounding=("original assignment",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "service",
                                "attribute": "owner",
                                "value": "Alice",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.8,
                                "weight": 0.8,
                                "provenance": [
                                    {
                                        "source": "assignment record",
                                        "context": "service ownership",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The service owner is Bob.",
            response_text="That creates an unresolved tension until timing is known.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The service owner is Bob.",
                    grounding=("current assignment",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "service",
                                "attribute": "owner",
                                "value": "Bob",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.9,
                                "weight": 0.9,
                                "provenance": [
                                    {
                                        "source": "current assignment record",
                                        "context": "service ownership",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )

        completed = await self.service.complete_interaction(
            user_message="The ownership history explains the difference.",
            response_text="This should be represented as ownership changing over time.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="ownership history",
                    response="The change record shows Alice handed ownership to Bob on September 1.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.95,
                        weight=0.9,
                        provenance=(
                            ProvenanceHop(
                                source="ownership change record",
                                context="service ownership",
                                condition="approved",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="service",
                        attribute="owner",
                        value="Bob",
                    ),
                    tension_finding=TensionInvestigationFinding(
                        subject="service",
                        attribute="owner",
                        existing_value="Alice",
                        proposed_value="Bob",
                        provenance_independence="verified_independent",
                        temporal_relationship="changed_over_time",
                        contextual_relationship="same_context",
                        basis=(
                            "The ownership change record gives an effective-date transition from Alice to Bob.",
                        ),
                        existing_scope="before September 1",
                        proposed_scope="on or after September 1",
                    ),
                ),
            ),
        )

        readiness = completed["tension_reassessments"][0]["deliberation"]["resolution_readiness"]
        self.assertEqual(readiness["status"], "reframe_required")
        self.assertIsNone(readiness["candidate_side"])
        self.assertIsNone(readiness["candidate_value"])
        self.assertTrue(
            any("different times" in item for item in readiness["basis"])
        )

        later = await self.service.begin_interaction("Who owns the service?")
        self.assertIn(
            "Belief reframe required",
            later["recalled_context"]["summary"],
        )
        self.assertNotIn(
            "Check whether the competing values can both be valid at different times",
            later["recalled_context"]["summary"],
        )

        reframed = await self.service.complete_interaction(
            user_message="Represent the ownership change with its established time scopes.",
            response_text="Ownership is now represented as a scoped temporal belief.",
            proposed_memories=(),
            belief_reframes=(
                BeliefReframeProposal(
                    subject="service",
                    attribute="owner",
                    existing_value="Alice",
                    proposed_value="Bob",
                ),
            ),
        )
        decision = reframed["belief_reframe_decisions"][0]
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["relationship"], "temporal")
        self.assertEqual(decision["existing_scope"], "before September 1")
        self.assertEqual(decision["proposed_scope"], "on or after September 1")

        memories = await self.memory.read()
        self.assertEqual(len(memories), 2)
        alice = next(memory for memory in memories if memory.content.endswith("Alice."))
        bob = next(memory for memory in memories if memory.content.endswith("Bob."))
        alice_scopes = [
            artifact.payload
            for artifact in alice.artifacts
            if artifact.kind == "scoped_belief"
        ]
        bob_scopes = [
            artifact.payload
            for artifact in bob.artifacts
            if artifact.kind == "scoped_belief"
        ]
        self.assertEqual(alice_scopes[-1]["status"], "valid_in_scope")
        self.assertEqual(alice_scopes[-1]["scope"], "before September 1")
        self.assertEqual(bob_scopes[-1]["scope"], "on or after September 1")
        self.assertFalse(
            any(
                artifact.kind == "belief_status"
                for memory in memories
                for artifact in memory.artifacts
            )
        )

        reframe_entries = [
            entry for entry in await self.journal.read()
            if entry.kind.value == "belief_reframe"
        ]
        self.assertEqual(len(reframe_entries), 1)
        self.assertEqual(reframe_entries[0].experience["relationship"], "temporal")

        duplicate = await self.service.complete_interaction(
            user_message="Reframe the same ownership history again.",
            response_text="That scoped belief is already committed.",
            proposed_memories=(),
            belief_reframes=(
                BeliefReframeProposal(
                    subject="service",
                    attribute="owner",
                    existing_value="Alice",
                    proposed_value="Bob",
                ),
            ),
        )
        self.assertFalse(duplicate["belief_reframe_decisions"][0]["accepted"])
        self.assertIn("already been reframed", duplicate["belief_reframe_decisions"][0]["reason"])
        self.assertEqual(
            len([
                entry for entry in await self.journal.read()
                if entry.kind.value == "belief_reframe"
            ]),
            1,
        )

        recalled = await self.service.begin_interaction("Who owns the service?")
        summary = recalled["recalled_context"]["summary"]
        self.assertIn(
            "Scoped belief: service · owner = Alice [before September 1] ; Bob [on or after September 1]",
            summary,
        )
        self.assertNotIn("Belief reframe required", summary)
        self.assertNotIn("Resolution readiness:", summary)

    async def test_belief_reframe_rejects_missing_scopes_without_mutation(self) -> None:
        await self.service.complete_interaction(
            user_message="The service region is east.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The service region is east.",
                    grounding=("historical record",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "service",
                                "attribute": "region",
                                "value": "east",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.8,
                                "weight": 0.8,
                                "provenance": [
                                    {
                                        "source": "historical record",
                                        "context": "service region",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The service region is west.",
            response_text="That creates a tension.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The service region is west.",
                    grounding=("current record",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "service",
                                "attribute": "region",
                                "value": "west",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.9,
                                "weight": 0.9,
                                "provenance": [
                                    {
                                        "source": "current record",
                                        "context": "service region",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The values changed over time.",
            response_text="A temporal reframe is required, but the exact scopes are not established.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="region history",
                    response="The history confirms a change from east to west but gives no effective date.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.9,
                        weight=0.8,
                        provenance=(
                            ProvenanceHop(
                                source="region history",
                                context="service region",
                                condition="incomplete timeline",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="service",
                        attribute="region",
                        value="west",
                    ),
                    tension_finding=TensionInvestigationFinding(
                        subject="service",
                        attribute="region",
                        existing_value="east",
                        proposed_value="west",
                        provenance_independence="verified_independent",
                        temporal_relationship="changed_over_time",
                        contextual_relationship="same_context",
                        basis=("The region changed, but the effective boundary is unknown.",),
                    ),
                ),
            ),
        )

        rejected = await self.service.complete_interaction(
            user_message="Reframe the service region.",
            response_text="The reframe cannot be committed until both scopes are established.",
            proposed_memories=(),
            belief_reframes=(
                BeliefReframeProposal(
                    subject="service",
                    attribute="region",
                    existing_value="east",
                    proposed_value="west",
                ),
            ),
        )
        self.assertFalse(rejected["belief_reframe_decisions"][0]["accepted"])
        self.assertIn("does not yet provide explicit scopes", rejected["belief_reframe_decisions"][0]["reason"])
        self.assertFalse(
            any(
                artifact.kind in {"belief_reframe", "scoped_belief"}
                for memory in await self.memory.read()
                for artifact in memory.artifacts
            )
        )

    async def test_semantic_scope_controls_equivalence_and_tension(self) -> None:
        customer_a = SemanticScope(kind="contextual", label="Customer A")
        customer_b = SemanticScope(kind="contextual", label="Customer B")

        await self.service.complete_interaction(
            user_message="Customer A uses route Alpha.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Customer A approval route is Alpha.",
                    grounding=("Customer A configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Alpha",
                                "scope": customer_a.model_dump(mode="json"),
                            },
                        ),
                    ),
                ),
            ),
        )

        corroborating = await self.service.complete_interaction(
            user_message="Customer A still uses Alpha.",
            response_text="That corroborates the Customer A proposition.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The active Customer A route remains Alpha.",
                    grounding=("Customer A active configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Alpha",
                                "scope": customer_a.model_dump(mode="json"),
                            },
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(corroborating["memory_decisions"][0]["tensions"], [])
        corroborating_memory = corroborating["memory_decisions"][0]["memory"]
        self.assertTrue(
            any(
                artifact["kind"] == "semantic_equivalence"
                for artifact in corroborating_memory["artifacts"]
            )
        )

        different_scope = await self.service.complete_interaction(
            user_message="Customer B uses route Beta.",
            response_text="That is a distinct scoped proposition.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Customer B approval route is Beta.",
                    grounding=("Customer B configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Beta",
                                "scope": customer_b.model_dump(mode="json"),
                            },
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(different_scope["memory_decisions"][0]["tensions"], [])
        distinct_memory = different_scope["memory_decisions"][0]["memory"]
        self.assertTrue(
            any(
                artifact["kind"] == "semantic_scope_distinction"
                for artifact in distinct_memory["artifacts"]
            )
        )

        same_scope_conflict = await self.service.complete_interaction(
            user_message="Customer A uses route Gamma.",
            response_text="That conflicts with the existing Customer A proposition.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Customer A approval route is Gamma.",
                    grounding=("Customer A change report",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Gamma",
                                "scope": customer_a.model_dump(mode="json"),
                            },
                        ),
                    ),
                ),
            ),
        )
        tensions = same_scope_conflict["memory_decisions"][0]["tensions"]
        self.assertEqual(len(tensions), 1)
        self.assertEqual(tensions[0]["existing_value"], "Alpha")
        self.assertEqual(tensions[0]["proposed_value"], "Gamma")
        self.assertEqual(tensions[0]["scope"]["label"], "Customer A")

        wrong_scope_research = await self.service.complete_interaction(
            user_message="I found Customer B evidence.",
            response_text="That evidence belongs to Customer B and does not re-deliberate Customer A.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="Customer B route",
                    response="Customer B also reports Gamma.",
                    semantic_interpretation=SemanticInterpretation(
                        subject="invoice",
                        attribute="approval_route",
                        value="Gamma",
                        scope=customer_b,
                    ),
                ),
            ),
        )
        self.assertEqual(wrong_scope_research["tension_reassessments"], [])

        matching_scope_research = await self.service.complete_interaction(
            user_message="I found Customer A evidence.",
            response_text="That evidence belongs to the active Customer A tension.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="Customer A route",
                    response="Customer A independently reports Gamma.",
                    semantic_interpretation=SemanticInterpretation(
                        subject="invoice",
                        attribute="approval_route",
                        value="Gamma",
                        scope=customer_a,
                    ),
                ),
            ),
        )
        self.assertEqual(len(matching_scope_research["tension_reassessments"]), 1)
        self.assertEqual(
            matching_scope_research["tension_reassessments"][0]["scope"]["label"],
            "Customer A",
        )

    async def test_identical_text_is_allowed_when_semantic_scope_differs(self) -> None:
        await self.service.complete_interaction(
            user_message="Record Customer A routing.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The approval route is Alpha.",
                    grounding=("Customer A configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Alpha",
                                "scope": {
                                    "kind": "contextual",
                                    "label": "Customer A",
                                },
                            },
                        ),
                    ),
                ),
            ),
        )
        second = await self.service.complete_interaction(
            user_message="Record Customer C routing.",
            response_text="Recorded separately because the scope differs.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The approval route is Alpha.",
                    grounding=("Customer C configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Alpha",
                                "scope": {
                                    "kind": "contextual",
                                    "label": "Customer C",
                                },
                            },
                        ),
                    ),
                ),
            ),
        )
        self.assertTrue(second["memory_decisions"][0]["accepted"])
        self.assertEqual(second["memory_decisions"][0]["tensions"], [])
        self.assertEqual(len(await self.memory.read()), 2)

    async def test_contextual_belief_reframe_preserves_simultaneously_valid_values(self) -> None:
        await self.service.complete_interaction(
            user_message="Customer A uses approval route Alpha.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The invoice approval route is Alpha.",
                    grounding=("Customer A configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Alpha",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.9,
                                "weight": 0.8,
                                "provenance": [
                                    {
                                        "source": "Customer A configuration",
                                        "context": "Customer A",
                                        "condition": "active",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="Customer B uses approval route Beta.",
            response_text="That creates a semantic tension until context is resolved.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The invoice approval route is Beta.",
                    grounding=("Customer B configuration",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Beta",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.9,
                                "weight": 0.8,
                                "provenance": [
                                    {
                                        "source": "Customer B configuration",
                                        "context": "Customer B",
                                        "condition": "active",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        assessed = await self.service.complete_interaction(
            user_message="The routes are customer-specific.",
            response_text="Both routes are valid in different customer contexts.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="customer configurations",
                    response="Customer A is Alpha and Customer B is Beta.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.95,
                        weight=0.9,
                        provenance=(
                            ProvenanceHop(
                                source="configuration comparison",
                                context="customer implementations",
                                condition="verified",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="invoice",
                        attribute="approval_route",
                        value="Beta",
                    ),
                    tension_finding=TensionInvestigationFinding(
                        subject="invoice",
                        attribute="approval_route",
                        existing_value="Alpha",
                        proposed_value="Beta",
                        provenance_independence="verified_independent",
                        temporal_relationship="same_timeframe",
                        contextual_relationship="different_contexts",
                        basis=("The routes belong to distinct customer configurations.",),
                        existing_scope="Customer A",
                        proposed_scope="Customer B",
                    ),
                ),
            ),
        )
        self.assertEqual(
            assessed["tension_reassessments"][0]["deliberation"]["resolution_readiness"]["status"],
            "reframe_required",
        )

        committed = await self.service.complete_interaction(
            user_message="Reframe the approval route by customer.",
            response_text="Both routes are now represented in their customer scopes.",
            proposed_memories=(),
            belief_reframes=(
                BeliefReframeProposal(
                    subject="invoice",
                    attribute="approval_route",
                    existing_value="Alpha",
                    proposed_value="Beta",
                ),
            ),
        )
        decision = committed["belief_reframe_decisions"][0]
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["relationship"], "contextual")

        recalled = await self.service.begin_interaction("What is the invoice approval route?")
        self.assertIn("Alpha [Customer A] ; Beta [Customer B]", recalled["recalled_context"]["summary"])

        customer_a_support = await self.service.complete_interaction(
            user_message="Customer A continues to use Alpha.",
            response_text="That corroborates Alpha within Customer A only.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Customer A still uses approval route Alpha.",
                    grounding=("Customer A validation",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Alpha",
                                "scope": {
                                    "kind": "contextual",
                                    "label": "Customer A",
                                },
                            },
                        ),
                    ),
                ),
            ),
        )
        self.assertEqual(customer_a_support["memory_decisions"][0]["tensions"], [])
        self.assertTrue(
            any(
                artifact["kind"] == "semantic_equivalence"
                for artifact in customer_a_support["memory_decisions"][0]["memory"]["artifacts"]
            )
        )

        customer_a_change = await self.service.complete_interaction(
            user_message="Customer A changed to Gamma.",
            response_text="That creates a Customer A tension only.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Customer A now uses approval route Gamma.",
                    grounding=("Customer A change report",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "invoice",
                                "attribute": "approval_route",
                                "value": "Gamma",
                                "scope": {
                                    "kind": "contextual",
                                    "label": "Customer A",
                                },
                            },
                        ),
                    ),
                ),
            ),
        )
        tensions = customer_a_change["memory_decisions"][0]["tensions"]
        self.assertEqual(len(tensions), 1)
        self.assertEqual(tensions[0]["existing_value"], "Alpha")
        self.assertEqual(tensions[0]["proposed_value"], "Gamma")
        self.assertEqual(tensions[0]["scope"]["label"], "Customer A")

    async def test_scoped_candidate_transition_closes_only_that_scope(self) -> None:
        scope = SemanticScope(kind="contextual", label="Customer A")
        for value, confidence, weight, source in (
            ("October 1", 0.55, 0.4, "Customer A old plan"),
            ("October 8", 0.8, 0.7, "Customer A new plan"),
        ):
            result = await self.service.complete_interaction(
                user_message=f"Customer A deployment date is {value}.",
                response_text="Recorded.",
                proposed_memories=(
                    MemoryProposal(
                        memory_class=MemoryClass.SEMANTIC,
                        content=f"Customer A deployment date is {value}.",
                        grounding=(source,),
                        artifacts=(
                            MemoryArtifactProposal(
                                kind="semantic_interpretation",
                                payload={
                                    "subject": "deployment",
                                    "attribute": "date",
                                    "value": value,
                                    "scope": scope.model_dump(mode="json"),
                                },
                            ),
                            MemoryArtifactProposal(
                                kind="evidence_appraisal",
                                payload={
                                    "confidence": confidence,
                                    "weight": weight,
                                    "provenance": [
                                        {
                                            "source": source,
                                            "context": "Customer A",
                                            "condition": "published",
                                        }
                                    ],
                                },
                            ),
                        ),
                    ),
                ),
            )
        self.assertEqual(len(result["memory_decisions"][0]["tensions"]), 1)
        self.assertEqual(result["memory_decisions"][0]["tensions"][0]["scope"]["label"], "Customer A")

        assessed = await self.service.complete_interaction(
            user_message="Verify the Customer A deployment date.",
            response_text="October 8 is candidate-ready within Customer A.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="Customer A release board",
                    response="The independent Customer A release board lists October 8.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.9,
                        weight=0.75,
                        provenance=(
                            ProvenanceHop(
                                source="Customer A release board",
                                context="Customer A",
                                condition="published",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="deployment",
                        attribute="date",
                        value="October 8",
                        scope=scope,
                    ),
                    tension_finding=TensionInvestigationFinding(
                        subject="deployment",
                        attribute="date",
                        existing_value="October 1",
                        proposed_value="October 8",
                        scope=scope,
                        provenance_independence="verified_independent",
                        temporal_relationship="same_timeframe",
                        contextual_relationship="same_context",
                        basis=(
                            "The Customer A release board is maintained independently.",
                            "Both values apply to the same Customer A release decision.",
                        ),
                    ),
                ),
            ),
        )
        readiness = assessed["tension_reassessments"][0]["deliberation"]["resolution_readiness"]
        self.assertEqual(readiness["status"], "candidate_ready")
        self.assertEqual(readiness["candidate_value"], "October 8")

        transitioned = await self.service.complete_interaction(
            user_message="Adopt Customer A October 8.",
            response_text="October 8 is now the current Customer A deployment-date belief.",
            proposed_memories=(),
            belief_transitions=(
                BeliefTransitionProposal(
                    subject="deployment",
                    attribute="date",
                    candidate_value="October 8",
                    scope=scope,
                ),
            ),
        )
        decision = transitioned["belief_transition_decisions"][0]
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["scope"]["label"], "Customer A")

        recalled = await self.service.begin_interaction("What is Customer A's deployment date?")
        self.assertIn(
            "Current belief: deployment · date = October 8 [Customer A] (superseded October 1)",
            recalled["recalled_context"]["summary"],
        )

    async def _prepare_candidate_ready_deployment(self) -> None:
        await self.service.complete_interaction(
            user_message="The deployment date is October 1.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 1.",
                    grounding=("approved plan",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.55,
                                "weight": 0.4,
                                "provenance": [
                                    {
                                        "source": "approved plan",
                                        "context": "release decision",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The deployment date is October 8.",
            response_text="That creates an unresolved tension.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 8.",
                    grounding=("project lead update",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 8",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.8,
                                "weight": 0.7,
                                "provenance": [
                                    {
                                        "source": "project lead",
                                        "context": "release decision",
                                        "condition": "published",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )
        completed = await self.service.complete_interaction(
            user_message="I verified the deployment evidence.",
            response_text="October 8 is candidate-ready.",
            proposed_memories=(),
            current_evidence=(
                ResearchObservation(
                    query="release board",
                    response="The independently maintained release board lists October 8.",
                    appraisal=EvidenceAppraisal(
                        confidence=0.9,
                        weight=0.75,
                        provenance=(
                            ProvenanceHop(
                                source="release board",
                                context="release decision",
                                condition="published",
                            ),
                        ),
                    ),
                    semantic_interpretation=SemanticInterpretation(
                        subject="deployment",
                        attribute="date",
                        value="October 8",
                    ),
                    tension_finding=TensionInvestigationFinding(
                        subject="deployment",
                        attribute="date",
                        existing_value="October 1",
                        proposed_value="October 8",
                        provenance_independence="verified_independent",
                        temporal_relationship="same_timeframe",
                        contextual_relationship="same_context",
                        basis=(
                            "The release board is independently maintained.",
                            "Both values describe the same release decision and timeframe.",
                        ),
                    ),
                ),
            ),
        )
        readiness = completed["tension_reassessments"][0]["deliberation"]["resolution_readiness"]
        self.assertEqual(readiness["status"], "candidate_ready")
        self.assertEqual(readiness["candidate_value"], "October 8")

    async def test_candidate_ready_belief_transition_supersedes_without_erasing_evidence(self) -> None:
        await self._prepare_candidate_ready_deployment()

        completed = await self.service.complete_interaction(
            user_message="Adopt the candidate-ready deployment date.",
            response_text="The current belief is now October 8.",
            proposed_memories=(),
            belief_transitions=(
                BeliefTransitionProposal(
                    subject="deployment",
                    attribute="date",
                    candidate_value="October 8",
                ),
            ),
        )

        decision = completed["belief_transition_decisions"][0]
        self.assertTrue(decision["accepted"])
        self.assertEqual(decision["from_value"], "October 1")
        self.assertEqual(decision["to_value"], "October 8")

        memories = await self.memory.read()
        self.assertEqual(
            {memory.content for memory in memories},
            {
                "The deployment date is October 1.",
                "The deployment date is October 8.",
            },
        )
        old_memory = next(memory for memory in memories if memory.content.endswith("October 1."))
        new_memory = next(memory for memory in memories if memory.content.endswith("October 8."))

        old_status = [
            artifact.payload
            for artifact in old_memory.artifacts
            if artifact.kind == "belief_status"
        ]
        new_status = [
            artifact.payload
            for artifact in new_memory.artifacts
            if artifact.kind == "belief_status"
        ]
        transitions = [
            artifact.payload
            for artifact in new_memory.artifacts
            if artifact.kind == "belief_transition"
        ]

        self.assertEqual(old_status[-1]["status"], "superseded")
        self.assertEqual(old_status[-1]["current_value"], "October 8")
        self.assertEqual(new_status[-1]["status"], "current")
        self.assertEqual(len(transitions), 1)
        self.assertEqual(transitions[0]["from_value"], "October 1")
        self.assertEqual(transitions[0]["to_value"], "October 8")
        self.assertEqual(transitions[0]["status"], "committed")

        transition_entries = [
            entry
            for entry in await self.journal.read()
            if entry.kind.value == "belief_transition"
        ]
        self.assertEqual(len(transition_entries), 1)
        self.assertEqual(transition_entries[0].experience["to_value"], "October 8")
        self.assertIn(
            "The deployment date is October 1.",
            transition_entries[0].experience["superseded_evidence"],
        )
        self.assertIn(
            "The deployment date is October 8.",
            transition_entries[0].experience["candidate_evidence"],
        )

        later = await self.service.begin_interaction("What is the deployment date?")
        summary = later["recalled_context"]["summary"]
        self.assertIn(
            "Current belief: deployment · date = October 8 (superseded October 1)",
            summary,
        )
        self.assertNotIn("Candidate ready for later belief transition", summary)
        self.assertNotIn("Seek independent corroboration", summary)

    async def test_belief_transition_rejects_blocked_or_wrong_candidate_without_mutation(self) -> None:
        await self.service.complete_interaction(
            user_message="The deployment date is October 1.",
            response_text="Recorded.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 1.",
                    grounding=("approved plan",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        ),
                    ),
                ),
            ),
        )
        await self.service.complete_interaction(
            user_message="The deployment date is October 8.",
            response_text="The values are unresolved.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 8.",
                    grounding=("status statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 8",
                            },
                        ),
                    ),
                ),
            ),
        )

        rejected = await self.service.complete_interaction(
            user_message="Switch the belief now.",
            response_text="The transition is not authorized.",
            proposed_memories=(),
            belief_transitions=(
                BeliefTransitionProposal(
                    subject="deployment",
                    attribute="date",
                    candidate_value="October 8",
                ),
            ),
        )
        self.assertFalse(rejected["belief_transition_decisions"][0]["accepted"])

        memories = await self.memory.read()
        self.assertFalse(
            any(
                artifact.kind in {"belief_status", "belief_transition"}
                for memory in memories
                for artifact in memory.artifacts
            )
        )
        self.assertFalse(
            any(entry.kind.value == "belief_transition" for entry in await self.journal.read())
        )

    async def test_belief_transition_rejects_wrong_candidate_value(self) -> None:
        await self._prepare_candidate_ready_deployment()
        wrong = await self.service.complete_interaction(
            user_message="Adopt October 15.",
            response_text="That candidate is not authorized.",
            proposed_memories=(),
            belief_transitions=(
                BeliefTransitionProposal(
                    subject="deployment",
                    attribute="date",
                    candidate_value="October 15",
                ),
            ),
        )
        self.assertFalse(wrong["belief_transition_decisions"][0]["accepted"])
        self.assertFalse(
            any(
                artifact.kind in {"belief_status", "belief_transition"}
                for memory in await self.memory.read()
                for artifact in memory.artifacts
            )
        )

    async def test_duplicate_transition_is_rejected_and_new_tension_uses_current_belief(self) -> None:
        await self._prepare_candidate_ready_deployment()
        await self.service.complete_interaction(
            user_message="Adopt October 8.",
            response_text="October 8 is now current.",
            proposed_memories=(),
            belief_transitions=(
                BeliefTransitionProposal(
                    subject="deployment",
                    attribute="date",
                    candidate_value="October 8",
                ),
            ),
        )

        duplicate = await self.service.complete_interaction(
            user_message="Adopt October 8 again.",
            response_text="It is already current.",
            proposed_memories=(),
            belief_transitions=(
                BeliefTransitionProposal(
                    subject="deployment",
                    attribute="date",
                    candidate_value="October 8",
                ),
            ),
        )
        self.assertFalse(duplicate["belief_transition_decisions"][0]["accepted"])
        self.assertIn("already the current belief", duplicate["belief_transition_decisions"][0]["reason"])

        new_evidence = await self.service.complete_interaction(
            user_message="The deployment date is October 15.",
            response_text="That creates a new tension against the current belief.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="The deployment date is October 15.",
                    grounding=("new statement",),
                    artifacts=(
                        MemoryArtifactProposal(
                            kind="semantic_interpretation",
                            payload={
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 15",
                            },
                        ),
                        MemoryArtifactProposal(
                            kind="evidence_appraisal",
                            payload={
                                "confidence": 0.6,
                                "weight": 0.5,
                                "provenance": [
                                    {
                                        "source": "new statement",
                                        "context": "release decision",
                                        "condition": "unverified",
                                    }
                                ],
                            },
                        ),
                    ),
                ),
            ),
        )

        tensions = new_evidence["memory_decisions"][0]["tensions"]
        self.assertEqual(len(tensions), 1)
        self.assertEqual(tensions[0]["existing_value"], "October 8")
        self.assertEqual(tensions[0]["proposed_value"], "October 15")

    async def test_recalled_history_is_compact_and_does_not_embed_prior_journal_documents(self) -> None:
        for turn in range(8):
            await self.service.complete_interaction(
                user_message=f"Continuity checkpoint turn {turn}",
                response_text=f"Recorded continuity checkpoint turn {turn}.",
                proposed_memories=(),
            )

        later = await self.service.begin_interaction("continuity checkpoint")
        prior = later["recalled_context"]["prior_experience"]

        self.assertTrue(prior)
        self.assertTrue(all("excerpt" in item for item in prior))
        self.assertTrue(all("experience" not in item for item in prior))

        entries = await self.journal.read()
        latest_payload = json.dumps(entries[-1].model_dump(mode="json"))
        self.assertLess(len(latest_payload), 50_000)

    async def test_identity_memory_is_not_writable_through_v01_steward(self) -> None:
        completed = await self.service.complete_interaction(
            user_message="Change who you are.",
            response_text="That requires identity governance.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.IDENTITY,
                    content="I am now a different individual.",
                    grounding=("User requested an identity change.",),
                ),
            ),
        )

        self.assertFalse(completed["memory_decisions"][0]["accepted"])
        status = await self.service.status()
        self.assertEqual(status["durable_memory_count"], 0)


if __name__ == "__main__":
    unittest.main()
