from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aicognitive_mind.commit import atomic

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
from aicognitive_mind.host_behaviors import HostBehaviorRegistry
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.state_context import CurrentStateLedger

from aicognitive_mind.task_behaviors import (
    TaskBehaviorRegistry,
    TaskExecutionContext,
    TaskPromptAssembler,
)

_SENSORY_DATA_URL = re.compile(
    r"data:[^,\s\"']+;base64,[A-Za-z0-9+/=\r\n]+",
    re.IGNORECASE,
)
_SENSORY_PAYLOAD_KEYS = {"payload_base64", "image_data", "audio_data"}


def _journal_safe_value(value: Any, *, key: str | None = None) -> Any:
    """Redact encoded media from the journal while leaving reasoning inputs untouched."""
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
        records = RuntimeRecords(mind)
        self._host_behaviors = HostBehaviorRegistry(records)
        self._task_prompt_assembler = TaskPromptAssembler(TaskBehaviorRegistry(records))

    async def _compose_reasoning_contract(self) -> str:
        host_contract = await self._host_behaviors.compose(CONSCIOUS_WORKSPACE_SYSTEM_PROMPT)
        task_layers = await self._task_prompt_assembler.system_prompt(TaskExecutionContext(
            task="reasoning",
            provider="connected-host",
            model="host-selected",
        ))
        return host_contract + "\n\n" + task_layers

    @atomic
    async def initialize(
        self,
        self_name: str | None = None,
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
        from aicognitive_mind.retrieval import count
        memory_count = await count(self._memory)
        journal_count = await count(self._journal)
        return {
            "mind": mind.model_dump(mode="json"),
            "durable_memory_count": memory_count,
            "journal_experience_count": journal_count,
            "naming": {
                "status": (
                    "prohibited" if journal_count < 1000
                    else "eligible" if journal_count < 2000
                    else "required"
                ),
                "eligible_at_event": 1000,
                "required_at_event": 2000,
                "is_named": mind.identity.self_name is not None,
            },
            "integration": {
                "protocol": "MCP",
                "reasoning_owner": "connected MCP host",
                "identity_owner": "Cognitive Mind",
                "memory_owner": "Cognitive Mind",
            },
        }

    async def begin_interaction(
        self, user_message: str, host_working_context: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Return recalled knowledge plus Axiom's persisted current-state ledger."""
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
        contract = await self._compose_reasoning_contract()
        behaviors = await self._host_behaviors.list()
        current_state = await self._refresh_current_state(
            mind, recalled["context"], user_message, host_working_context or {}, contract,
            [item.model_dump(mode="json") for item in behaviors],
        )
        return {
            "status": "ready_to_reason",
            "idempotency_key": uuid4().hex,
            "mind": mind.model_dump(mode="json"),
            "recalled_context": recalled["context"],
            "current_state": current_state.as_context(),
            "conscious_workspace_contract": contract,
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
                "text and only stable memory proposals that should influence future interactions. "
                "Pass the returned idempotency_key unchanged on completion and any retry."
            ),
        }

    @atomic
    async def complete_interaction(
        self,
        user_message: str,
        response_text: str,
        proposed_memories: tuple[MemoryProposal, ...] = (),
        current_evidence: tuple[ResearchObservation, ...] = (),
        belief_transitions: tuple[BeliefTransitionProposal, ...] = (),
        belief_reframes: tuple[BeliefReframeProposal, ...] = (),
        idempotency_key: str | None = None,
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
                experience=_journal_safe_value({
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
                }),
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

    async def read_current_state(self) -> dict[str, Any]:
        return (await self._load_current_state()).as_context()

    @atomic
    async def update_current_state(
        self, event: str, updates: dict[str, Any] | None = None,
        source: str = "explicit_state_event",
    ) -> dict[str, Any]:
        ledger = await self._load_current_state()
        updated = ledger.apply_event(event, updates, source=source)
        await self._persist_current_state(updated)
        return updated.as_context()

    async def _load_current_state(self) -> CurrentStateLedger:
        if hasattr(self._journal, "latest_checkpoint"):
            entries = await self._journal.latest_checkpoint("current_state_ledger")
        else:
            entries, _ = await self._journal.query_page(
                offset=0, limit=1, newest_first=True,
                kind=JournalKind.CHECKPOINT.value, search="current_state_ledger",
            )
        for entry in entries:
            state = entry.experience.get("state_ledger")
            if entry.experience.get("checkpoint_type") == "current_state_ledger" and isinstance(state, dict):
                try:
                    return CurrentStateLedger.model_validate(state)
                except Exception:
                    pass
        return CurrentStateLedger.empty()

    async def _persist_current_state(self, ledger: CurrentStateLedger) -> None:
        await self._journal.append(
            JournalEntry(kind=JournalKind.CHECKPOINT, experience={
                "checkpoint_type": "current_state_ledger",
                "state_ledger": ledger.as_context(),
            }),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )

    async def _refresh_current_state(
        self, mind: CognitiveMind, recalled: dict[str, Any], message: str,
        working: dict[str, Any], contract: str, behaviors: list[dict[str, Any]],
    ) -> CurrentStateLedger:
        ledger = await self._load_current_state()
        before = {k: v.model_dump(mode="json") for k, v in ledger.fields.items()}
        ledger.answer("identity", mind.identity.model_dump(mode="json") | {
            "developmental_state": mind.developmental_state,
        }, source="persistent_mind_identity")
        ledger.answer("foundations", {
            "foundational_values": list(mind.identity.foundational_values),
            "commitments": list(mind.identity.commitments),
            "relationships": list(mind.identity.relationships),
        }, source="persistent_mind_identity")
        ledger.answer("behaviors", {"rules": behaviors, "contract_loaded": bool(contract)},
                      source="runtime_behavior_assembler")
        ledger.answer("skills", [
            {"memory_class": m.get("memory_class"), "content": m.get("content"),
             "associations": m.get("associations", [])}
            for m in recalled.get("durable_memory", [])
            if m.get("memory_class") == MemoryClass.PROCEDURAL.value
        ][:12], source="memory_steward_recall")
        summary = working.get("summary")
        if summary:
            ledger.answer("active_topic", summary, source="host_working_context")
        elif ledger.fields["active_topic"].status == "unknown":
            ledger.answer("active_topic", message, source="current_human_input")
        participants = working.get("participants", [])
        ledger.answer("interlocutor", {
            "participants": participants,
            "active_speaker": working.get("active_speaker"),
            "addressee": working.get("addressee"),
        } if participants else {"type": "current human interlocutor", "identity_status": "unresolved"},
            source="validated_host_working_context" if participants else "current_human_input")
        if participants:
            ledger.answer("presence", participants, source="validated_host_working_context")
        elif ledger.fields["presence"].status == "unknown":
            ledger.answer("presence", {"interaction_presence": "human input received",
                "physical_presence": "unknown"}, source="current_human_input")
        if summary or working.get("unresolved_references"):
            ledger.answer("decisions_and_open_questions", {
                "working_summary": summary or "",
                "unresolved_references": working.get("unresolved_references", []),
            }, source="host_working_context")
        ledger.answer("active_task", "reasoning", source="active_mcp_interaction")
        ledger.answer("connection_status", {"mind_service": "available_for_current_interaction"},
                      source="successful_begin_interaction")
        ledger.answer("capabilities", ["read_current_state", "update_current_state",
            "begin_interaction", "complete_interaction"], source="registered_mind_service_operations")
        if working.get("unresolved_references"):
            ledger.answer("pending_work", working["unresolved_references"], source="host_working_context")
        elif ledger.fields["pending_work"].status == "unknown":
            ledger.answer("pending_work", [], source="initial_state")
        if ledger.fields["locality"].status == "unknown":
            ledger.invalidate("locality", event="locality_not_grounded")
        if ledger.fields["current_scene"].status == "unknown":
            ledger.invalidate("current_scene", event="scene_not_grounded")
        after = {k: v.model_dump(mode="json") for k, v in ledger.fields.items()}
        if after != before:
            ledger.revision += 1
            from aicognitive_mind.domain import utc_now
            ledger.updated_at, ledger.last_event = utc_now(), "interaction_started"
            await self._persist_current_state(ledger)
        return ledger

    async def _require_mind(self) -> CognitiveMind:
        mind = await self._mind.load()
        if mind is None:
            raise RuntimeError(
                "The Mind has not been initialized. Call initialize_mind exactly once first."
            )
        return mind
