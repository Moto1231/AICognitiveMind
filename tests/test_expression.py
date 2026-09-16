import unittest

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    ReasoningProposal,
    ReasoningRequest,
)
from aicognitive_mind.expression import ExpressionRenderer
from aicognitive_mind.foundation import (
    CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
    CONSCIOUS_EXPRESSION_FOUNDATION_SEED,
    CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
    CONSCIOUS_WORKSPACE_FOUNDATION_SEED,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_SEED,
)
from aicognitive_mind.knowledge import KnowledgeSynthesizer
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryFoundationStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)
from aicognitive_mind.tooling import ReasoningTool


class DraftEngine:
    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        del request, tools
        return ReasoningProposal(
            response_text="The human's birthday is February 7.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "draft-engine"},
            ),
        )


class FixedSynthesizer:
    async def synthesize(
        self,
        mind: CognitiveMind,
        focus: str,
        evidence: tuple[str, ...],
        instructions: str,
    ) -> str:
        del mind, focus, evidence, instructions
        return "The human's birthday is February 7."


class RecordingRenderer:
    def __init__(self) -> None:
        self.input_text: str | None = None
        self.knowledge: str | None = None
        self.draft: str | None = None
        self.instructions: str | None = None

    async def render(
        self,
        mind: CognitiveMind,
        input_text: str,
        knowledge: str,
        draft: str,
        instructions: str,
    ) -> ReasoningProposal:
        del mind
        self.input_text = input_text
        self.knowledge = knowledge
        self.draft = draft
        self.instructions = instructions
        return ReasoningProposal(
            response_text="Your birthday is February 7.",
            diagnostic=DiagnosticObservation(
                component="expression_renderer",
                operation="render_response",
                implementation={"name": "recording-expression"},
            ),
        )


class ExpressionBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_rendered_expression_is_returned_and_journaled(self) -> None:
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
        renderer: ExpressionRenderer = RecordingRenderer()
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=foundation,
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=DraftEngine(),
            knowledge_synthesizer=FixedSynthesizer(),
            expression_renderer=renderer,
        )
        await core.initialize("Genesis")

        result = await core.interact("When is my birthday?")

        self.assertEqual(result.response_text, "Your birthday is February 7.")
        recording = renderer
        self.assertEqual(recording.draft, "The human's birthday is February 7.")
        self.assertEqual(recording.knowledge, "The human's birthday is February 7.")
        self.assertEqual(recording.instructions, CONSCIOUS_EXPRESSION_FOUNDATION_SEED)
        experience = (await journal.read())[-1].experience
        self.assertEqual(
            experience["expression"]["content"],
            "Your birthday is February 7.",
        )
        self.assertNotIn("The human's birthday", str(experience["expression"]))


if __name__ == "__main__":
    unittest.main()
