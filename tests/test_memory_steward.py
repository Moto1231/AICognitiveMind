import unittest
from typing import Any, cast

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    MemoryClass,
    MindIdentity,
    ReasoningProposal,
    ReasoningRequest,
)
from aicognitive_mind.evidence import (
    EvidenceAssessment,
    EvidenceProvenanceHop,
    EvidenceScorecard,
    adjudicate_contradiction,
)
from aicognitive_mind.foundation import (
    CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
    CONSCIOUS_EXPRESSION_FOUNDATION_SEED,
    CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
    CONSCIOUS_WORKSPACE_FOUNDATION_SEED,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_SEED,
)
from aicognitive_mind.knowledge import KnowledgeSynthesizer
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.propositions import PropositionEvidence
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryFoundationStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
    InMemoryWorkingMemoryStore,
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
    def __init__(self) -> None:
        self.request: ReasoningRequest | None = None

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        self.request = request
        return ReasoningProposal(
            response_text="I did not call recall myself.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "non-consulting-test-engine"},
            ),
        )


class KnownSpeakerBirthdayEngine:
    def __init__(self) -> None:
        self.request: ReasoningRequest | None = None

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        del tools
        self.request = request
        can_answer = (
            "current_speaker: William" in request.system_prompt
            and "The human's birthday is February 7." in request.system_prompt
        )
        return ReasoningProposal(
            response_text=(
                "Your birthday is February 7."
                if can_answer
                else "I do not have enough identity-bound knowledge."
            ),
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "known-speaker-birthday-test-engine"},
            ),
        )


class SpeakerIsolationEngine:
    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        del tools
        if "birthday?" in request.input_text.casefold():
            if (
                "current_speaker: Michael" in request.system_prompt
                and "January 3" in request.system_prompt
            ):
                response_text = "Your birthday is January 3."
            elif "February 7" in request.system_prompt:
                response_text = "Your birthday is February 7."
            else:
                response_text = "I don't know your birthday."
        else:
            response_text = "Noted."

        return ReasoningProposal(
            response_text=response_text,
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "speaker-isolation-test-engine"},
            ),
        )


class SpeakerAwareBirthdaySynthesizer:
    async def synthesize(
        self,
        mind: CognitiveMind,
        focus: str,
        evidence: tuple[str, ...],
        instructions: str,
    ) -> str:
        del mind, focus, instructions
        if any("michael's birthday is january 3" in item.casefold() for item in evidence):
            return "Michael's birthday is January 3."
        if any(
            "resolved subject: michael" in item.casefold()
            and "his birthday is january 3" in item.casefold()
            for item in evidence
        ):
            return "Michael's birthday is January 3."
        if any("his birthday is january 3" in item.casefold() for item in evidence):
            return "An unresolved male person's birthday is January 3."
        if any("my birthday is february 7" in item.casefold() for item in evidence):
            return "The current speaker's birthday is February 7."
        return "No relevant birthday knowledge is available."


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


class RecordingScorecardEvaluator:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def derive(
        self,
        *,
        proposition: str,
        prior: EvidenceScorecard,
        provenance: tuple[EvidenceProvenanceHop, ...],
        current_speaker: str | None,
        current_context: dict[str, Any],
    ) -> EvidenceScorecard:
        self.calls.append(
            {
                "proposition": proposition,
                "prior": prior,
                "provenance": provenance,
                "current_speaker": current_speaker,
                "current_context": current_context,
            }
        )
        return EvidenceScorecard(
            confidence=min(1.0, prior.confidence + 0.1),
            weight=min(1.0, prior.weight + 0.2),
        )


class CurrentSpeakerSourceEvaluator:
    """Test evaluator proving the live path without defining production trust math."""

    def derive(
        self,
        *,
        proposition: str,
        prior: EvidenceScorecard,
        provenance: tuple[EvidenceProvenanceHop, ...],
        current_speaker: str | None,
        current_context: dict[str, Any],
    ) -> EvidenceScorecard:
        del proposition, current_context
        source = provenance[0].source if provenance else ""
        if current_speaker and source.casefold() == current_speaker.casefold():
            return EvidenceScorecard(confidence=0.9, weight=0.8)
        return prior.model_copy()


class AdjudicatedBirthdayEngine:
    def __init__(self) -> None:
        self.request: ReasoningRequest | None = None

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        del tools
        self.request = request
        if (
            "Adjudicated current knowledge:" in request.system_prompt
            and "January 4" in request.system_prompt
        ):
            response_text = "Your birthday is January 4."
        else:
            response_text = "I don't know your birthday."
        return ReasoningProposal(
            response_text=response_text,
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "adjudicated-birthday-test-engine"},
            ),
        )


class FavoriteColorDetector:
    def detect(
        self,
        text: str,
        *,
        speaker: str | None,
        resolved_subject: str | None,
        assessment: EvidenceAssessment,
    ) -> tuple[PropositionEvidence, ...]:
        del resolved_subject
        normalized = text.casefold()
        subject = speaker
        if "michael's favorite color is " in normalized:
            subject = "Michael"
            value = text.rsplit(" ", 1)[-1].rstrip(".")
        elif "my favorite color is " in normalized and speaker:
            value = text.rsplit(" ", 1)[-1].rstrip(".")
        else:
            return ()
        return (
            PropositionEvidence(
                subject=subject or "unknown",
                attribute="favorite color",
                value=value,
                assessment=assessment,
            ),
        )


class FavoriteColorEngine:
    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        del tools
        return ReasoningProposal(
            response_text="No clarification was required.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "favorite-color-test-engine"},
            ),
        )


class RabbitHoleSupportEvaluator:
    """Test evaluator proving newly recalled support can change effective scoring."""

    def derive(
        self,
        *,
        proposition: str,
        prior: EvidenceScorecard,
        provenance: tuple[EvidenceProvenanceHop, ...],
        current_speaker: str | None,
        current_context: dict[str, Any],
    ) -> EvidenceScorecard:
        del provenance, current_speaker
        recalled = current_context.get("recalled_evidence", ())
        has_support = any(
            "William heard the January 3 birthday claim directly from Michael."
            in str(item)
            for item in recalled
        )
        if has_support and "January 3" in proposition:
            return EvidenceScorecard(confidence=0.8, weight=0.8)
        return prior.model_copy()


class RecordingSynthesizer:
    def __init__(self, summary: str) -> None:
        self.summary = summary
        self.focus: str | None = None
        self.evidence: tuple[str, ...] = ()
        self.instructions: str | None = None

    async def synthesize(
        self,
        mind: CognitiveMind,
        focus: str,
        evidence: tuple[str, ...],
        instructions: str,
    ) -> str:
        del mind
        self.focus = focus
        self.evidence = evidence
        self.instructions = instructions
        return self.summary


class MemoryStewardTests(unittest.IsolatedAsyncioTestCase):
    async def _foundation(self) -> InMemoryFoundationStore:
        foundation = InMemoryFoundationStore()
        await foundation.seed(
            CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
            CONSCIOUS_WORKSPACE_FOUNDATION_SEED,
        )
        await foundation.seed(
            MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
            MEMORY_STEWARD_SYNTHESIS_FOUNDATION_SEED,
        )
        await foundation.seed(
            CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
            CONSCIOUS_EXPRESSION_FOUNDATION_SEED,
        )
        return foundation

    async def test_prompt_driven_tool_flow_records_experience_and_durable_learning(self) -> None:
        engine = MemoryUsingEngine()
        memory = InMemoryMemoryStore()
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=memory,
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
        )
        await core.initialize("Genesis", ("understanding-before-recommending",))

        await core.interact("How does the constitution govern learning?")

        self.assertIsNotNone(engine.request)
        request = cast(ReasoningRequest, engine.request)
        self.assertTrue(request.system_prompt.startswith(CONSCIOUS_WORKSPACE_FOUNDATION_SEED))
        self.assertIn("Relevant knowledge:", request.system_prompt)
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
            foundation=await self._foundation(),
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

    async def test_core_performs_recall_before_non_consulting_engine_runs(self) -> None:
        engine = NonConsultingEngine()
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
        )
        await core.initialize("Genesis")

        result = await core.interact("Respond without remembering.")

        self.assertEqual(result.response_text, "I did not call recall myself.")
        self.assertIsNotNone(engine.request)
        request = cast(ReasoningRequest, engine.request)
        self.assertIn("Relevant knowledge:", request.system_prompt)
        self.assertIn("No relevant knowledge is available.", request.system_prompt)
        self.assertEqual(len(await core.read_journal()), 2)

    async def test_known_speaker_uses_synthesized_knowledge_without_losing_working_identity(
        self,
    ) -> None:
        engine = KnownSpeakerBirthdayEngine()
        synthesizer: KnowledgeSynthesizer = RecordingSynthesizer(
            "The human's birthday is February 7."
        )
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "William",
                        "content": "I love birthday parties and my birthday is February 7.",
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "That sounds fun.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
            knowledge_synthesizer=synthesizer,
            working_memory=working_memory,
        )
        await core.initialize("Genesis")
        await working_memory.set_context("current_speaker", "William")

        result = await core.interact("When is my birthday?")

        self.assertEqual(result.response_text, "Your birthday is February 7.")
        request = cast(ReasoningRequest, engine.request)
        self.assertIn("current_speaker: William", request.system_prompt)
        self.assertIn("The human's birthday is February 7.", request.system_prompt)
        self.assertNotIn("I love birthday parties", request.system_prompt)
        self.assertEqual(
            (await core.read_working_memory()).context,
            {"current_speaker": "William"},
        )

        recorder = cast(RecordingSynthesizer, synthesizer)
        self.assertIn(
            "I love birthday parties and my birthday is February 7.",
            recorder.evidence,
        )
        self.assertEqual(
            recorder.instructions,
            MEMORY_STEWARD_SYNTHESIS_FOUNDATION_SEED,
        )

        await core.checkpoint()
        self.assertEqual((await core.read_working_memory()).context, {})

    async def test_speaker_switch_keeps_first_person_memory_bound_to_its_speaker(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=SpeakerIsolationEngine(),
            knowledge_synthesizer=SpeakerAwareBirthdaySynthesizer(),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("My birthday is February 7.")

        birthday_entry = next(
            entry
            for entry in await journal.read()
            if entry.experience.get("input", {}).get("content")
            == "My birthday is February 7."
        )
        self.assertEqual(
            birthday_entry.experience["input"]["speaker"],
            "William",
        )

        await core.interact("I'm Michael.")
        michael_result = await core.interact("What is my birthday?")
        self.assertEqual(michael_result.response_text, "I don't know your birthday.")
        self.assertEqual(
            (await core.read_working_memory()).context,
            {"current_speaker": "Michael"},
        )

        await core.interact("I'm William.")
        william_result = await core.interact("What is my birthday?")
        self.assertEqual(william_result.response_text, "Your birthday is February 7.")
        self.assertEqual(
            (await core.read_working_memory()).context,
            {"current_speaker": "William"},
        )

    async def test_explicit_subject_knowledge_survives_a_speaker_change(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=SpeakerIsolationEngine(),
            knowledge_synthesizer=SpeakerAwareBirthdaySynthesizer(),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("Michael's birthday is January 3.")

        evidence_entry = next(
            entry
            for entry in await journal.read()
            if entry.experience.get("input", {}).get("content")
            == "Michael's birthday is January 3."
        )
        self.assertEqual(evidence_entry.experience["input"]["speaker"], "William")

        await core.interact("I'm Michael.")
        result = await core.interact("What is my birthday?")

        self.assertEqual(result.response_text, "Your birthday is January 3.")
        self.assertEqual(
            (await core.read_working_memory()).context,
            {"current_speaker": "Michael"},
        )

    async def test_resolved_third_person_pronoun_survives_working_memory_flush(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=SpeakerIsolationEngine(),
            knowledge_synthesizer=SpeakerAwareBirthdaySynthesizer(),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await working_memory.set_context("current_subject", "Michael")
        await core.interact("His birthday is January 3.")

        evidence_entry = next(
            entry
            for entry in await journal.read()
            if entry.experience.get("input", {}).get("content")
            == "His birthday is January 3."
        )
        self.assertEqual(
            evidence_entry.experience["input"]["resolved_subject"],
            "Michael",
        )

        await core.checkpoint()
        await core.interact("I'm Michael.")
        result = await core.interact("What is my birthday?")

        self.assertEqual(result.response_text, "Your birthday is January 3.")
        self.assertEqual(
            (await core.read_working_memory()).context,
            {"current_speaker": "Michael"},
        )

    async def test_unresolved_third_person_pronoun_does_not_become_person_specific_knowledge(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=SpeakerIsolationEngine(),
            knowledge_synthesizer=SpeakerAwareBirthdaySynthesizer(),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("His birthday is January 3.")

        await core.interact("I'm Michael.")
        result = await core.interact("What is my birthday?")

        self.assertEqual(result.response_text, "I don't know your birthday.")
        self.assertEqual(
            (await core.read_working_memory()).context,
            {"current_speaker": "Michael"},
        )

    async def test_conflicting_person_specific_evidence_reaches_synthesis_together(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        synthesizer: KnowledgeSynthesizer = RecordingSynthesizer(
            "Conflicting birthday evidence is present."
        )
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=NonConsultingEngine(),
            knowledge_synthesizer=synthesizer,
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("Michael's birthday is January 3.")
        await core.interact("I'm Michael.")
        await core.interact("No, my birthday is January 4.")

        await core.interact("What is my birthday?")

        recorder = cast(RecordingSynthesizer, synthesizer)
        self.assertIn("Michael's birthday is January 3.", recorder.evidence)
        self.assertIn("No, my birthday is January 4.", recorder.evidence)

    async def test_unresolved_conflict_expands_supporting_recall_before_clarifying(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "William",
                        "content": (
                            "Michael directly reported birthday information to William."
                        ),
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "William",
                        "content": "Michael's birthday is January 3.",
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "Michael",
                        "content": "My birthday is January 4.",
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        synthesizer: KnowledgeSynthesizer = RecordingSynthesizer(
            "Conflicting birthday evidence remains unresolved."
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="What is my birthday?",
            memory=InMemoryMemoryStore(),
            journal=journal,
            current_speaker="Michael",
            current_context={"current_speaker": "Michael"},
            synthesizer=synthesizer,
            recall_limit=2,
        )

        result = await tool.invoke(
            {"action": "recall", "focus": "What is my birthday?"}
        )

        context = cast(dict[str, Any], result["context"])
        self.assertEqual(context["recursive_recall_depth"], 1)
        self.assertEqual(context["evidence_items_examined"], 3)
        self.assertEqual(len(context["prior_experience"]), 3)
        self.assertEqual(
            context["clarification_question"],
            "I have conflicting information about your birthday. "
            "Is it January 3 or January 4?",
        )
        recorder = cast(RecordingSynthesizer, synthesizer)
        self.assertIn(
            "Michael directly reported birthday information to William.",
            recorder.evidence,
        )

    async def test_rabbit_hole_support_can_resolve_tie_before_clarification(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "William",
                        "content": (
                            "William heard the January 3 birthday claim directly "
                            "from Michael."
                        ),
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "William",
                        "content": "Michael's birthday is January 3.",
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "Michael",
                        "content": "My birthday is January 4.",
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        synthesizer: KnowledgeSynthesizer = RecordingSynthesizer(
            "Conflicting birthday evidence remains preserved."
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="What is my birthday?",
            memory=InMemoryMemoryStore(),
            journal=journal,
            current_speaker="Michael",
            current_context={"current_speaker": "Michael"},
            scorecard_evaluator=RabbitHoleSupportEvaluator(),
            synthesizer=synthesizer,
            recall_limit=2,
        )

        result = await tool.invoke(
            {"action": "recall", "focus": "What is my birthday?"}
        )

        context = cast(dict[str, Any], result["context"])
        self.assertEqual(context["recursive_recall_depth"], 1)
        self.assertIsNone(context["clarification_question"])
        self.assertIn(
            "Adjudicated current knowledge: Michael's birthday is January 3.",
            context["summary"],
        )
        recorder = cast(RecordingSynthesizer, synthesizer)
        self.assertIn(
            "William heard the January 3 birthday claim directly from Michael.",
            recorder.evidence,
        )
        self.assertTrue(
            any(
                item.startswith(
                    "Prototype contradiction adjudication: "
                    "preferred=Michael's birthday is January 3."
                )
                for item in recorder.evidence
            )
        )

    async def test_non_birthday_detector_uses_generic_contradiction_boundary(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=FavoriteColorEngine(),
            knowledge_synthesizer=RecordingSynthesizer(
                "Conflicting favorite-color evidence is present."
            ),
            proposition_detector=FavoriteColorDetector(),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("Michael's favorite color is blue.")
        await core.interact("I'm Michael.")
        await core.interact("My favorite color is red.")

        result = await core.interact("What is my favorite color?")

        self.assertEqual(
            result.response_text,
            "I have conflicting information about your favorite color. "
            "Is it blue or red?",
        )

    async def test_live_stronger_birthday_evidence_becomes_current_knowledge(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        engine = AdjudicatedBirthdayEngine()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
            knowledge_synthesizer=RecordingSynthesizer(
                "Conflicting birthday evidence remains preserved."
            ),
            scorecard_evaluator=CurrentSpeakerSourceEvaluator(),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("Michael's birthday is January 3.")
        await core.interact("I'm Michael.")
        await core.interact("No, my birthday is January 4.")

        result = await core.interact("What is my birthday?")

        self.assertEqual(result.response_text, "Your birthday is January 4.")
        self.assertIsNotNone(engine.request)
        request = cast(ReasoningRequest, engine.request)
        self.assertIn(
            "Adjudicated current knowledge: No, my birthday is January 4.",
            request.system_prompt,
        )
        self.assertIn(
            "Supporting synthesis: Conflicting birthday evidence remains preserved.",
            request.system_prompt,
        )

    async def test_live_equal_birthday_contradiction_asks_for_clarification(
        self,
    ) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=NonConsultingEngine(),
            knowledge_synthesizer=RecordingSynthesizer(
                "Conflicting birthday evidence is present."
            ),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("Michael's birthday is January 3.")
        await core.interact("I'm Michael.")
        await core.interact("No, my birthday is January 4.")

        result = await core.interact("What is my birthday?")

        self.assertEqual(
            result.response_text,
            "I have conflicting information about your birthday. "
            "Is it January 3 or January 4?",
        )
        experience = (await journal.read())[-1].experience
        self.assertEqual(
            experience["memory_steward"]["recalled_context"]["clarification_question"],
            result.response_text,
        )

    async def test_clarification_answer_becomes_resolution_evidence(self) -> None:
        journal = InMemoryJournalStore()
        working_memory = InMemoryWorkingMemoryStore()
        engine = AdjudicatedBirthdayEngine()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=engine,
            knowledge_synthesizer=RecordingSynthesizer(
                "Conflicting birthday evidence remains preserved."
            ),
            working_memory=working_memory,
        )
        await core.initialize("Genesis")

        await core.interact("I'm William.")
        await core.interact("Michael's birthday is January 3.")
        await core.interact("I'm Michael.")
        await core.interact("My birthday is January 4.")

        first_question = await core.interact("What is my birthday?")
        self.assertEqual(
            first_question.response_text,
            "I have conflicting information about your birthday. "
            "Is it January 3 or January 4?",
        )
        pending = (await core.read_working_memory()).context["pending_clarification"]
        self.assertEqual(pending["subject"], "Michael")
        self.assertEqual(pending["attribute"], "birthday")

        clarification = await core.interact("January 4.")
        self.assertEqual(
            clarification.response_text,
            "Got it. I've recorded your clarification: your birthday is January 4.",
        )
        self.assertIsNone(
            (await core.read_working_memory()).context["pending_clarification"]
        )

        answer = await core.interact("What is my birthday?")
        self.assertEqual(answer.response_text, "Your birthday is January 4.")

        memories = await core.read_memory()
        consolidated = [
            memory
            for memory in memories
            if memory.content == "Michael's birthday is January 4."
        ]
        self.assertEqual(len(consolidated), 1)
        self.assertEqual(consolidated[0].memory_class, MemoryClass.SEMANTIC)
        self.assertEqual(
            consolidated[0].associations,
            ("Michael", "birthday", "January 4"),
        )
        self.assertIn(
            "Explicit human clarification resolved a prior contradiction.",
            consolidated[0].grounding,
        )
        self.assertIn(
            "Literal clarification: January 4.",
            consolidated[0].grounding,
        )

        second_answer = await core.interact("What is my birthday?")
        self.assertEqual(second_answer.response_text, "Your birthday is January 4.")
        memories_after_second_recall = await core.read_memory()
        self.assertEqual(
            len(
                [
                    memory
                    for memory in memories_after_second_recall
                    if memory.content == "Michael's birthday is January 4."
                ]
            ),
            1,
        )

        resolution_entry = next(
            entry
            for entry in await journal.read()
            if entry.experience.get("resolved_clarification") is not None
        )
        self.assertEqual(
            resolution_entry.experience["input"]["content"],
            "January 4.",
        )
        self.assertEqual(
            resolution_entry.experience["resolved_clarification"]["proposition"],
            "Michael's birthday is January 4.",
        )

    def test_confidence_weight_support_prefers_materially_stronger_evidence(self) -> None:
        earlier = EvidenceAssessment(
            proposition="Michael's birthday is January 3.",
            prior=EvidenceScorecard(confidence=0.7, weight=0.7),
            effective=EvidenceScorecard(confidence=0.7, weight=0.7),
        )
        correction = EvidenceAssessment(
            proposition="Michael's birthday is January 4.",
            prior=EvidenceScorecard(confidence=0.9, weight=0.8),
            effective=EvidenceScorecard(confidence=0.9, weight=0.8),
        )

        decision = adjudicate_contradiction(earlier, correction)

        self.assertTrue(decision.resolved)
        self.assertEqual(
            decision.preferred_proposition,
            "Michael's birthday is January 4.",
        )
        self.assertFalse(decision.clarification_required)
        self.assertAlmostEqual(decision.support_delta, 0.23)

    def test_near_equal_support_requires_clarification(self) -> None:
        first = EvidenceAssessment(
            proposition="Michael's birthday is January 3.",
            prior=EvidenceScorecard(confidence=0.8, weight=0.5),
            effective=EvidenceScorecard(confidence=0.8, weight=0.5),
        )
        second = EvidenceAssessment(
            proposition="Michael's birthday is January 4.",
            prior=EvidenceScorecard(confidence=0.5, weight=0.8),
            effective=EvidenceScorecard(confidence=0.5, weight=0.8),
        )

        decision = adjudicate_contradiction(first, second)

        self.assertFalse(decision.resolved)
        self.assertIsNone(decision.preferred_proposition)
        self.assertTrue(decision.clarification_required)
        self.assertAlmostEqual(decision.support_delta, 0.0)

    def test_support_within_prototype_epsilon_requires_clarification(self) -> None:
        first = EvidenceAssessment(
            proposition="Michael's birthday is January 3.",
            prior=EvidenceScorecard(confidence=0.8, weight=0.6),
            effective=EvidenceScorecard(confidence=0.8, weight=0.6),
        )
        second = EvidenceAssessment(
            proposition="Michael's birthday is January 4.",
            prior=EvidenceScorecard(confidence=0.75, weight=0.6),
            effective=EvidenceScorecard(confidence=0.75, weight=0.6),
        )

        decision = adjudicate_contradiction(first, second)

        self.assertFalse(decision.resolved)
        self.assertTrue(decision.clarification_required)
        self.assertAlmostEqual(decision.support_delta, 0.03)

    async def test_live_recall_derives_effective_scorecard_through_evaluator(
        self,
    ) -> None:
        memory = InMemoryMemoryStore()
        await memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="Michael's birthday is January 3.",
                associations=("Michael", "birthday"),
                grounding=("William reported it.",),
                confidence=0.7,
                weight=0.6,
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        evaluator = RecordingScorecardEvaluator()
        synthesizer: KnowledgeSynthesizer = RecordingSynthesizer(
            "Michael's birthday may be January 3."
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Genesis")),
            input_text="What is my birthday?",
            memory=memory,
            journal=InMemoryJournalStore(),
            current_speaker="Michael",
            current_context={
                "current_speaker": "Michael",
                "current_subject": "Michael",
            },
            scorecard_evaluator=evaluator,
            synthesizer=synthesizer,
        )

        await tool.invoke({"action": "recall", "focus": "What is my birthday?"})

        self.assertEqual(len(evaluator.calls), 1)
        self.assertEqual(evaluator.calls[0]["current_speaker"], "Michael")
        self.assertEqual(
            evaluator.calls[0]["current_context"]["current_subject"],
            "Michael",
        )
        recorder = cast(RecordingSynthesizer, synthesizer)
        self.assertIn(
            "Current effective scorecard: confidence=0.800; weight=0.800; "
            "support=0.640; content=Michael's birthday is January 3.",
            recorder.evidence,
        )

    async def test_live_recall_supplies_scorecard_provenance_and_current_context_to_synthesis(
        self,
    ) -> None:
        memory = InMemoryMemoryStore()
        await memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="Michael's birthday is January 3.",
                associations=("Michael", "birthday"),
                grounding=("William reported it.",),
                confidence=0.7,
                weight=0.6,
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        journal = InMemoryJournalStore()
        await journal.append(
            JournalEntry(
                kind="interaction",
                experience={
                    "input": {
                        "source": "human",
                        "speaker": "William",
                        "resolved_subject": "Michael",
                        "content": "Michael's birthday is January 3.",
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": "Noted.",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        working_memory = InMemoryWorkingMemoryStore()
        synthesizer: KnowledgeSynthesizer = RecordingSynthesizer(
            "Michael's birthday may be January 3."
        )
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=await self._foundation(),
            journal=journal,
            memory=memory,
            diagnostics=InMemoryDiagnosticStore(),
            engine=NonConsultingEngine(),
            knowledge_synthesizer=synthesizer,
            working_memory=working_memory,
        )
        await core.initialize("Genesis")
        await working_memory.set_context("current_speaker", "Michael")
        await working_memory.set_context("current_subject", "Michael")

        await core.interact("What is my birthday?")

        recorder = cast(RecordingSynthesizer, synthesizer)
        self.assertIn(
            "Long-term prior scorecard: confidence=0.700; weight=0.600; "
            "support=0.420; content=Michael's birthday is January 3.",
            recorder.evidence,
        )
        self.assertIn(
            "Experience provenance; source=William; resolved_subject=Michael; "
            "content=Michael's birthday is January 3.",
            recorder.evidence,
        )
        self.assertTrue(
            any(
                item.startswith(
                    "Current conscious evidence context: current_speaker=Michael;"
                )
                and "'current_subject': 'Michael'" in item
                for item in recorder.evidence
            )
        )

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


if __name__ == "__main__":
    unittest.main()
