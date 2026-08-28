from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DurableMemory,
    InteractionResult,
    JournalEntry,
    JournalKind,
    MindIdentity,
    ReasoningRequest,
)
from aicognitive_mind.engines import ReasoningEngine
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.prompts import CONSCIOUS_WORKSPACE_SYSTEM_PROMPT
from aicognitive_mind.storage import DiagnosticStore, JournalStore, MemoryStore, MindStore


class MindNotInitializedError(LookupError):
    pass


class CognitiveCore:
    def __init__(
        self,
        mind: MindStore,
        journal: JournalStore,
        memory: MemoryStore,
        diagnostics: DiagnosticStore,
        engine: ReasoningEngine,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._mind = mind
        self._journal = journal
        self._memory = memory
        self._diagnostics = diagnostics
        self._engine = engine
        self._policy = policy or PermissionPolicy()

    async def initialize(
        self,
        self_name: str,
        foundational_values: tuple[str, ...] = (),
    ) -> CognitiveMind:
        mind = await self._mind.initialize(
            CognitiveMind(
                identity=MindIdentity(
                    self_name=self_name,
                    foundational_values=foundational_values,
                )
            )
        )
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.INITIALIZATION,
                experience={
                    "self_name": mind.identity.self_name,
                    "foundational_values": list(mind.identity.foundational_values),
                    "developmental_state": mind.developmental_state,
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        return mind

    async def load_mind(self) -> CognitiveMind:
        mind = await self._mind.load()
        if mind is None:
            raise MindNotInitializedError("This instance has not initialized its mind")
        return mind

    async def interact(self, input_text: str) -> InteractionResult:
        mind = await self.load_mind()
        memory_steward = MemoryStewardTool(
            mind=mind,
            input_text=input_text,
            memory=self._memory,
            journal=self._journal,
        )
        self._policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE,
            CognitiveOperation.PROPOSE_RESPONSE,
        )
        proposal = await self._engine.propose(
            ReasoningRequest(
                mind=mind,
                input_text=input_text,
                system_prompt=CONSCIOUS_WORKSPACE_SYSTEM_PROMPT,
            ),
            tools=(memory_steward,),
        )
        memory_trace = await memory_steward.complete()

        journal_entry = await self._journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={
                    "input": {
                        "source": "human",
                        "content": input_text,
                    },
                    "memory_steward": memory_trace.model_dump(mode="python"),
                    "expression": {
                        "source": "conscious_workspace",
                        "content": proposal.response_text,
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await self._diagnostics.record(proposal.diagnostic)

        return InteractionResult(
            response_text=proposal.response_text,
            occurred_at=journal_entry.occurred_at,
        )

    async def read_journal(self) -> list[JournalEntry]:
        await self.load_mind()
        return await self._journal.read()

    async def read_memory(self) -> list[DurableMemory]:
        await self.load_mind()
        return await self._memory.read()
