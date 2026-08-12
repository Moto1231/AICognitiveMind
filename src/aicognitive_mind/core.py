from uuid import UUID, uuid4

from aicognitive_mind.domain import (
    Being,
    CognitiveActor,
    CognitiveEvent,
    EventType,
    InteractionResult,
    ReasoningRequest,
)
from aicognitive_mind.engines import ReasoningEngine
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import BeingStore, EventStore


class BeingNotFoundError(LookupError):
    pass


class CognitiveCore:
    def __init__(
        self,
        beings: BeingStore,
        events: EventStore,
        engine: ReasoningEngine,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._beings = beings
        self._events = events
        self._engine = engine
        self._policy = policy or PermissionPolicy()

    async def create_being(
        self, name: str, host_id: str, values: tuple[str, ...] = ()
    ) -> Being:
        being = await self._beings.create(Being(name=name, host_id=host_id, values=values))
        await self._events.append(
            CognitiveEvent(
                being_id=being.being_id,
                event_type=EventType.BEING_CREATED,
                source=CognitiveActor.HOST,
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                payload={
                    "name": being.name,
                    "host_id": being.host_id,
                    "identity_version": being.identity_version,
                },
            )
        )
        return being

    async def interact(self, being_id: UUID, host_message: str) -> InteractionResult:
        being = await self._beings.get(being_id)
        if being is None:
            raise BeingNotFoundError(str(being_id))

        correlation_id = uuid4()
        host_event = await self._events.append(
            CognitiveEvent(
                being_id=being_id,
                event_type=EventType.HOST_MESSAGE_RECEIVED,
                source=CognitiveActor.HOST,
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                payload={"text": host_message},
                correlation_id=correlation_id,
            )
        )

        self._policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE, CognitiveOperation.PROPOSE_RESPONSE
        )
        proposal = await self._engine.propose(
            ReasoningRequest(
                being=being,
                host_message=host_message,
                correlation_id=correlation_id,
            )
        )

        proposal_event = await self._events.append(
            CognitiveEvent(
                being_id=being_id,
                event_type=EventType.REASONING_PROPOSED,
                source=CognitiveActor.REASONING_ENGINE,
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                payload={
                    "engine_id": proposal.engine_id,
                    "model_name": proposal.model_name,
                    "response_text": proposal.response_text,
                    "metadata": proposal.metadata,
                },
                correlation_id=correlation_id,
                causation_id=host_event.event_id,
            )
        )

        response_event = await self._events.append(
            CognitiveEvent(
                being_id=being_id,
                event_type=EventType.RESPONSE_EXPRESSED,
                source=CognitiveActor.CONSCIOUS_WORKSPACE,
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                payload={
                    "text": proposal.response_text,
                    "engine_id": proposal.engine_id,
                },
                correlation_id=correlation_id,
                causation_id=proposal_event.event_id,
            )
        )

        return InteractionResult(
            being_id=being_id,
            response_text=proposal.response_text,
            engine_id=proposal.engine_id,
            correlation_id=correlation_id,
            event_ids=(host_event.event_id, proposal_event.event_id, response_event.event_id),
        )

    async def history(self, being_id: UUID) -> list[CognitiveEvent]:
        if await self._beings.get(being_id) is None:
            raise BeingNotFoundError(str(being_id))
        return await self._events.list_for_being(being_id)

