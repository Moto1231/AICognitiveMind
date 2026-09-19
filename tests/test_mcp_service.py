import json
import unittest

from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.memory_steward import (
    EvidenceAppraisal,
    MemoryArtifactProposal,
    ProvenanceHop,
    ResearchObservation,
    SemanticInterpretation,
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
        self.assertEqual(deliberation["trigger"], "current_evidence_reassessment")
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
