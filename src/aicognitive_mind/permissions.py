from enum import StrEnum

from aicognitive_mind.domain import CognitiveActor


class CognitiveOperation(StrEnum):
    RECORD_JOURNAL = "record_journal"
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
    """Cognitive authority, independent from MongoDB access mechanics."""

    _allowed: dict[CognitiveActor, frozenset[CognitiveOperation]] = {
        CognitiveActor.HUMAN: frozenset(
            {
                CognitiveOperation.PROPOSE_MEMORY,
                CognitiveOperation.PROPOSE_IDENTITY_REVISION,
            }
        ),
        CognitiveActor.CONSCIOUS_WORKSPACE: frozenset(
            {
                CognitiveOperation.RECORD_JOURNAL,
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
                CognitiveOperation.RECORD_JOURNAL,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.SUBCONSCIOUS_MEMORY_STEWARD: frozenset(
            {
                CognitiveOperation.RECORD_JOURNAL,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.REFLECTION_STEWARD: frozenset(
            {
                CognitiveOperation.RECORD_JOURNAL,
                CognitiveOperation.APPROVE_REFLECTION,
                CognitiveOperation.WRITE_DURABLE_MEMORY,
            }
        ),
        CognitiveActor.VALUES_STEWARD: frozenset(
            {
                CognitiveOperation.RECORD_JOURNAL,
                CognitiveOperation.APPROVE_IDENTITY_REVISION,
            }
        ),
        CognitiveActor.KNOWLEDGE_STEWARD: frozenset(
            {
                CognitiveOperation.RECORD_JOURNAL,
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
        self,
        actor: CognitiveActor,
        operation: CognitiveOperation,
    ) -> None:
        if operation not in self._allowed.get(actor, frozenset()):
            raise CognitivePermissionError(f"{actor} may not perform {operation}")

