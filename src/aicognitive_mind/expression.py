from typing import Protocol

from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    ReasoningProposal,
    ReasoningRequest,
)
from aicognitive_mind.engines import ReasoningEngine


class ExpressionRenderer(Protocol):
    async def render(
        self,
        mind: CognitiveMind,
        input_text: str,
        knowledge: str,
        draft: str,
        instructions: str,
    ) -> ReasoningProposal: ...


class DirectExpressionRenderer:
    """Deterministic fallback that preserves the reasoning draft unchanged."""

    async def render(
        self,
        mind: CognitiveMind,
        input_text: str,
        knowledge: str,
        draft: str,
        instructions: str,
    ) -> ReasoningProposal:
        del mind, input_text, knowledge, instructions
        return ReasoningProposal(
            response_text=draft,
            diagnostic=DiagnosticObservation(
                component="expression_renderer",
                operation="render_response",
                implementation={"name": "direct-expression"},
            ),
        )


class ReasoningExpressionRenderer:
    """Renders an internal reasoning draft as the Mind's human-facing expression."""

    def __init__(self, engine: ReasoningEngine) -> None:
        self._engine = engine

    async def render(
        self,
        mind: CognitiveMind,
        input_text: str,
        knowledge: str,
        draft: str,
        instructions: str,
    ) -> ReasoningProposal:
        return await self._engine.propose(
            ReasoningRequest(
                mind=mind,
                input_text=(
                    f"Human message:\n{input_text}\n\n"
                    f"Relevant knowledge:\n{knowledge}\n\n"
                    f"Reasoning draft:\n{draft}"
                ),
                system_prompt=instructions,
            ),
            tools=(),
        )
