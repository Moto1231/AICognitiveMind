# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

import re
from typing import Any

from aicognitive_mind.commit import atomic

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
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.prompts import CONSCIOUS_WORKSPACE_SYSTEM_PROMPT
from aicognitive_mind.storage import DiagnosticStore, JournalStore, MemoryStore, MindStore
from aicognitive_mind.tooling import ReasoningTool


_SENSORY_DATA_URL = re.compile(
    r'data:[^,\s"\']+;base64,[A-Za-z0-9+/=\r\n]+',
    re.IGNORECASE,
)
_SENSORY_PAYLOAD_KEYS = {"payload_base64", "image_data", "audio_data"}


def _journal_safe_value(value: Any, *, key: str | None = None) -> Any:
    """Keep encoded sensory media out of journal text without changing live input."""
    if isinstance(value, dict):
        return {
            str(child_key): _journal_safe_value(child_value, key=str(child_key).lower())
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_journal_safe_value(item) for item in value]
    if not isinstance(value, str):
        return value
    if key in _SENSORY_PAYLOAD_KEYS:
        return "[encoded sensory payload omitted from journal; see preserved evidence reference]"
    return _SENSORY_DATA_URL.sub(
        "[encoded sensory payload omitted from journal; see preserved evidence reference]",
        value,
    )


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
        reasoning_tools: tuple[ReasoningTool, ...] = (),
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._mind = mind
        self._journal = journal
        self._memory = memory
        self._diagnostics = diagnostics
        self._engine = engine
        self._reasoning_tools = reasoning_tools
        self._policy = policy or PermissionPolicy()

    @atomic
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
                    "pronouns": mind.identity.pronouns,
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

    @atomic
    async def interact(
        self,
        input_text: str,
        *,
        source: str = "human",
        input_context: dict[str, object] | None = None,
    ) -> InteractionResult:
        mind = await self.load_mind()
        memory_steward = MemoryStewardTool(
            mind=mind,
            input_text=input_text,
            memory=self._memory,
            journal=self._journal,
        )
        governance_steward = GovernanceStewardTool(
            mind=self._mind,
            journal=self._journal,
            input_text=input_text,
            policy=self._policy,
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
            tools=(memory_steward, governance_steward, *self._reasoning_tools),
        )
        memory_trace = await memory_steward.complete()

        journal_entry = await self._journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience=_journal_safe_value({
                    "input": {
                        "source": source,
                        "content": input_text,
                        **({"context": input_context} if input_context else {}),
                    },
                    "memory_steward": memory_trace.model_dump(mode="python"),
                    "governance_steward": {
                        "decisions": [
                            decision.model_dump(mode="python")
                            for decision in governance_steward.decisions
                        ]
                    },
                    "expression": {
                        "source": "conscious_workspace",
                        "content": proposal.response_text,
                    },
                }),
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        # Diagnostics must not turn a committed cognitive operation into a retry.
        try:
            await self._diagnostics.record(proposal.diagnostic)
        except Exception:
            import logging
            logging.getLogger(__name__).warning("Diagnostic recording failed", exc_info=True)

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
