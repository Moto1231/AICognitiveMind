"""Per-task behavior profiles and runtime-neutral prompt assembly.

Required task skills and optional shared skills are composed ahead of the
separate behavior layer. Runtime context is explicit and deliberately contains
references/current state, not an entire host conversation history.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from aicognitive_mind.task_model_assignments import TASK_LABELS, TaskModelAssignmentRegistry
from aicognitive_mind.host_behaviors import HostBehaviorRegistry
from aicognitive_mind.effective_skills import EffectiveSkillRegistry
from aicognitive_mind.task_skill_defaults import TASK_CORE_SKILL_CONTENT

TaskBehaviorKind = Literal[
    "vision", "audio", "audio_voice", "coding", "image_generation", "summarization",
    "memory_recall", "web_research", "structured_extraction", "reasoning",
]


# Compatibility alias for saved records and external callers. These values now
# surface as protected, required task skills rather than a separate user-facing
# Foundation concept.
TASK_FOUNDATIONS: dict[TaskBehaviorKind, str] = dict(TASK_CORE_SKILL_CONTENT)


class TaskBehavior(BaseModel):
    """Legacy inline behavior profile promoted into the shared behavior catalog."""

    task: TaskBehaviorKind
    name: str = Field(min_length=1, max_length=120)
    instructions: str = Field(default="", max_length=4000)
    enabled: bool = True
    revision: int = Field(default=1, ge=1)

    @field_validator("name", "instructions")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


TASK_BEHAVIOR_LABELS: dict[TaskBehaviorKind, str] = {
    **TASK_LABELS,
    "reasoning": "Reasoning (connected host)",
}


def default_task_behaviors() -> list[TaskBehavior]:
    return [
        TaskBehavior(task=task, name=label, instructions="")
        for task, label in TASK_BEHAVIOR_LABELS.items()
    ]


class TaskBehaviorRegistry:
    RECORD_KEY = "task_behaviors"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[TaskBehavior]:
        record = await self.records.get(self.RECORD_KEY)
        defaults = {item.task: item for item in default_task_behaviors()}
        if record:
            for value in record.get("items", []):
                item = TaskBehavior.model_validate(value)
                defaults[item.task] = item
        return [defaults[task] for task in TASK_BEHAVIOR_LABELS]

    async def replace(self, behaviors: list[TaskBehavior]) -> list[TaskBehavior]:
        by_task = {item.task: item for item in behaviors}
        expected = set(TASK_BEHAVIOR_LABELS)
        if len(behaviors) != len(TASK_BEHAVIOR_LABELS) or set(by_task) != expected:
            raise ValueError("Task behaviors must contain exactly one profile for every supported task")
        current = {item.task: item for item in await self.list()}
        ordered: list[TaskBehavior] = []
        for task in TASK_BEHAVIOR_LABELS:
            candidate = by_task[task]
            previous = current[task]
            changed = (
                candidate.name != previous.name
                or candidate.instructions != previous.instructions
                or candidate.enabled != previous.enabled
            )
            ordered.append(candidate.model_copy(update={
                "revision": previous.revision + 1 if changed else previous.revision
            }))
        after = {"items": [item.model_dump(mode="json") for item in ordered]}
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("Task behavior registry changed concurrently; refresh and retry")
        return ordered


@dataclass(frozen=True)
class TaskExecutionContext:
    """Small handoff contract shared by stateless adapters and persistent workers."""

    task: TaskBehaviorKind
    provider: str = ""
    model: str = ""
    behavior_revision: int = 1
    session_id: str | None = None
    state_ref: str | None = None
    memory_refs: tuple[str, ...] = ()
    working_context: str = ""


class TaskRuntime(Protocol):
    """Execution seam for API-backed now and resident/self-hosted workers later."""

    async def execute(self, context: TaskExecutionContext, payload: Any) -> Any: ...


class TaskPromptAssembler:
    """Compose Mind skills, task skills, behaviors, assignment, and context."""

    def __init__(self, registry: TaskBehaviorRegistry) -> None:
        self.registry = registry

    async def system_prompt(self, context: TaskExecutionContext) -> str:
        profile = next(
            item for item in await self.registry.list() if item.task == context.task
        )
        skills = EffectiveSkillRegistry(self.registry.records)
        assignments = await TaskModelAssignmentRegistry(self.registry.records).list()
        assignment = next(item for item in assignments if item.task == context.task)
        layers = []
        if context.task == "reasoning":
            startup = await skills.startup_contract()
            if startup:
                layers.append(startup)
        task_contract = await skills.task_contract(context.task, assignment.skill_ids)
        if task_contract:
            layers.extend(([""] if layers else []) + [task_contract])
        selected = await HostBehaviorRegistry(self.registry.records).selected(context.task)
        if selected:
            layers.extend([
                "",
                f"CONFIGURABLE TASK BEHAVIOR ({profile.name}, revision {profile.revision}):",
                *[f"- [{item.id}] {item.instruction}" for item in selected],
            ])
        layers.extend([
            "",
            "CURRENT ASSIGNMENT:",
            f"Task: {context.task}",
            f"Provider: {context.provider or '(runtime-selected)'}",
            f"Model: {context.model or '(runtime-selected)'}",
            f"Behavior revision: {profile.revision}",
        ])
        if context.session_id:
            layers.append(f"Session reference: {context.session_id}")
        if context.state_ref:
            layers.append(f"Working-state reference: {context.state_ref}")
        if context.memory_refs:
            layers.append("Relevant memory references: " + ", ".join(context.memory_refs))
        if context.working_context.strip():
            layers.extend(["", "CURRENT WORKING CONTEXT:", context.working_context.strip()])
        return "\n".join(layers)
