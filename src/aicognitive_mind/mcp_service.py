from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
)
from aicognitive_mind.memory_steward import (
    MemoryArtifactProposal,
    MemoryStewardTool,
    ResearchObservation,
    SemanticScope,
)
from aicognitive_mind.prompts import (
    CONSCIOUS_MEMORY_STEWARD_SYSTEM_PROMPT,
    CONSCIOUS_WORKSPACE_SYSTEM_PROMPT,
)
from aicognitive_mind.storage import JournalStore, MemoryStore, MindStore


class MemoryProposal(BaseModel):
    memory_class: MemoryClass
    content: str = Field(min_length=1)
    associations: tuple[str, ...] = ()
    grounding: tuple[str, ...] = Field(min_length=1)
    artifacts: tuple[MemoryArtifactProposal, ...] = ()


class BeliefTransitionProposal(BaseModel):
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    candidate_value: Any
    scope: SemanticScope | None = None


class BeliefReframeProposal(BaseModel):
    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    existing_value: Any
    proposed_value: Any


class CognitiveMcpService:
    """Host-model interface to one persistent Cognitive Mind."""

    def __init__(
        self,
        mind: MindStore,
        journal: JournalStore,
        memory: MemoryStore,
    ) -> None:
        self._mind = mind
        self._journal = journal
        self._memory = memory

    async def initialize(
        self,
        self_name: str,
        foundational_values: tuple[str, ...] = (),
    ) -> dict[str, Any]:
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
        return {
            "status": "initialized",
            "mind": mind.model_dump(mode="json"),
        }

    async def status(self) -> dict[str, Any]:
        mind = await self._require_mind()
        memories = await self._memory.read()
        journal = await self._journal.read()
        return {
            "mind": mind.model_dump(mode="json"),
            "durable_memory_count": len(memories),
            "journal_experience_count": len(journal),
            "integration": {
                "protocol": "MCP",
                "reasoning_owner": "connected MCP host",
                "identity_owner": "Cognitive Mind",
                "memory_owner": "Cognitive Mind",
            },
        }

    async def begin_interaction(self, user_message: str) -> dict[str, Any]:
        """Return the Mind context the connected host must use before reasoning."""
        mind = await self._require_mind()
        steward = MemoryStewardTool(
            mind=mind,
            input_text=user_message,
            memory=self._memory,
            journal=self._journal,
        )
        recalled = await steward.invoke(
            {
                "action": "recall",
                "focus": user_message,
            }
        )
        return {
            "status": "ready_to_reason",
            "mind": mind.model_dump(mode="json"),
            "recalled_context": recalled["context"],
            "conscious_workspace_contract": CONSCIOUS_WORKSPACE_SYSTEM_PROMPT,
            "next_step": (
                "Reason as this Mind using the recalled context. If unresolved evidence includes "
                "investigation guidance, pursue the material questions that can change or clarify "
                "the conclusion and submit useful findings as current_evidence. If resolution "
                "readiness says candidate_ready, you may explicitly propose that exact value in "
                "belief_transitions; the Memory Steward will independently revalidate it before "
                "changing current belief. Do not silently rewrite belief. If it says reframe_required, "
                "propose the exact competing values in belief_reframes only when the evidence-backed "
                "finding supplies explicit scopes for both values. "
                "Before presenting the final answer, call complete_interaction with the response "
                "text and only stable memory proposals that should influence future interactions."
            ),
        }

    async def complete_interaction(
        self,
        user_message: str,
        response_text: str,
        proposed_memories: tuple[MemoryProposal, ...] = (),
        current_evidence: tuple[ResearchObservation, ...] = (),
        belief_transitions: tuple[BeliefTransitionProposal, ...] = (),
        belief_reframes: tuple[BeliefReframeProposal, ...] = (),
    ) -> dict[str, Any]:
        """Let the Steward review proposed learning, commit accepted memory, and journal the experience."""
        mind = await self._require_mind()
        steward = MemoryStewardTool(
            mind=mind,
            input_text=user_message,
            memory=self._memory,
            journal=self._journal,
        )
        await steward.invoke({"action": "recall", "focus": user_message})

        for evidence in current_evidence:
            await steward.invoke(
                {
                    "action": "consider_evidence",
                    **evidence.model_dump(mode="json"),
                }
            )

        reframe_decisions: list[dict[str, Any]] = []
        for proposal in belief_reframes:
            reframe = await steward.invoke(
                {
                    "action": "reframe_belief",
                    **proposal.model_dump(mode="json"),
                }
            )
            reframe_decisions.append(reframe)

        transition_decisions: list[dict[str, Any]] = []
        for proposal in belief_transitions:
            transition = await steward.invoke(
                {
                    "action": "transition_belief",
                    **proposal.model_dump(mode="json"),
                }
            )
            transition_decisions.append(transition)

        decisions: list[dict[str, Any]] = []
        for proposal in proposed_memories:
            decision = await steward.invoke(
                {
                    "action": "propose_memory",
                    **proposal.model_dump(mode="json"),
                }
            )
            decisions.append(decision)

        trace = await steward.complete()
        journal_entry = await self._journal.append(
            JournalEntry(
                kind=JournalKind.INTERACTION,
                experience={
                    "input": {
                        "source": "human",
                        "content": user_message,
                    },
                    "memory_steward": trace.model_dump(mode="python"),
                    "expression": {
                        "source": "conscious_workspace",
                        "content": response_text,
                    },
                    "reasoning_runtime": {
                        "source": "connected_mcp_host",
                    },
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )

        return {
            "status": "interaction_committed",
            "occurred_at": journal_entry.occurred_at.isoformat(),
            "memory_decisions": decisions,
            "tension_reassessments": [
                tension.model_dump(mode="json")
                for tension in trace.tension_reassessments
            ],
            "belief_transition_decisions": transition_decisions,
            "belief_reframe_decisions": reframe_decisions,
            "memory_steward_contract": CONSCIOUS_MEMORY_STEWARD_SYSTEM_PROMPT,
        }

    async def _require_mind(self) -> CognitiveMind:
        mind = await self._mind.load()
        if mind is None:
            raise RuntimeError(
                "The Mind has not been initialized. Call initialize_mind exactly once first."
            )
        return mind
