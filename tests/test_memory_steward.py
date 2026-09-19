import unittest
from typing import Any, cast

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    MemoryClass,
    MindIdentity,
    ReasoningProposal,
    ReasoningRequest,
)
from aicognitive_mind.memory_steward import (
    MemoryStewardNotConsultedError,
    MemoryStewardTool,
)
from aicognitive_mind.prompts import CONSCIOUS_WORKSPACE_SYSTEM_PROMPT
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)
from aicognitive_mind.tooling import ReasoningTool


class MemoryUsingEngine:
    def __init__(self) -> None:
        self.request: ReasoningRequest | None = None
        self.recalled: dict[str, object] | None = None

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        self.request = request
        steward = tools[0]
        self.recalled = await steward.invoke(
            {"action": "recall", "focus": request.input_text}
        )
        await steward.invoke(
            {
                "action": "consider_evidence",
                "query": "constitutional AI memory architecture",
                "response": "Current systems commonly inject external memory into model context.",
                "articles": [
                    {
                        "title": "Memory architecture",
                        "url": "https://example.test/memory",
                        "relevant_content": "External state is recalled into working context.",
                    }
                ],
            }
        )
        await steward.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": (
                    "mir.ai Technology's Digital Genesis Constitution governs the "
                    "Cognitive Mind."
                ),
                "associations": [
                    "constitution",
                    "mir.ai Technology",
                    "Digital Genesis",
                    "Cognitive Mind",
                ],
                "grounding": ["current-user-statement", "https://example.test/memory"],
            }
        )
        return ReasoningProposal(
            response_text="The constitutional relationship is remembered.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "memory-using-test-engine"},
            ),
        )


class NonConsultingEngine:
    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        return ReasoningProposal(
            response_text="I skipped memory.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "non-consulting-test-engine"},
            ),
        )


class RecallOnlyEngine:
    def __init__(self) -> None:
        self.recalled: dict[str, object] | None = None

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        self.recalled = await tools[0].invoke(
            {"action": "recall", "focus": request.input_text}
        )
        return ReasoningProposal(
            response_text="Recalled.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "recall-only-test-engine"},
            ),
        )


class MemoryStewardTests(unittest.IsolatedAsyncioTestCase):
    async def test_prompt_driven_tool_flow_records_experience_and_durable_learning(self) -> None:
        engine = MemoryUsingEngine()
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=journal,
            memory=memory,
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
        )
        await core.initialize("Genesis", ("understanding-before-recommending",))

        await core.interact("How does the constitution govern learning?")

        self.assertIsNotNone(engine.request)
        request = cast(ReasoningRequest, engine.request)
        self.assertEqual(request.system_prompt, CONSCIOUS_WORKSPACE_SYSTEM_PROMPT)
        self.assertIn("memory_steward", request.system_prompt)
        memories = await core.read_memory()
        self.assertEqual(len(memories), 1)
        self.assertEqual(memories[0].memory_class, MemoryClass.SEMANTIC)
        self.assertIn("mir.ai Technology", memories[0].associations)

        experience = (await core.read_journal())[-1].experience
        steward_trace = experience["memory_steward"]
        self.assertEqual(len(steward_trace["evidence_considered"]), 1)
        self.assertTrue(steward_trace["memory_decisions"][0]["accepted"])

    async def test_associations_expand_recall_beyond_the_literal_prompt(self) -> None:
        memory = InMemoryMemoryStore()
        await memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="The constitutional framework establishes bounded sovereignty.",
                associations=("constitution", "mir.ai Technology"),
                grounding=("Digital Genesis Constitutional Blueprint",),
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        await memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="Digital Genesis defines the future digital species.",
                associations=("mir.ai Technology", "Digital Genesis"),
                grounding=("Digital Genesis Constitutional Blueprint",),
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        engine = RecallOnlyEngine()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=InMemoryJournalStore(),
            memory=memory,
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
        )
        await core.initialize("Genesis")

        await core.interact("Does the constitution already answer this?")

        self.assertIsNotNone(engine.recalled)
        payload = cast(dict[str, Any], engine.recalled)
        context = cast(dict[str, Any], payload["context"])
        recalled = cast(list[dict[str, Any]], context["durable_memory"])
        self.assertEqual(len(recalled), 2)
        self.assertTrue(any("Digital Genesis" in item["content"] for item in recalled))

    async def test_response_is_rejected_when_engine_skips_memory(self) -> None:
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=NonConsultingEngine(),
        )
        await core.initialize("Genesis")

        with self.assertRaises(MemoryStewardNotConsultedError):
            await core.interact("Respond without remembering.")

        self.assertEqual(len(await core.read_journal()), 1)

    async def test_memory_steward_refuses_direct_identity_change(self) -> None:
        memory = InMemoryMemoryStore()
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="Change who you are.",
            memory=memory,
            journal=InMemoryJournalStore(),
        )
        await tool.invoke({"action": "recall", "focus": "Change who you are."})

        decision = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "identity",
                "content": "A reasoning engine changed the Mind's identity.",
                "associations": ["identity"],
                "grounding": ["reasoning-engine-proposal"],
            }
        )
        await tool.complete()

        self.assertFalse(decision["accepted"])
        self.assertEqual(await memory.read(), [])




    async def test_semantic_equivalence_preserves_distinct_corroborating_evidence(self) -> None:
        memory = InMemoryMemoryStore()
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="My birthday is February 7.",
            memory=memory,
            journal=InMemoryJournalStore(),
        )
        await tool.invoke({"action": "recall", "focus": "birthday"})
        first = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "The user's birthday is February 7.",
                "associations": ["birthday", "February 7"],
                "grounding": ["direct-user-statement"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "current_human",
                            "attribute": "birthday",
                            "value": "February 7",
                        },
                    }
                ],
            }
        )
        await tool.complete()
        self.assertTrue(first["accepted"])

        second_tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="Will's birthday is February 7.",
            memory=memory,
            journal=InMemoryJournalStore(),
        )
        await second_tool.invoke({"action": "recall", "focus": "birthday"})
        second = await second_tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "Will's birthday is February 7.",
                "associations": ["Will", "birthday", "February 7"],
                "grounding": ["direct-user-statement"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "CURRENT_HUMAN",
                            "attribute": "Birthday",
                            "value": "  February 7  ",
                        },
                    }
                ],
            }
        )
        await second_tool.complete()

        self.assertTrue(second["accepted"])
        self.assertIn("corroborating evidence", second["reason"])
        memories = await memory.read()
        self.assertEqual(len(memories), 2)
        self.assertEqual(memories[0].content, "The user's birthday is February 7.")
        self.assertEqual(memories[1].content, "Will's birthday is February 7.")
        equivalence = [
            artifact
            for artifact in memories[1].artifacts
            if artifact.kind == "semantic_equivalence"
        ]
        self.assertEqual(len(equivalence), 1)
        self.assertEqual(
            equivalence[0].payload["equivalent_evidence_content"],
            "The user's birthday is February 7.",
        )



    async def test_current_evidence_keeps_confidence_weight_and_provenance_separate(self) -> None:
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="Evaluate the current evidence.",
            memory=InMemoryMemoryStore(),
            journal=InMemoryJournalStore(),
        )
        await tool.invoke({"action": "recall", "focus": "current evidence"})

        considered = await tool.invoke(
            {
                "action": "consider_evidence",
                "query": "source chain example",
                "response": "A current evidence summary.",
                "articles": [],
                "appraisal": {
                    "confidence": 0.8,
                    "weight": 0.35,
                    "provenance": [
                        {
                            "source": "analyst summary",
                            "context": "active research session",
                            "condition": "secondary account",
                        },
                        {
                            "source": "original witness",
                            "context": "event observation",
                            "condition": "direct observation",
                        },
                    ],
                    "basis": ["source chain is known", "account is internally consistent"],
                },
            }
        )

        appraisal = considered["context"]["current_evidence"][0]["appraisal"]
        self.assertEqual(appraisal["confidence"], 0.8)
        self.assertEqual(appraisal["weight"], 0.35)
        self.assertEqual(len(appraisal["provenance"]), 2)
        self.assertEqual(appraisal["provenance"][0]["source"], "analyst summary")
        self.assertEqual(appraisal["provenance"][1]["source"], "original witness")
        self.assertNotIn("combined_score", appraisal)

    async def test_tension_deliberation_detects_shared_provenance_without_selecting_winner(self) -> None:
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The deployment date is October 1.",
                    "grounding": ["published-status"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        },
                        {
                            "kind": "evidence_appraisal",
                            "payload": {
                                "confidence": 0.8,
                                "weight": 0.7,
                                "provenance": [
                                    {
                                        "source": "status report",
                                        "context": "weekly publication",
                                        "condition": "written summary",
                                    },
                                    {
                                        "source": "project lead",
                                        "context": "release planning",
                                        "condition": "first-party statement",
                                    },
                                ],
                            },
                        },
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The approved release calendar lists October 1.",
                    "grounding": ["release-calendar"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        },
                        {
                            "kind": "evidence_appraisal",
                            "payload": {
                                "confidence": 0.75,
                                "weight": 0.65,
                                "provenance": [
                                    {
                                        "source": "release calendar",
                                        "context": "approved planning artifact",
                                        "condition": "published",
                                    }
                                ],
                            },
                        },
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="The deployment date is October 8.",
            memory=memory,
            journal=journal,
        )
        await tool.invoke({"action": "recall", "focus": "deployment date"})
        decision = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "The deployment date is October 8.",
                "grounding": ["meeting-notes"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "deployment",
                            "attribute": "date",
                            "value": "October 8",
                        },
                    },
                    {
                        "kind": "evidence_appraisal",
                        "payload": {
                            "confidence": 0.9,
                            "weight": 0.6,
                            "provenance": [
                                {
                                    "source": "meeting notes",
                                    "context": "status meeting",
                                    "condition": "written notes",
                                },
                                {
                                    "source": "project lead",
                                    "context": "status meeting",
                                    "condition": "first-party statement",
                                },
                            ],
                        },
                    },
                ],
            }
        )

        tension = decision["tensions"][0]
        deliberation = tension["deliberation"]
        self.assertEqual(tension["status"], "unresolved")
        self.assertEqual(deliberation["existing_support_count"], 2)
        self.assertEqual(deliberation["proposed_support_count"], 1)
        self.assertEqual(deliberation["provenance_relationship"], "overlap_detected")
        self.assertEqual(deliberation["existing_provenance_depth"], 2)
        self.assertEqual(deliberation["proposed_provenance_depth"], 2)
        self.assertTrue(deliberation["context_observations"])
        self.assertTrue(
            any("shared provenance" in question for question in deliberation["investigation_questions"])
        )
        self.assertNotIn("winner", deliberation)
        self.assertTrue(
            any(
                artifact["kind"] == "evidence_deliberation"
                for artifact in decision["memory"]["artifacts"]
            )
        )

    async def test_recall_carries_missing_appraisal_investigation_forward(self) -> None:
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The deployment date is October 1.",
                    "grounding": ["historical note"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        }
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="The deployment date is October 8.",
            memory=memory,
            journal=journal,
        )
        await tool.invoke({"action": "recall", "focus": "deployment date"})
        decision = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "The deployment date is October 8.",
                "grounding": ["current statement"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "deployment",
                            "attribute": "date",
                            "value": "October 8",
                        },
                    }
                ],
            }
        )
        await tool.complete()

        deliberation = decision["tensions"][0]["deliberation"]
        self.assertEqual(deliberation["provenance_relationship"], "unknown")
        self.assertEqual(len(deliberation["appraisal_gaps"]), 2)
        self.assertTrue(
            any("Appraise missing evidence" in question for question in deliberation["investigation_questions"])
        )

        recalled_tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="What do we know about the deployment date?",
            memory=memory,
            journal=journal,
        )
        recalled = await recalled_tool.invoke(
            {"action": "recall", "focus": "deployment date"}
        )
        summary = recalled["context"]["summary"]
        self.assertIn("Investigation guidance:", summary)
        self.assertIn("Appraise missing evidence", summary)

    async def test_multiple_current_evidence_items_create_ordered_reassessment_history(self) -> None:
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The deployment date is October 1.",
                    "grounding": ["approved plan"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        },
                        {
                            "kind": "evidence_appraisal",
                            "payload": {
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
                        },
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The deployment date is October 8.",
                    "grounding": ["status statement"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 8",
                            },
                        },
                        {
                            "kind": "evidence_appraisal",
                            "payload": {
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
                        },
                        {
                            "kind": "semantic_tension",
                            "payload": {
                                "status": "unresolved",
                                "subject": "deployment",
                                "attribute": "date",
                                "existing_value": "October 1",
                                "proposed_value": "October 8",
                                "existing_evidence_content": "The deployment date is October 1.",
                            },
                        },
                        {
                            "kind": "evidence_deliberation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "existing_value": "October 1",
                                "proposed_value": "October 8",
                                "revision": 1,
                                "trigger": "tension_detected",
                                "existing_support_count": 1,
                                "proposed_support_count": 1,
                                "provenance_relationship": "no_overlap_observed",
                                "existing_provenance_depth": 1,
                                "proposed_provenance_depth": 1,
                                "appraisal_gaps": [],
                                "context_observations": [],
                                "investigation_questions": [
                                    "Seek independent corroboration for the existing value.",
                                    "Seek independent corroboration for the proposed value.",
                                ],
                            },
                        },
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="Investigate the deployment date.",
            memory=memory,
            journal=journal,
        )
        await tool.invoke({"action": "recall", "focus": "deployment date"})

        first = await tool.invoke(
            {
                "action": "consider_evidence",
                "query": "current calendar",
                "response": "The release board lists October 8.",
                "appraisal": {
                    "confidence": 0.9,
                    "weight": 0.55,
                    "provenance": [
                        {
                            "source": "release board",
                            "context": "current calendar",
                            "condition": "published",
                        }
                    ],
                },
                "semantic_interpretation": {
                    "subject": "deployment",
                    "attribute": "date",
                    "value": "October 8",
                },
            }
        )
        second = await tool.invoke(
            {
                "action": "consider_evidence",
                "query": "change record",
                "response": "The change log independently records October 8.",
                "appraisal": {
                    "confidence": 0.88,
                    "weight": 0.5,
                    "provenance": [
                        {
                            "source": "change log",
                            "context": "release governance",
                            "condition": "approved",
                        }
                    ],
                },
                "semantic_interpretation": {
                    "subject": "deployment",
                    "attribute": "date",
                    "value": "October 8",
                },
            }
        )
        trace = await tool.complete()

        self.assertEqual(
            first["tension_reassessments"][0]["deliberation"]["revision"],
            2,
        )
        self.assertEqual(
            second["tension_reassessments"][0]["deliberation"]["revision"],
            3,
        )
        self.assertEqual(len(trace.tension_reassessments), 2)

        stored = await memory.read()
        tension_memory = next(
            item for item in stored if item.content.endswith("October 8.")
        )
        deliberations = [
            artifact.payload
            for artifact in tension_memory.artifacts
            if artifact.kind == "evidence_deliberation"
        ]
        self.assertEqual(
            [payload["revision"] for payload in deliberations],
            [1, 2, 3],
        )
        self.assertEqual(deliberations[-1]["proposed_support_count"], 3)
        self.assertEqual(deliberations[-1]["current_proposed_support_count"], 2)

        reassessment_entries = [
            entry
            for entry in await journal.read()
            if entry.kind.value == "tension"
            and entry.experience.get("phase") == "reassessment"
        ]
        self.assertEqual(len(reassessment_entries), 2)
        self.assertEqual(
            len(reassessment_entries[0].experience["current_evidence"]),
            1,
        )
        self.assertEqual(
            len(reassessment_entries[1].experience["current_evidence"]),
            2,
        )

        recalled_tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="What remains unresolved about deployment?",
            memory=memory,
            journal=journal,
        )
        recalled = await recalled_tool.invoke(
            {"action": "recall", "focus": "deployment date"}
        )
        summary = recalled["context"]["summary"]
        self.assertNotIn(
            "Seek independent corroboration for the proposed value.",
            summary,
        )
        self.assertIn(
            "Seek independent corroboration for the existing value.",
            summary,
        )

    async def test_semantic_tension_carries_both_evidence_appraisals_without_resolution(self) -> None:
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The deployment date is October 1.",
                    "grounding": ["project-plan"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "deployment",
                                "attribute": "date",
                                "value": "October 1",
                            },
                        },
                        {
                            "kind": "evidence_appraisal",
                            "payload": {
                                "confidence": 0.7,
                                "weight": 0.9,
                                "provenance": [
                                    {
                                        "source": "project plan",
                                        "context": "approved baseline",
                                        "condition": "published",
                                    }
                                ],
                                "basis": ["approved plan"],
                            },
                        },
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="The deployment date is October 8.",
            memory=memory,
            journal=journal,
        )
        await tool.invoke({"action": "recall", "focus": "deployment date"})
        decision = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "The deployment date is October 8.",
                "grounding": ["meeting statement"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "deployment",
                            "attribute": "date",
                            "value": "October 8",
                        },
                    },
                    {
                        "kind": "evidence_appraisal",
                        "payload": {
                            "confidence": 0.85,
                            "weight": 0.6,
                            "provenance": [
                                {
                                    "source": "project lead",
                                    "context": "status meeting",
                                    "condition": "verbal update",
                                }
                            ],
                            "basis": ["first-party project role"],
                        },
                    },
                ],
            }
        )
        await tool.complete()

        tension = decision["tensions"][0]
        self.assertEqual(tension["status"], "unresolved")
        self.assertEqual(tension["existing_appraisal"]["confidence"], 0.7)
        self.assertEqual(tension["existing_appraisal"]["weight"], 0.9)
        self.assertEqual(tension["proposed_appraisal"]["confidence"], 0.85)
        self.assertEqual(tension["proposed_appraisal"]["weight"], 0.6)

        tension_entry = next(
            entry for entry in await journal.read() if entry.kind.value == "tension"
        )
        appraisals = tension_entry.experience["appraisals"]
        self.assertEqual(appraisals["existing"]["confidence"], 0.7)
        self.assertEqual(appraisals["proposed"]["confidence"], 0.85)
        self.assertEqual(tension_entry.experience["status"], "unresolved")

    async def test_competing_semantic_values_create_unresolved_tension(self) -> None:
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The user's birthday is February 7.",
                    "grounding": ["direct-user-statement"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "current_human",
                                "attribute": "birthday",
                                "value": "February 7",
                            },
                        }
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="Actually, my birthday is February 8.",
            memory=memory,
            journal=journal,
        )
        await tool.invoke({"action": "recall", "focus": "birthday"})
        decision = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "The user's birthday is February 8.",
                "associations": ["birthday", "February 8"],
                "grounding": ["direct-user-statement"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "current_human",
                            "attribute": "birthday",
                            "value": "February 8",
                        },
                    }
                ],
            }
        )
        await tool.complete()

        self.assertTrue(decision["accepted"])
        self.assertIn("unresolved semantic tension", decision["reason"])
        self.assertEqual(len(decision["tensions"]), 1)
        self.assertEqual(decision["tensions"][0]["existing_value"], "February 7")
        self.assertEqual(decision["tensions"][0]["proposed_value"], "February 8")

        memories = await memory.read()
        self.assertEqual(len(memories), 2)
        tension_artifacts = [
            artifact
            for artifact in memories[1].artifacts
            if artifact.kind == "semantic_tension"
        ]
        self.assertEqual(len(tension_artifacts), 1)
        self.assertEqual(tension_artifacts[0].payload["status"], "unresolved")
        self.assertEqual(
            tension_artifacts[0].payload["existing_evidence_content"],
            "The user's birthday is February 7.",
        )

        journal_entries = await journal.read()
        tension_entries = [
            entry for entry in journal_entries if entry.kind.value == "tension"
        ]
        self.assertEqual(len(tension_entries), 1)
        tension = tension_entries[0].experience
        self.assertEqual(tension["status"], "unresolved")
        self.assertEqual(tension["competing_values"]["existing"], "February 7")
        self.assertEqual(tension["competing_values"]["proposed"], "February 8")

    async def test_same_subject_and_attribute_with_different_value_is_not_equivalence(self) -> None:
        memory = InMemoryMemoryStore()
        await memory.remember(
            DurableMemory.model_validate(
                {
                    "memory_class": "semantic",
                    "content": "The user's birthday is February 7.",
                    "grounding": ["direct-user-statement"],
                    "artifacts": [
                        {
                            "kind": "semantic_interpretation",
                            "payload": {
                                "subject": "current_human",
                                "attribute": "birthday",
                                "value": "February 7",
                            },
                        }
                    ],
                }
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="My birthday is February 8.",
            memory=memory,
            journal=InMemoryJournalStore(),
        )
        await tool.invoke({"action": "recall", "focus": "birthday"})
        decision = await tool.invoke(
            {
                "action": "propose_memory",
                "memory_class": "semantic",
                "content": "The user's birthday is February 8.",
                "grounding": ["direct-user-statement"],
                "artifacts": [
                    {
                        "kind": "semantic_interpretation",
                        "payload": {
                            "subject": "current_human",
                            "attribute": "birthday",
                            "value": "February 8",
                        },
                    }
                ],
            }
        )
        await tool.complete()

        self.assertTrue(decision["accepted"])
        self.assertFalse(
            any(
                artifact["kind"] == "semantic_equivalence"
                for artifact in decision["memory"]["artifacts"]
            )
        )
        self.assertTrue(
            any(
                artifact["kind"] == "semantic_tension"
                for artifact in decision["memory"]["artifacts"]
            )
        )

    def test_legacy_memory_without_artifacts_remains_valid(self) -> None:
        memory = DurableMemory.model_validate(
            {
                "memory_class": "semantic",
                "content": "Legacy memory",
                "associations": ["legacy"],
                "grounding": ["historical-record"],
            }
        )

        self.assertEqual(memory.artifacts, ())

    async def test_exact_memory_replacement_preserves_document_model(self) -> None:
        memory = InMemoryMemoryStore()
        original = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The user's birthday is February 7.",
            associations=("birthday",),
            grounding=("direct-user-statement",),
        )
        await memory.remember(
            original,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        replacement = original.model_copy(
            update={
                "content": "The user's birthday is February 8.",
                "associations": ("birthday", "corrected"),
            }
        )

        revised = await memory.replace_exact(
            original,
            replacement,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        self.assertEqual(revised, replacement)
        stored = await memory.read()
        self.assertEqual(stored, [replacement])
        self.assertEqual(stored[0].formed_at, original.formed_at)


if __name__ == "__main__":
    unittest.main()
