# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from aicognitive_mind.commit import atomic
import json

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DurableMemory,
    InteractionResult,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
    ReasoningRequest,
)
from aicognitive_mind.engines import ReasoningEngine
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.prompts import CONSCIOUS_WORKSPACE_SYSTEM_PROMPT
from aicognitive_mind.storage import DiagnosticStore, JournalStore, MemoryStore, MindStore
from aicognitive_mind.state_context import apply_current_state_event
from aicognitive_mind.tooling import ReasoningTool


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
        durable_memories = await self._memory.read()
        current_state = await apply_current_state_event(
            self._journal,
            "topic_changed",
            {
                "values": {
                    "identity": {
                        "value": {
                            "self_name": mind.identity.self_name,
                            "pronouns": mind.identity.pronouns,
                            "developmental_state": mind.developmental_state,
                        },
                        "source": "persistent_mind_identity",
                    },
                    "foundations": {
                        "value": {
                            "foundational_values": list(mind.identity.foundational_values),
                            "commitments": list(mind.identity.commitments),
                            "relationships": list(mind.identity.relationships),
                        },
                        "source": "persistent_mind_identity",
                    },
                    "behaviors": {
                        "value": {
                            "contract_loaded": True,
                            "contract_reference": "code-owned CONSCIOUS_WORKSPACE_SYSTEM_PROMPT",
                        },
                        "source": "code_owned_reasoning_contract",
                    },
                    "skills": {
                        "value": [
                            {
                                "memory_class": item.memory_class.value,
                                "content": item.content,
                                "associations": list(item.associations),
                            }
                            for item in durable_memories
                            if item.memory_class == MemoryClass.PROCEDURAL
                        ][:12],
                        "source": "durable_procedural_memory",
                    },
                    "active_topic": {
                        "value": {
                            "source": source,
                            "content": input_text,
                            "input_context": input_context or {},
                        },
                        "source": "current_interaction_input",
                    },
                    "active_task": {"value": "reasoning", "source": "active_core_interaction"},
                    "connection_status": {
                        "value": {"cognitive_core": "available"},
                        "source": "successful_core_interaction_start",
                    },
                    "capabilities": {
                        "value": ["interact", "read_journal", "read_memory"],
                        "source": "cognitive_core_operations",
                    },
                    "interlocutor": {
                        "value": {
                            "source": source,
                            "identity_status": "unresolved",
                            "grounding": ["current interaction boundary"],
                        },
                        "source": "current_interaction_boundary",
                    },
                    "presence": {
                        "value": (
                            input_context["presence"]
                            if input_context and input_context.get("presence")
                            else {
                                "interaction_presence": "input received",
                                "physical_presence": "unknown",
                            }
                        ),
                        "source": "current_input_context",
                    },
                }
            },
            source=f"core:{source}",
        )
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
                system_prompt=(
                    CONSCIOUS_WORKSPACE_SYSTEM_PROMPT
                    + "\n\nPERSISTED CURRENT STATE LEDGER (read before reasoning):\n"
                    + current_state.model_dump_json(indent=2)
                ),
            ),
            tools=(memory_steward, governance_steward, *self._reasoning_tools),
        )
        memory_trace = await memory_steward.complete()

        journal_entry = await self._journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={
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
                },
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
