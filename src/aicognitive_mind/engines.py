from typing import Protocol

from aicognitive_mind.domain import ReasoningProposal, ReasoningRequest


class ReasoningEngine(Protocol):
    @property
    def engine_id(self) -> str: ...

    async def propose(self, request: ReasoningRequest) -> ReasoningProposal: ...


class EchoReasoningEngine:
    """Deterministic engine used to test the Cognitive Core without a provider."""

    def __init__(self, engine_id: str = "echo-engine-a", prefix: str = "I heard") -> None:
        self._engine_id = engine_id
        self._prefix = prefix

    @property
    def engine_id(self) -> str:
        return self._engine_id

    async def propose(self, request: ReasoningRequest) -> ReasoningProposal:
        return ReasoningProposal(
            engine_id=self.engine_id,
            model_name="deterministic-echo",
            response_text=f"{self._prefix}: {request.host_message}",
        )

