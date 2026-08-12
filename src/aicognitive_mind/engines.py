from typing import Protocol

from aicognitive_mind.domain import (
    DiagnosticObservation,
    ReasoningProposal,
    ReasoningRequest,
)


class ReasoningEngine(Protocol):
    async def propose(self, request: ReasoningRequest) -> ReasoningProposal: ...


class EchoReasoningEngine:
    """Deterministic implementation used without making it part of the mind."""

    def __init__(self, diagnostic_name: str = "echo-a", prefix: str = "I heard") -> None:
        self._diagnostic_name = diagnostic_name
        self._prefix = prefix

    async def propose(self, request: ReasoningRequest) -> ReasoningProposal:
        response = f"{self._prefix}: {request.input_text}"
        return ReasoningProposal(
            response_text=response,
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={
                    "name": self._diagnostic_name,
                    "model": "deterministic-echo",
                    "proposal": response,
                },
            ),
        )

