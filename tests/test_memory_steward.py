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


if __name__ == "__main__":
    unittest.main()
