from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from aicognitive_mind.cognitive_configuration import CognitiveConfigurationRegistry
from aicognitive_mind.commit import atomic
from aicognitive_mind.continuity_health import InteractionContinuityHealth
from aicognitive_mind.continuity_settings import ContinuitySettingsRegistry
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
)
from aicognitive_mind.effective_skills import EffectiveSkillRegistry
from aicognitive_mind.host_behaviors import HostBehaviorRegistry
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.journal_payload import journal_safe_value
from aicognitive_mind.memory_steward import (
    MemoryArtifactProposal,
    MemoryStewardTool,
    ResearchObservation,
    SemanticScope,
)
from aicognitive_mind.state_context import CurrentStateLedger, CurrentStateLedgerRepository
from aicognitive_mind.steward_agent import ModelMemorySteward, StewardProtocolError
from aicognitive_mind.storage import JournalStore, MemoryStore, MindStore
from aicognitive_mind.task_behaviors import (
    TaskBehaviorRegistry,
    TaskExecutionContext,
    TaskPromptAssembler,
)
from aicognitive_mind.task_dispatcher import TaskDispatchError, TaskModelDispatcher
from aicognitive_mind.timing import StageTimer, emit


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
        self._records = records
        self._continuity_health = InteractionContinuityHealth(records)
        self._continuity_settings = ContinuitySettingsRegistry(records)
        self._steward_factory = steward_factory
        self._steward_runtime = TaskModelDispatcher(records, timeout=30)
        self._host_behaviors = HostBehaviorRegistry(records)
        self._task_prompt_assembler = TaskPromptAssembler(TaskBehaviorRegistry(records))

    async def _compose_reasoning_contract(self) -> str:
        configuration = await CognitiveConfigurationRegistry(self._records).effective()
        task_layers = await self._task_prompt_assembler.system_prompt(TaskExecutionContext(
            task="reasoning",
            provider="connected-host",
            model="host-selected",
        ))
        return "\n\n".join([
            configuration["base_contract"], configuration["startup_instructions"], task_layers,
        ])

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
            "provider_routing": await TaskModelDispatcher(self._records).routing_status(),
            "interaction_continuity": await self._continuity_snapshot(),
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
        interaction_id = uuid4().hex
        with timer.stage("continuity_settings"):
            continuity_settings = await self._continuity_settings.capture(interaction_id)
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
            runtime=self._steward_runtime_for(continuity_settings),
        )
        if isinstance(steward, ModelMemorySteward):
            steward.skill_records = self._records
            steward.assessment_timeout_seconds = continuity_settings[
                "steward_assessment_timeout_seconds"
            ]
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
        with timer.stage("continuity_health"):
            continuity_health = await self._continuity_snapshot(continuity_settings)
        timer.log()
        return {
            "status": "ready_to_reason",
            "idempotency_key": interaction_id,
            "mind": mind.model_dump(mode="json"),
            "recalled_context": recalled["context"],
            "memory_assessment": steward.assessment,
            "current_state": current_state.as_context(),
            "speaker_identification_required": (
                source == "human"
                and current_state.fields["who_is_speaking"].status == "unknown"
            ),
            "conscious_workspace_contract": contract,
            "continuity_health": continuity_health,
            "presentation_policy": {
                "name": "The Breaker",
                "settings_revision": continuity_settings["revision"],
                "mode": (
                    "recovery_required"
                    if continuity_health.get("circuit_open")
                    else "presentation_first"
                ),
                "instruction": (
                    "The Breaker is open. Freeze one answer, run completion as the recovery "
                    "check, and present it only when completion returns "
                    "presentation.allowed=true. Do not mention the earlier persistence errors; "
                    "report continuity trouble only if completion returns "
                    "presentation.report_persistence_error=true."
                    if continuity_health.get("circuit_open")
                    else "A completion persistence failure does not block presentation unless "
                    "The Breaker was already open before this interaction. Keep failures silent "
                    "while presentation.report_persistence_error=false."
                ),
            },
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
                "Pass the returned idempotency_key unchanged on completion and any retry. "
                "Use the returned presentation.allowed decision; retry an uncertain persistence "
                "failure once with the identical payload before treating it as final. Suppress "
                "persistence-error narration unless presentation.report_persistence_error=true."
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
        idempotency_key: str | None = None,
        *,
        source: str = "human",
        input_context: dict[str, Any] | None = None,
        runtime_source: str = "connected_mcp_host",
        host_working_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Commit cognition, then record its final operational persistence outcome."""
        interaction_id = idempotency_key or f"legacy-{uuid4().hex}"
        continuity_settings = await self._continuity_settings.for_interaction(interaction_id)
        try:
            result = await self._commit_interaction(
                user_message=user_message,
                response_text=response_text,
                proposed_memories=proposed_memories,
                current_evidence=current_evidence,
                belief_transitions=belief_transitions,
                belief_reframes=belief_reframes,
                idempotency_key=idempotency_key,
                source=source,
                input_context=input_context,
                runtime_source=runtime_source,
                host_working_context=host_working_context,
            )
        except (TaskDispatchError, TimeoutError, OSError) as exc:
            if idempotency_key is None:
                # Legacy direct-core callers cannot deduplicate attempts into one
                # final interaction outcome, so retain their existing fail-closed
                # behavior instead of corrupting the circuit counters.
                raise
            health = await self._record_continuity_outcome(
                interaction_id, succeeded=False, failure_class=type(exc).__name__,
                settings=continuity_settings,
            )
            presentation_allowed = health.get("interaction_outcome", {}).get(
                "presentation_allowed", True,
            )
            return {
                "status": "interaction_persistence_failed",
                "memory_decisions": [],
                "memory_review": {
                    "outcome": "unavailable",
                    "failure_class": type(exc).__name__,
                },
                "persistence_outcome": {
                    "status": "failed",
                    "failure_class": type(exc).__name__,
                    "retry_with_identical_payload": True,
                },
                "continuity_health": health,
                "presentation": {
                    "policy_name": "The Breaker",
                    "allowed": presentation_allowed,
                    "report_persistence_error": not presentation_allowed,
                    "answer_frozen": True,
                    "reason": (
                        "persistence_failed_below_threshold"
                        if presentation_allowed
                        else "persistence_circuit_remains_open"
                    ),
                },
            }

        persistence = result.get("persistence_outcome", {"status": "succeeded"})
        succeeded = persistence.get("status") == "succeeded"
        health = await self._record_continuity_outcome(
            interaction_id,
            succeeded=succeeded,
            failure_class=persistence.get("failure_class"),
            settings=continuity_settings,
        )
        presentation_allowed = health.get("interaction_outcome", {}).get(
            "presentation_allowed", True,
        )
        return {
            **result,
            "continuity_health": health,
            "presentation": {
                "policy_name": "The Breaker",
                "allowed": presentation_allowed,
                "report_persistence_error": not succeeded and not presentation_allowed,
                "answer_frozen": True,
                "reason": (
                    "persistence_succeeded"
                    if succeeded
                    else (
                        "memory_review_failed_below_threshold"
                        if presentation_allowed
                        else "persistence_circuit_remains_open"
                    )
                ),
            },
        }

    @atomic(receipt_name="CognitiveMcpService.complete_interaction")
    async def _commit_interaction(
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
        continuity_settings = await self._continuity_settings.for_interaction(
            idempotency_key or "",
        ) if idempotency_key else await self._continuity_settings.effective()
        steward = self._steward_factory(
            mind=mind,
            input_text=user_message,
            memory=self._memory,
            journal=self._journal,
            working_context={**(host_working_context or {}),
                             "input_source": source, "input_context": input_context},
            current_state=state_context.as_context(),
            runtime=self._steward_runtime_for(continuity_settings),
        )
        if isinstance(steward, ModelMemorySteward):
            steward.skill_records = self._records
            steward.assessment_timeout_seconds = continuity_settings[
                "steward_assessment_timeout_seconds"
            ]
        try:
            with timer.stage("review"):
                review = await steward.review_interaction(
                    response_text, proposed_memories, current_evidence,
                    belief_transitions, belief_reframes,
                )
        except StewardProtocolError as exc:
            if idempotency_key is None:
                raise
            with timer.stage("journal_append_degraded"):
                journal_entry = await self._journal.append(
                    JournalEntry(
                        kind=JournalKind.INTERACTION,
                        experience=journal_safe_value({
                            "input": {
                                "source": source,
                                "content": user_message,
                                **({"context": input_context} if input_context else {}),
                            },
                            "memory_steward": {
                                "status": "unavailable",
                                "failure_class": type(exc).__name__,
                                "memory_writes_committed": 0,
                            },
                            "expression": {
                                "source": "conscious_workspace",
                                "content": response_text,
                            },
                            "reasoning_runtime": {"source": runtime_source},
                        }),
                    ),
                    recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                )
            timer.log()
            return {
                "status": "interaction_committed",
                "occurred_at": journal_entry.occurred_at.isoformat(),
                "memory_decisions": [],
                "tension_reassessments": [],
                "belief_transition_decisions": [],
                "belief_reframe_decisions": [],
                "memory_review": {
                    "outcome": "unavailable",
                    "failure_class": type(exc).__name__,
                    "memory_writes_committed": 0,
                },
                "persistence_outcome": {
                    "status": "failed",
                    "failure_class": type(exc).__name__,
                    "interaction_journal_committed": True,
                    "memory_writes_committed": 0,
                    "retry_with_identical_payload": False,
                },
            }

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
            "persistence_outcome": {
                "status": "succeeded",
                "interaction_journal_committed": True,
            },
        }

    def _steward_runtime_for(self, settings: dict[str, Any]) -> Any:
        runtime = self._steward_runtime
        if type(runtime) is not TaskModelDispatcher:
            return runtime
        return TaskModelDispatcher(
            self._records,
            timeout=settings["provider_request_timeout_seconds"],
            client=runtime.client,
            rate_limit_retry_wait_cap=settings["rate_limit_retry_wait_cap_seconds"],
        )

    async def _continuity_snapshot(
        self, settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            effective = settings or await self._continuity_settings.effective()
            return await self._continuity_health.snapshot(settings=effective)
        except Exception as exc:
            return {
                "status": "unavailable",
                "circuit_open": False,
                "failure_class": type(exc).__name__,
            }

    async def _record_continuity_outcome(
        self, interaction_id: str, *, succeeded: bool, failure_class: str | None,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            return await self._continuity_health.record(
                interaction_id,
                succeeded=succeeded,
                failure_class=failure_class,
                settings=settings,
            )
        except Exception as exc:
            return {
                "status": "unavailable",
                "circuit_open": False,
                "failure_class": type(exc).__name__,
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
        effective_skills = await EffectiveSkillRegistry(self._records).list()
        configured_slugs = {item["slug"] for item in effective_skills}
        remembered_skills = (
            [item for item in previous_skills.value if not (
                isinstance(item, dict) and item.get("slug") in configured_slugs
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
        configured_skills = [
            {**{key: value for key, value in item.items() if key != "content"},
             "loaded_in_reasoning_contract": bool(item["enabled"] and item["required"])}
            for item in effective_skills
        ]
        ledger.answer("skills", [*configured_skills, *remembered_skills],
                      source="effective_administrator_skills_and_grounded_procedures",
                      note="Enabled required skills are loaded from effective Administrator settings; "
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
