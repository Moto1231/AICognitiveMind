from typing import Protocol

from aicognitive_mind.domain import CognitiveMind, ReasoningRequest
from aicognitive_mind.engines import ReasoningEngine


class KnowledgeSynthesizer(Protocol):
    async def synthesize(
        self,
        mind: CognitiveMind,
        focus: str,
        evidence: tuple[str, ...],
        instructions: str,
    ) -> str: ...


class DirectKnowledgeSynthesizer:
    """Deterministic fallback used when no model-backed synthesis process is available."""

    async def synthesize(
        self,
        mind: CognitiveMind,
        focus: str,
        evidence: tuple[str, ...],
        instructions: str,
    ) -> str:
        del mind, focus, instructions
        return "\n".join(evidence) if evidence else "No relevant knowledge is available."


class ReasoningKnowledgeSynthesizer:
    """Runs a separate reasoning pass in the Memory Steward role without tool access."""

    def __init__(self, engine: ReasoningEngine) -> None:
        self._engine = engine

    async def synthesize(
        self,
        mind: CognitiveMind,
        focus: str,
        evidence: tuple[str, ...],
        instructions: str,
    ) -> str:
        if not evidence:
            return "No relevant knowledge is available."

        rendered_evidence = "\n".join(f"- {item}" for item in evidence)
        proposal = await self._engine.propose(
            ReasoningRequest(
                mind=mind,
                input_text=(
                    f"Focus:\n{focus}\n\n"
                    "Selected evidence:\n"
                    f"{rendered_evidence}"
                ),
                system_prompt=instructions,
            ),
            tools=(),
        )
        summary = proposal.response_text.strip()
        if not summary:
            raise RuntimeError("Knowledge synthesis returned an empty summary")
        return summary
