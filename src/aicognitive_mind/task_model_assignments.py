from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


TaskKind = Literal[
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
    provider: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=160)

    @field_validator("provider", "model")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()


class TaskModelAssignment(BaseModel):
    task: TaskKind
    provider: str = Field(default="", max_length=80)
    model: str = Field(default="", max_length=160)
    fallbacks: list[TaskFallbackAssignment] = Field(default_factory=list)
    voice_reference_id: str = Field(default="", max_length=200)
    notes: str = Field(default="", max_length=500)

    @field_validator("provider", "model", "voice_reference_id", "notes")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()


def default_task_assignments() -> list[TaskModelAssignment]:
    return [TaskModelAssignment(task=task) for task in TASK_LABELS]


class TaskModelAssignmentRegistry:
    RECORD_KEY = "task_model_assignments"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[TaskModelAssignment]:
        record = await self.records.get(self.RECORD_KEY)
        if not record:
            return default_task_assignments()
        by_task = {}
        for value in record.get("items", []):
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
        return [
            by_task.get(task, TaskModelAssignment(task=task))
            for task in TASK_LABELS
        ]

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
        after = {"items": [item.model_dump(mode="json") for item in ordered]}
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("Task assignments changed concurrently; refresh and retry")
        return ordered
