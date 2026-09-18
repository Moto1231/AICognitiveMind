import re

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DurableMemory,
    InteractionResult,
    JournalEntry,
    JournalKind,
    MindIdentity,
    ReasoningRequest,
    WorkingMemoryState,
)
from aicognitive_mind.engines import ReasoningEngine
from aicognitive_mind.evidence import EffectiveScorecardEvaluator
from aicognitive_mind.propositions import PropositionDetector
from aicognitive_mind.expression import (
    DirectExpressionRenderer,
    ExpressionRenderer,
)
from aicognitive_mind.foundation import (
    CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
    CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
)
from aicognitive_mind.knowledge import (
    DirectKnowledgeSynthesizer,
    KnowledgeSynthesizer,
)
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.permissions import (
    CognitiveOperation,
    PermissionPolicy,
)
from aicognitive_mind.storage import (
    DiagnosticStore,
    FoundationReader,
    InMemoryWorkingMemoryStore,
    JournalStore,
    MemoryStore,
    MindStore,
    WorkingMemoryStore,
)
from aicognitive_mind.working_memory import WorkingMemoryTool

UNKNOWN_SPEAKER_KNOWLEDGE = (
    "Person-specific long-term knowledge is unavailable until the current speaker "
    "is identified."
)
IDENTITY_CLARIFICATION_RESPONSE = (
    "I don't know who I'm speaking with yet. What's your name?"
)
_IDENTITY_DEPENDENT_TERMS = {
    "address",
    "age",
    "birthday",
    "favorite",
    "favourite",
    "name",
    "preference",
    "preferences",
}


def _speaker_is_known(current_speaker: object) -> bool:
    speaker = str(current_speaker or "").strip().casefold()
    return bool(speaker) and speaker != "unknown"


_SPEAKER_IDENTITY_PATTERN = (
    r"(?:i['’]?m|i am|this is|my name is)\s+"
    r"([A-Za-z][A-Za-z' -]{0,79}?)"
)


def _explicit_speaker_identity(input_text: str) -> str | None:
    match = re.match(
        rf"^\s*{_SPEAKER_IDENTITY_PATTERN}(?=\s*(?:[.!?,]|$))",
        input_text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None

    speaker = " ".join(match.group(1).split())
    if not speaker or len(speaker.split()) > 4:
        return None
    return speaker


def _is_identity_declaration_only(input_text: str) -> bool:
    return (
        re.fullmatch(
            rf"\s*{_SPEAKER_IDENTITY_PATTERN}\s*[.!]?\s*",
            input_text,
            flags=re.IGNORECASE,
        )
        is not None
    )


def _requires_speaker_identity(input_text: str, current_speaker: object) -> bool:
    if _speaker_is_known(current_speaker):
        return False
    normalized = "".join(
        character if character.isalnum() else " " for character in input_text.casefold()
    )
    tokens = set(normalized.split())
    return "my" in tokens and bool(tokens & _IDENTITY_DEPENDENT_TERMS)


def _scope_recalled_knowledge(
    input_text: str,
    current_speaker: object,
    memory_summary: str,
) -> tuple[str, bool]:
    speaker_known = _speaker_is_known(current_speaker)
    normalized = "".join(
        character if character.isalnum() else " " for character in input_text.casefold()
    )
    first_person_reference = bool(
        {"i", "me", "my", "mine"}.intersection(normalized.split())
    )
    if not speaker_known and first_person_reference:
        return UNKNOWN_SPEAKER_KNOWLEDGE, False
    return memory_summary, True


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
        working_memory: WorkingMemoryStore | None = None,
        knowledge_synthesizer: KnowledgeSynthesizer | None = None,
        scorecard_evaluator: EffectiveScorecardEvaluator | None = None,
        proposition_detector: PropositionDetector | None = None,
        expression_renderer: ExpressionRenderer | None = None,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._mind = mind
        self._foundation = foundation
        self._journal = journal
        self._memory = memory
        self._working_memory = working_memory or InMemoryWorkingMemoryStore()
        self._diagnostics = diagnostics
        self._engine = engine
        self._knowledge_synthesizer = knowledge_synthesizer or DirectKnowledgeSynthesizer()
        self._scorecard_evaluator = scorecard_evaluator
        self._proposition_detector = proposition_detector
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
        await self._working_memory.clear()
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

        explicit_speaker = _explicit_speaker_identity(input_text)
        if explicit_speaker is not None:
            await self._working_memory.set_context("current_speaker", explicit_speaker)
            if _is_identity_declaration_only(input_text):
                response_text = f"Got it, {explicit_speaker}."
                journal_entry = await self._journal.append(
                    JournalEntry(
                        kind=JournalKind.INTERACTION,
                        experience={
                            "input": {
                                "source": "human",
                                "speaker": explicit_speaker,
                                "content": input_text,
                            },
                            "expression": {
                                "source": "conscious_workspace",
                                "content": response_text,
                            },
                        },
                    ),
                    recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                )
                return InteractionResult(
                    response_text=response_text,
                    occurred_at=journal_entry.occurred_at,
                )

        working_state = await self._working_memory.read()
        current_speaker = working_state.context.get("current_speaker", "unknown")
        if _requires_speaker_identity(input_text, current_speaker):
            journal_entry = await self._journal.append(
                JournalEntry(
                    kind=JournalKind.INTERACTION,
                    experience={
                        "input": {"source": "human", "content": input_text},
                        "expression": {
                            "source": "conscious_workspace",
                            "content": IDENTITY_CLARIFICATION_RESPONSE,
                        },
                    },
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
            return InteractionResult(
                response_text=IDENTITY_CLARIFICATION_RESPONSE,
                occurred_at=journal_entry.occurred_at,
            )

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

        working_tool = WorkingMemoryTool(self._working_memory)
        memory_steward = MemoryStewardTool(
            mind=mind,
            input_text=input_text,
            memory=self._memory,
            journal=self._journal,
            current_speaker=str(current_speaker),
            current_context=dict(working_state.context),
            scorecard_evaluator=self._scorecard_evaluator,
            proposition_detector=self._proposition_detector,
            synthesizer=self._knowledge_synthesizer,
            synthesis_instructions=synthesis_foundation.content,
        )
        recalled_context = await memory_steward.invoke(
            {"action": "recall", "focus": input_text}
        )
        memory_summary = recalled_context["context"]["summary"]
        clarification_question = recalled_context["context"].get(
            "clarification_question"
        )
        if isinstance(clarification_question, str) and clarification_question:
            memory_trace = await memory_steward.complete()
            journal_entry = await self._journal.append(
                JournalEntry(
                    kind=JournalKind.INTERACTION,
                    experience={
                        "input": {
                            "source": "human",
                            "speaker": current_speaker,
                            "resolved_subject": working_state.context.get(
                                "current_subject"
                            ),
                            "content": input_text,
                        },
                        "memory_steward": memory_trace.model_dump(mode="python"),
                        "expression": {
                            "source": "conscious_workspace",
                            "content": clarification_question,
                        },
                    },
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
            return InteractionResult(
                response_text=clarification_question,
                occurred_at=journal_entry.occurred_at,
            )

        visible_knowledge, recall_allowed = _scope_recalled_knowledge(
            input_text,
            current_speaker,
            memory_summary,
        )
        reasoning_prompt = (
            f"{workspace_foundation.content}\n\n"
            "Current working context (temporary present-state, not long-term memory):\n"
            f"current_speaker: {current_speaker}\n"
            f"context: {working_state.context}\n\n"
            "Relevant knowledge:\n"
            f"{visible_knowledge}"
        )
        self._policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE,
            CognitiveOperation.PROPOSE_RESPONSE,
        )
        tools = (memory_steward, working_tool) if recall_allowed else (working_tool,)
        proposal = await self._engine.propose(
            ReasoningRequest(
                mind=mind,
                input_text=input_text,
                system_prompt=reasoning_prompt,
            ),
            tools=tools,
        )
        memory_trace = await memory_steward.complete()
        expression = await self._expression_renderer.render(
            mind=mind,
            input_text=input_text,
            knowledge=visible_knowledge,
            draft=proposal.response_text,
            instructions=expression_foundation.content,
        )

        journal_entry = await self._journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={
                    "input": {
                        "source": "human",
                        "speaker": current_speaker,
                        "resolved_subject": working_state.context.get("current_subject"),
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

    async def read_working_memory(self) -> WorkingMemoryState:
        await self.load_mind()
        return await self._working_memory.read()

    async def checkpoint(self) -> WorkingMemoryState:
        await self.load_mind()
        state = await self._working_memory.clear()
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                experience={"working_memory_flushed": True},
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        return state
