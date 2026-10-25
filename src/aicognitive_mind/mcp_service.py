from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aicognitive_mind.commit import atomic
from aicognitive_mind.journal_payload import journal_safe_value

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
    CONSCIOUS_WORKSPACE_SYSTEM_PROMPT,
)
from aicognitive_mind.storage import JournalStore, MemoryStore, MindStore
from aicognitive_mind.steward_agent import ModelMemorySteward
from aicognitive_mind.task_dispatcher import TaskModelDispatcher
from aicognitive_mind.host_behaviors import HostBehaviorRegistry
from aicognitive_mind.core_skills import REQUIRED_SKILLS, required_skill_catalog
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.state_context import CurrentStateLedger, CurrentStateLedgerRepository
from aicognitive_mind.timing import StageTimer, emit

from aicognitive_mind.task_behaviors import (
    TaskBehaviorRegistry,
    TaskExecutionContext,
    TaskPromptAssembler,
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
        *,
        steward_factory: Callable[..., MemoryStewardTool] = ModelMemorySteward,
    ) -> None:
        self._mind = mind
        self._journal = journal
        self._memory = memory
        records = RuntimeRecords(mind)
        self._steward_factory = steward_factory
        self._steward_runtime = TaskModelDispatcher(records, timeout=30)
        self._host_behaviors = HostBehaviorRegistry(records)
        self._task_prompt_assembler = TaskPromptAssembler(TaskBehaviorRegistry(records))

    async def _compose_reasoning_contract(self) -> str:
        task_layers = await self._task_prompt_assembler.system_prompt(TaskExecutionContext(
            task="reasoning",
            provider="connected-host",
            model="host-selected",
        ))
        speaker_grounding = (
            "\n\nSPEAKER GROUNDING RULE (mandatory): If current_state.fields."
            "who_is_speaking is unknown, do not address the current human by a "
            "name recalled from history or account metadata. Ask 'Who am I speaking "
            "with?' before personalized attribution. A remembered name is not "
            "evidence of the current speaker. Explicit self-identification may "
            "be represented as self-reported; camera/voice inference remains "
            "provisional until validated. Unknown physical presence must remain "
            "unknown without actual presence evidence."
        )
        return CONSCIOUS_WORKSPACE_SYSTEM_PROMPT + speaker_grounding + "\n\n" + task_layers

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
        journal_count = await count(self._journal, exclude_checkpoint_type="current_state_ledger")
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

    @atomic
    async def begin_interaction(
        self, user_message: str, host_working_context: dict[str, Any] | None = None,
        *, source: str = "human", input_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Return recalled knowledge plus Axiom's persisted current-state ledger."""
        timer = StageTimer(f"begin_interaction source={source}")
        with timer.stage("mind"):
            mind = await self._require_mind()
        with timer.stage("state_context"):
            state_context = await self._load_current_state()
        steward = self._steward_factory(
            mind=mind,
            input_text=user_message,
            memory=self._memory,
            journal=self._journal,
            working_context={**(host_working_context or {}),
                             "input_source": source, "input_context": input_context},
            current_state=state_context.as_context(),
            runtime=self._steward_runtime,
        )
        with timer.stage("recall"):
            recalled = await steward.invoke(
                {
                    "action": "recall",
                    "focus": user_message,
                }
            )
        with timer.stage("contract"):
            contract = await self._compose_reasoning_contract()
        with timer.stage("behaviors"):
            behaviors = await self._host_behaviors.selected("reasoning")
        with timer.stage("state"):
            current_state = await self._refresh_current_state(
                mind, steward.state_context(), user_message, host_working_context or {}, contract,
                [item.model_dump(mode="json") for item in behaviors],
                source=source, input_context=input_context,
            )
        timer.log()
        return {
            "status": "ready_to_reason",
            "idempotency_key": uuid4().hex,
            "mind": mind.model_dump(mode="json"),
            "recalled_context": recalled["context"],
            "memory_assessment": steward.assessment,
            "current_state": current_state.as_context(),
            "speaker_identification_required": (
                source == "human"
                and current_state.fields["who_is_speaking"].status == "unknown"
            ),
            "conscious_workspace_contract": contract,
            "next_step": (
                "Use the Steward's assessment and any returned brief. A no_recall_needed outcome "
                "means work can proceed using current context; do not force a lookup. "
                "If unresolved evidence includes "
                "investigation guidance, pursue the material questions that can change or clarify "
                "the conclusion and submit useful findings as current_evidence. If resolution "
                "readiness says candidate_ready, you may explicitly propose that exact value in "
                "belief_transitions; the Memory Steward will independently revalidate it before "
                "changing current belief. Do not silently rewrite belief. If it says reframe_required, "
                "propose the exact competing values in belief_reframes only when the evidence-backed "
                "finding supplies explicit scopes for both values. "
                "Before presenting the final answer, call complete_interaction with the response "
                "text, updated host_working_context, evidence and optional memory suggestions. "
                "The Steward independently reviews the whole result even when suggestions are empty. "
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
        *,
        source: str = "human",
        input_context: dict[str, Any] | None = None,
        runtime_source: str = "connected_mcp_host",
        host_working_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Let the Steward choose and route learning, then atomically commit the experience."""
        timer = StageTimer(f"complete_interaction source={source}")
        with timer.stage("mind"):
            mind = await self._require_mind()
        with timer.stage("state_context"):
            state_context = await self._load_current_state()
        steward = self._steward_factory(
            mind=mind,
            input_text=user_message,
            memory=self._memory,
            journal=self._journal,
            working_context={**(host_working_context or {}),
                             "input_source": source, "input_context": input_context},
            current_state=state_context.as_context(),
            runtime=self._steward_runtime,
        )
        with timer.stage("review"):
            review = await steward.review_interaction(
                response_text, proposed_memories, current_evidence,
                belief_transitions, belief_reframes,
            )

        with timer.stage("evidence"):
            for evidence in review["current_evidence"]:
                await steward.invoke(
                    {
                        "action": "consider_evidence",
                        **evidence.model_dump(mode="json"),
                    }
                )

        reframe_decisions: list[dict[str, Any]] = []
        with timer.stage("reframes"):
            for proposal in review["belief_reframes"]:
                reframe = await steward.invoke(
                    {
                        "action": "reframe_belief",
                        **proposal.model_dump(mode="json"),
                    }
                )
                reframe_decisions.append(reframe)

        transition_decisions: list[dict[str, Any]] = []
        with timer.stage("transitions"):
            for proposal in review["belief_transitions"]:
                transition = await steward.invoke(
                    {
                        "action": "transition_belief",
                        **proposal.model_dump(mode="json"),
                    }
                )
                transition_decisions.append(transition)

        decisions: list[dict[str, Any]] = []
        with timer.stage("memories"):
            for proposal in review["proposed_memories"]:
                decision = await steward.invoke(
                    {
                        "action": "propose_memory",
                        **proposal.model_dump(mode="json"),
                    }
                )
                decisions.append(decision)

        with timer.stage("steward_complete"):
            trace = await steward.complete()
            trace_payload = trace.model_dump(mode="python")
            trace_payload["recalled_context"] = steward.host_context()
            trace_payload["assessment"] = steward.assessment
        with timer.stage("journal_append"):
            journal_entry = await self._journal.append(
                JournalEntry(
                    kind=JournalKind.INTERACTION,
                    experience=journal_safe_value({
                        "input": {
                            "source": source,
                            "content": user_message,
                            **({"context": input_context} if input_context else {}),
                        },
                        "memory_steward": trace_payload,
                        "expression": {
                            "source": "conscious_workspace",
                            "content": response_text,
                        },
                        "reasoning_runtime": {
                            "source": runtime_source,
                        },
                    }),
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
        timer.log()

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
            "memory_review": steward.assessment,
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
        started = time.perf_counter()
        ledger = await CurrentStateLedgerRepository(self._journal).load()
        emit("timing ledger.load total=%.3fs", time.perf_counter() - started)
        return ledger

    async def _persist_current_state(self, ledger: CurrentStateLedger) -> None:
        started = time.perf_counter()
        await self._journal.append(
            JournalEntry(kind=JournalKind.CHECKPOINT, experience={
                "checkpoint_type": "current_state_ledger",
                "state_ledger": journal_safe_value(ledger.as_context()),
            }),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        emit("timing ledger.persist total=%.3fs", time.perf_counter() - started)

    async def _refresh_current_state(
        self, mind: CognitiveMind, recalled: dict[str, Any], message: str,
        working: dict[str, Any], contract: str, behaviors: list[dict[str, Any]],
        *, source: str = "human", input_context: dict[str, Any] | None = None,
    ) -> CurrentStateLedger:
        ledger = await self._load_current_state()
        # A missing mood field marks a ledger that has not received begin_context.
        # This also upgrades existing persisted ledgers without resetting identity.
        first_context = ledger.revision == 0 or "mood" not in ledger.fields
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
        previous_skills = ledger.fields.get("skills")
        remembered_skills = (
            [item for item in previous_skills.value if not (
                isinstance(item, dict) and item.get("slug") in REQUIRED_SKILLS
            )]
            if previous_skills is not None and previous_skills.status == "current"
            and isinstance(previous_skills.value, list)
            else []
        )
        if recalled.get("recall_outcome") not in {"no_recall_needed", "no_relevant_memory"}:
            remembered_skills = [
                {"memory_class": m.get("memory_class"), "content": m.get("content"),
                 "associations": m.get("associations", [])}
                for m in recalled.get("durable_memory", [])
                if m.get("memory_class") == MemoryClass.PROCEDURAL.value
            ][:12]
        packaged_skills = [
            {key: value for key, value in item.items() if key != "content"}
            for item in required_skill_catalog()
        ]
        ledger.answer("skills", [*packaged_skills, *remembered_skills],
                      source="packaged_runtime_protocols_and_grounded_procedures",
                      note="Required server protocols are loaded in the reasoning contract; "
                           "host plugin or catalog refresh is not verified.")
        if first_context:
            ledger.answer("mood", None, status="unknown",
                          source="memory_steward_no_grounded_mood",
                          note="Mood has not been assessed from evidence.")
        summary = working.get("summary")
        if summary:
            ledger.answer("active_topic", summary, source="host_working_context")
            ledger.answer("current_context", summary, source="host_working_context")
        elif ledger.fields["active_topic"].status == "unknown":
            ledger.answer("active_topic", message,
                          source="current_human_input" if source == "human" else source)
        if first_context and not summary:
            ledger.answer("current_context", message, source="current_human_input"
                          if source == "human" else source)
        participants = working.get("participants", [])
        if participants:
            ledger.answer("interlocutor", {
                "participants": participants,
                "active_speaker": working.get("active_speaker"),
                "addressee": working.get("addressee"),
            }, source="validated_host_working_context")
            ledger.answer("presence", participants, source="validated_host_working_context")
            ledger.answer("who_is_present", participants, source="validated_host_working_context")
            speaker = next((p for p in participants if
                            p.get("participant_id") == working.get("active_speaker")), None)
            if speaker:
                ledger.answer("who_is_speaking", speaker,
                              source="validated_host_working_context")
            else:
                ledger.invalidate("who_is_speaking", event="speaker_not_grounded")
        elif source == "human":
            ledger.invalidate("who_is_speaking", event="speaker_not_grounded")
            ledger.answer("interlocutor", {
                "type": "current human interlocutor", "identity_status": "unresolved",
            }, source="current_human_input")
            if (
                ledger.fields["presence"].status == "unknown"
                or ledger.fields["presence"].source == "validated_host_working_context"
            ):
                ledger.answer("presence", {"interaction_presence": "human input received",
                    "physical_presence": "unknown"}, source="current_human_input")
        else:
            ledger.invalidate("who_is_speaking", event="nonhuman_input")
            ledger.invalidate("interlocutor", event="nonhuman_input",
                              note="Sensory input does not establish a current human speaker.")
            observed_presence = (input_context or {}).get("presence")
            if isinstance(observed_presence, dict) and observed_presence:
                ledger.answer("presence", observed_presence, source=source)
                ledger.answer("who_is_present", observed_presence, source=source)
            elif (
                ledger.fields["presence"].status == "unknown"
                or ledger.fields["presence"].source in {
                    "current_human_input", "validated_host_working_context",
                }
            ):
                ledger.invalidate("presence", event="nonhuman_input",
                                  note="Sensory input does not establish participant presence.")
        if summary or working.get("unresolved_references"):
            ledger.answer("decisions_and_open_questions", {
                "working_summary": summary or "",
                "unresolved_references": working.get("unresolved_references", []),
            }, source="host_working_context")
        ledger.answer("active_task", "reasoning",
                      source="active_mcp_interaction" if source == "human" else source)
        ledger.answer("connection_status", {"mind_service": "available_for_current_interaction"},
                      source="successful_begin_interaction")
        ledger.answer("capabilities", ["read_current_state", "update_current_state",
            "begin_interaction", "complete_interaction"], source="registered_mind_service_operations")
        if working.get("unresolved_references"):
            ledger.answer("pending_work", working["unresolved_references"], source="host_working_context")
        elif ledger.fields["pending_work"].status == "unknown":
            ledger.answer("pending_work", [], source="initial_state")
        if first_context:
            # A connected conversation does not establish physical presence or mood.
            # Preserve grounded evidence already in the ledger when upgrading.
            if "who_is_present" not in ledger.fields:
                ledger.answer("who_is_present", None, status="unknown",
                              source="memory_steward_no_presence_evidence")
            if "who_is_speaking" not in ledger.fields:
                ledger.answer("who_is_speaking", None, status="unknown",
                              source="memory_steward_no_speaker_evidence")
        after = {k: v.model_dump(mode="json") for k, v in ledger.fields.items()}
        if after != before:
            ledger.revision += 1
            from aicognitive_mind.domain import utc_now
            ledger.updated_at, ledger.last_event = utc_now(), (
                "begin_context" if first_context else "interaction_started"
            )
            await self._persist_current_state(ledger)
        return ledger

    async def _require_mind(self) -> CognitiveMind:
        mind = await self._mind.load()
        if mind is None:
            raise RuntimeError(
                "The Mind has not been initialized. Call initialize_mind exactly once first."
            )
        return mind
