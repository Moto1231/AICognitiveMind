from enum import StrEnum

from aicognitive_mind.domain import CognitiveActor


class CognitiveOperation(StrEnum):
    APPEND_EVENT = "append_event"
    PROPOSE_RESPONSE = "propose_response"
    PROPOSE_MEMORY = "propose_memory"
    WRITE_DURABLE_MEMORY = "write_durable_memory"
    PROPOSE_REFLECTION = "propose_reflection"
    APPROVE_REFLECTION = "approve_reflection"
    PROPOSE_IDENTITY_REVISION = "propose_identity_revision"
    APPROVE_IDENTITY_REVISION = "approve_identity_revision"
    EXECUTE_EXTERNAL_ACTION = "execute_external_action"


class CognitivePermissionError(PermissionError):
    pass


class PermissionPolicy:
    """Central authority boundary for the first prototype.

    A component may only perform operations listed here. Most importantly, a
    reasoning engine can propose cognitive material but cannot persist it.
    """

    _allowed: dict[CognitiveActor, frozenset[CognitiveOperation]] = {
        CognitiveActor.HOST: frozenset(
            {
                CognitiveOperation.PROPOSE_MEMORY,
                CognitiveOperation.PROPOSE_IDENTITY_REVISION,
            }
        ),
        CognitiveActor.CONSCIOUS_WORKSPACE: frozenset(
            {
                CognitiveOperation.APPEND_EVENT,
                CognitiveOperation.PROPOSE_MEMORY,
                CognitiveOperation.PROPOSE_REFLECTION,
                CognitiveOperation.PROPOSE_IDENTITY_REVISION,
            }
        ),
        CognitiveActor.SUBCONSCIOUS_LAYER: frozenset(
            {
                CognitiveOperation.PROPOSE_MEMORY,
                CognitiveOperation.PROPOSE_REFLECTION,
            }
        ),
        CognitiveActor.CONSCIOUS_MEMORY_STEWARD: frozenset(
            {
                CognitiveOperation.APPEND_EVENT,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.SUBCONSCIOUS_MEMORY_STEWARD: frozenset(
            {
                CognitiveOperation.APPEND_EVENT,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.REFLECTION_STEWARD: frozenset(
            {
                CognitiveOperation.APPEND_EVENT,
                CognitiveOperation.APPROVE_REFLECTION,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.VALUES_STEWARD: frozenset(
            {
                CognitiveOperation.APPEND_EVENT,
                CognitiveOperation.APPROVE_IDENTITY_REVISION,
            }
        ),
        CognitiveActor.KNOWLEDGE_STEWARD: frozenset(
            {
                CognitiveOperation.APPEND_EVENT,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.REASONING_ENGINE: frozenset(
            {
                CognitiveOperation.PROPOSE_RESPONSE,
                CognitiveOperation.PROPOSE_MEMORY,
                CognitiveOperation.PROPOSE_REFLECTION,
                CognitiveOperation.PROPOSE_IDENTITY_REVISION,
            }
        ),
    }

    def assert_allowed(
        self, actor: CognitiveActor, operation: CognitiveOperation
    ) -> None:
        if operation not in self._allowed.get(actor, frozenset()):
            raise CognitivePermissionError(f"{actor} may not perform {operation}")

