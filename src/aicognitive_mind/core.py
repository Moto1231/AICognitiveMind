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
from aicognitive_mind.expression import DirectExpressionRenderer, ExpressionRenderer
from aicognitive_mind.foundation import (
    CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
    CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
)
from aicognitive_mind.knowledge import DirectKnowledgeSynthesizer, KnowledgeSynthesizer
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import (
    DiagnosticStore,
    FoundationReader,
    JournalStore,
    MemoryStore,
    MindStore,
)


class MindNotInitializedError(LookupError):
    pass


class FoundationNotInitializedError(LookupError):
    pass


class CognitiveCore:
    def __init__(
        self,
        mind: MindStore,
        foundation: FoundationReader,
        journal: JournalStore,
        memory: MemoryStore,
        diagnostics: DiagnosticStore,
        engine: ReasoningEngine,
        knowledge_synthesizer: KnowledgeSynthesizer | None = None,
        expression_renderer: ExpressionRenderer | None = None,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._mind = mind
        self._foundation = foundation
        self._journal = journal
        self._memory = memory
        self._diagnostics = diagnostics
        self._engine = engine
        self._knowledge_synthesizer = knowledge_synthesizer or DirectKnowledgeSynthesizer()
        self._expression_renderer = expression_renderer or DirectExpressionRenderer()
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
        workspace_foundation = await self._foundation.load_active(
            CONSCIOUS_WORKSPACE_FOUNDATION_KEY
        )
        synthesis_foundation = await self._foundation.load_active(
            MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY
        )
        expression_foundation = await self._foundation.load_active(
            CONSCIOUS_EXPRESSION_FOUNDATION_KEY
        )
        if workspace_foundation is None:
            raise FoundationNotInitializedError(
                "The Conscious Workspace foundation has not been initialized"
            )
        if synthesis_foundation is None:
            raise FoundationNotInitializedError(
                "The Memory Steward synthesis foundation has not been initialized"
            )
        if expression_foundation is None:
            raise FoundationNotInitializedError(
                "The Conscious Expression foundation has not been initialized"
            )

        memory_steward = MemoryStewardTool(
            mind=mind,
            input_text=input_text,
            memory=self._memory,
            journal=self._journal,
            synthesizer=self._knowledge_synthesizer,
            synthesis_instructions=synthesis_foundation.content,
        )
        recalled_context = await memory_steward.invoke(
            {"action": "recall", "focus": input_text}
        )
        memory_summary = recalled_context["context"]["summary"]
        reasoning_prompt = (
            f"{workspace_foundation.content}\n\n"
            "Relevant knowledge:\n"
            f"{memory_summary}"
        )
        self._policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE,
            CognitiveOperation.PROPOSE_RESPONSE,
        )
        proposal = await self._engine.propose(
            ReasoningRequest(
                mind=mind,
                input_text=input_text,
                system_prompt=reasoning_prompt,
            ),
            tools=(memory_steward,),
        )
        memory_trace = await memory_steward.complete()
        expression = await self._expression_renderer.render(
            mind=mind,
            input_text=input_text,
            knowledge=memory_summary,
            draft=proposal.response_text,
            instructions=expression_foundation.content,
        )

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
                        "content": expression.response_text,
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        await self._diagnostics.record(proposal.diagnostic)
        await self._diagnostics.record(expression.diagnostic)

        return InteractionResult(
            response_text=expression.response_text,
            occurred_at=journal_entry.occurred_at,
        )

    async def read_journal(self) -> list[JournalEntry]:
        await self.load_mind()
        return await self._journal.read()

    async def read_memory(self) -> list[DurableMemory]:
        await self.load_mind()
        return await self._memory.read()
