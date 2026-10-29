from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


TaskKind = Literal[
    "reasoning",
    "vision",
    "audio",
    "audio_voice",
    "coding",
    "image_generation",
    "summarization",
    "memory_recall",
    "web_research",
    "structured_extraction",
]

TASK_LABELS: dict[TaskKind, str] = {
    "reasoning": "Reasoning (connected host)",
    "vision": "Vision",
    "audio": "Audio & Transcription",
    "audio_voice": "Audio / Voice (Fish Audio)",
    "coding": "Coding",
    "image_generation": "Drawing & Image Generation",
    "summarization": "Summarizing",
    "memory_recall": "Memory Recall",
    "web_research": "Web Research",
    "structured_extraction": "Structured Extraction",
}


class TaskFallbackAssignment(BaseModel):
    provider: str = Field(default="", max_length=120)
    model: str = Field(default="", max_length=160)

    @field_validator("provider", "model")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()


class TaskModelAssignment(BaseModel):
    task: TaskKind
    provider: str = Field(default="", max_length=120)
    model: str = Field(default="", max_length=160)
    fallbacks: list[TaskFallbackAssignment] = Field(default_factory=list)
    provider_rotation: Literal["ordered", "daily_round_robin"] = "ordered"
    voice_reference_id: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=500)
    # None preserves membership from configurations predating the shared catalog.
    # An explicit empty list means no optional catalog behaviors are selected.
    behavior_ids: list[str] | None = Field(default=None, max_length=500)
    # Required task skills come from the Skills catalog. This list contains
    # only optional skills, in Administrator-selected execution order.
    skill_ids: list[str] | None = Field(default=None, max_length=500)

    @field_validator("provider", "model", "voice_reference_id", "notes")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("behavior_ids", "skill_ids")
    @classmethod
    def clean_behavior_ids(cls, values: list[str] | None) -> list[str] | None:
        return None if values is None else list(dict.fromkeys(value.strip() for value in values if value.strip()))


def default_task_assignments() -> list[TaskModelAssignment]:
    return [TaskModelAssignment(task=task) for task in TASK_LABELS]


class TaskModelAssignmentRegistry:
    RECORD_KEY = "task_model_assignments"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[TaskModelAssignment]:
        record = await self.records.get(self.RECORD_KEY)
        by_task = {}
        for value in (record or {}).get("items", []):
            normalized = dict(value)
            # Preserve the former single fallback as the first entry in the new chain.
            if "fallbacks" not in normalized:
                provider = str(normalized.pop("fallback_provider", "") or "").strip()
                model = str(normalized.pop("fallback_model", "") or "").strip()
                normalized["fallbacks"] = ([{"provider": provider, "model": model}]
                                           if provider and model else [])
            else:
                normalized.pop("fallback_provider", None)
                normalized.pop("fallback_model", None)
            item = TaskModelAssignment.model_validate(normalized)
            by_task[item.task] = item
        # Keep newly introduced task kinds visible when older saved configurations exist.
        ordered = [
            by_task.get(task, TaskModelAssignment(task=task))
            for task in TASK_LABELS
        ]
        # Host registration supplies the actual reasoning host/model. This is a
        # queue destination, not a fabricated HTTP endpoint or provider credential.
        host = await self.records.get("active_host")
        if host:
            reasoning = next(item for item in ordered if item.task == "reasoning")
            if not reasoning.provider or reasoning.provider == "connected-host":
                reasoning.provider = "connected-host"
                reasoning.model = str(host.get("model", ""))
        from aicognitive_mind.host_behaviors import HostBehaviorRegistry

        catalog = await HostBehaviorRegistry(self.records).list()
        catalog_ids = {behavior.id for behavior in catalog}
        for item in ordered:
            if item.behavior_ids is None:
                item.behavior_ids = [behavior.id for behavior in catalog if (
                    behavior.id == f"task-{item.task}-legacy"
                    or (item.task == "reasoning" and not behavior.id.startswith("task-"))
                )]
            else:
                item.behavior_ids = [value for value in item.behavior_ids if value in catalog_ids]
        from aicognitive_mind.effective_skills import EffectiveSkillRegistry

        assignable_skill_ids = {
            skill["slug"] for skill in await EffectiveSkillRegistry(self.records).list()
            if not skill["required"] and not skill["required_tasks"]
        }
        for item in ordered:
            if item.skill_ids is None:
                item.skill_ids = []
            else:
                item.skill_ids = [value for value in item.skill_ids if value in assignable_skill_ids]
        return ordered

    async def replace(
        self, assignments: list[TaskModelAssignment]
    ) -> list[TaskModelAssignment]:
        by_task = {item.task: item for item in assignments}
        expected = set(TASK_LABELS)
        if len(assignments) != len(TASK_LABELS) or set(by_task) != expected:
            missing = sorted(expected - set(by_task))
            unknown = sorted(set(by_task) - expected)
            detail = []
            if missing:
                detail.append("missing tasks: " + ", ".join(missing))
            if unknown:
                detail.append("unsupported tasks: " + ", ".join(unknown))
            if len(assignments) != len(by_task):
                detail.append("duplicate task entries")
            raise ValueError("Invalid task assignments (" + "; ".join(detail) + ")")
        ordered = [by_task[task] for task in TASK_LABELS]
        from aicognitive_mind.host_behaviors import HostBehaviorRegistry

        catalog = {item.id: item for item in await HostBehaviorRegistry(self.records).list()}
        from aicognitive_mind.effective_skills import EffectiveSkillRegistry

        assignable_skill_ids = {
            skill["slug"] for skill in await EffectiveSkillRegistry(self.records).list()
            if not skill["required"] and not skill["required_tasks"]
        }
        current = {item.task: item for item in await self.list()}
        for item in ordered:
            if item.behavior_ids is None:
                item.behavior_ids = current[item.task].behavior_ids
            if item.skill_ids is None:
                item.skill_ids = current[item.task].skill_ids
            previous = current[item.task]
            # The endpoint-only editor must not erase a working legacy model
            # while its existing endpoint has not yet selected a bound model.
            if not item.model and item.provider and item.provider.casefold() == previous.provider.casefold():
                item.model = previous.model
            for fallback in item.fallbacks:
                if fallback.model:
                    continue
                old = next((value for value in previous.fallbacks
                            if value.provider.casefold() == fallback.provider.casefold()), None)
                if old:
                    fallback.model = old.model
            unknown = set(item.behavior_ids or []) - set(catalog)
            if unknown:
                raise ValueError("Unknown behavior IDs: " + ", ".join(sorted(unknown)))
            unknown_skills = set(item.skill_ids or []) - assignable_skill_ids
            if unknown_skills:
                raise ValueError(
                    "Unknown or non-assignable skill IDs: " + ", ".join(sorted(unknown_skills))
                )
        # Materialize promoted inline instructions before explicit memberships
        # replace their old implicit selection. No task loses its existing text.
        catalog_before = await self.records.get("host_behaviors")
        stored_ids = {item.get("id") for item in (catalog_before or {}).get("items", [])}
        if any(item.id.startswith("task-") and item.id not in stored_ids for item in catalog.values()):
            await HostBehaviorRegistry(self.records).replace(list(catalog.values()))
        after = {"items": [item.model_dump(mode="json") for item in ordered]}
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("Task assignments changed concurrently; refresh and retry")
        return ordered
