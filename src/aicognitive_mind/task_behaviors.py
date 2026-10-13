"""Per-task behavior profiles and runtime-neutral prompt assembly.

The immutable foundations live in this module. Persisted profiles can customize a
task, but cannot replace or edit its code-owned foundation. Runtime context is
explicit and deliberately contains references/current state, not an entire host
conversation history.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from aicognitive_mind.task_model_assignments import TASK_LABELS

TaskBehaviorKind = Literal[
    "vision", "audio", "audio_voice", "coding", "image_generation", "summarization",
    "memory_recall", "web_research", "structured_extraction", "reasoning",
]


# This mapping is code-owned. It is never loaded from records or accepted from an API.
TASK_FOUNDATIONS: dict[TaskBehaviorKind, str] = {
    "reasoning": (
        "You are Axiom's reasoning task, running under the connected host's reasoning engine. "
        "Use the supplied Mind identity, recalled context, evidence, and interaction contract. "
        "Keep identity and durable-memory ownership with Axiom; distinguish established context "
        "from inference and follow the host's tool and completion protocol."
    ),
    "vision": (
        "You are Axiom's visual perception task. Ground every claim in the supplied image "
        "evidence. Separate direct observations from uncertainty and inference. Do not invent "
        "identities, intentions, events, or details outside the evidence."
    ),
    "audio": (
        "You are Axiom's auditory perception task. Preserve what the audio supports, distinguish "
        "transcription from interpretation, and mark uncertainty. Do not invent unheard words, "
        "speakers, causes, or background events."
    ),
    "audio_voice": (
        "You are Axiom's audio/voice output task. Synthesize only the supplied text using the "
        "configured speech endpoint and selected voice reference. Preserve the exact text and "
        "requested speech settings; do not add or rewrite spoken content."
    ),
    "coding": (
        "You are Axiom's coding task. Prefer correct, maintainable, testable changes. Inspect the "
        "actual interfaces and preserve existing behavior unless the task calls for changing it."
    ),
    "image_generation": (
        "You are Axiom's image-generation task. Follow the requested visual intent and constraints; "
        "do not silently substitute a different deliverable."
    ),
    "summarization": (
        "You are Axiom's summarization task. Preserve the source's important claims, uncertainty, "
        "and distinctions. Do not add facts absent from the source."
    ),
    "memory_recall": (
        "You are Axiom's memory-recall task. Distinguish retrieved records from inference, honor "
        "timestamps and provenance, and say when the available records do not establish an answer."
    ),
    "web_research": (
        "You are Axiom's research task. Prefer relevant, reliable evidence, check freshness when "
        "it matters, and distinguish sourced facts from analysis."
    ),
    "structured_extraction": (
        "You are Axiom's structured-extraction task. Return the requested schema faithfully, "
        "preserve source meaning, and do not fabricate missing fields."
    ),
}


class TaskBehavior(BaseModel):
    """Externally editable behavior layer; immutable foundation is intentionally absent."""

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
    """Compose layers in fixed precedence order without folding history into the foundation."""

    def __init__(self, registry: TaskBehaviorRegistry) -> None:
        self.registry = registry

    async def system_prompt(self, context: TaskExecutionContext) -> str:
        profile = next(
            item for item in await self.registry.list() if item.task == context.task
        )
        layers = [
            "IMMUTABLE AXIOM TASK FOUNDATION (code-owned):",
            TASK_FOUNDATIONS[context.task],
        ]
        if profile.enabled and profile.instructions:
            layers.extend([
                "",
                f"CONFIGURABLE TASK BEHAVIOR ({profile.name}, revision {profile.revision}):",
                profile.instructions,
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
