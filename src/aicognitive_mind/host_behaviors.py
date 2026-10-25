from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aicognitive_mind.core_skills import REQUIRED_SKILLS, REQUIRED_SKILL_NAMES
from aicognitive_mind.domain import utc_now


class BehaviorRevisionConflict(ValueError):
    """The Administrator edited a stale behavior catalog."""


class HostBehavior(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=4000)
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    protected: bool = False
    required: bool = False


DEFAULT_HOST_BEHAVIORS = (
    HostBehavior(
        id="ground-recalled-context",
        name="Ground answers in recalled context",
        instruction=(
            "Treat facts explicitly established by returned identity, recalled context, prior "
            "experience, or successful tool results as available episode context. Do not claim "
            "that such context is absent or unavailable unless newer evidence conflicts with it."
        ),
        priority=10,
        protected=True,
    ),
    HostBehavior(
        id="verify-capabilities",
        name="Verify capabilities before denying access",
        instruction=(
            "Before claiming an Axiom capability is unavailable, inspect the capabilities exposed "
            "to the active host and use the relevant read/status operation when available."
        ),
        priority=20,
        protected=True,
    ),
)


REQUIRED_HOST_BEHAVIORS = tuple(
    HostBehavior(
        id=slug, name=REQUIRED_SKILL_NAMES[slug],
        instruction=(
            f"{REQUIRED_SKILL_NAMES[slug]} follows the effective Mind skill configuration "
            "chosen by the Administrator. Saved skill, behavior and task settings take "
            "precedence over package defaults."
        ),
        priority=index, protected=True, required=True,
    )
    for index, slug in enumerate(REQUIRED_SKILLS)
)


class HostBehaviorRegistry:
    RECORD_KEY = "host_behaviors"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[HostBehavior]:
        return (await self.snapshot())[0]

    async def snapshot(self) -> tuple[list[HostBehavior], int]:
        record = await self.records.get(self.RECORD_KEY)
        items = (
            [HostBehavior.model_validate(item) for item in record.get("items", [])]
            if record is not None else [item.model_copy(deep=True) for item in (
                *REQUIRED_HOST_BEHAVIORS, *DEFAULT_HOST_BEHAVIORS,
            )]
        )
        revision = (record or {}).get("revision", 0)
        if record and record.get("task_profiles_migrated"):
            return items, revision
        # Promote the former inline task instructions into the shared catalog
        # without mutating storage on a read. The next catalog save persists them.
        # Once a task has explicit memberships, removing the legacy catalog item
        # must not cause it to reappear from its old profile.
        profiles = await self.records.get("task_behaviors")
        assignments = await self.records.get("task_model_assignments")
        assigned = {
            value.get("task"): value.get("behavior_ids")
            for value in (assignments or {}).get("items", [])
        }
        ids = {item.id for item in items}
        for profile in (profiles or {}).get("items", []):
            task = profile.get("task")
            instruction = str(profile.get("instructions", "")).strip()
            behavior_id = f"task-{task}-legacy"
            if not instruction or assigned.get(task) is not None or behavior_id in ids:
                continue
            items.append(HostBehavior(
                id=behavior_id,
                name=str(profile.get("name") or task),
                instruction=instruction,
                enabled=bool(profile.get("enabled", True)),
                priority=200,
            ))
            ids.add(behavior_id)
        return items, revision

    async def replace(
        self, behaviors: list[HostBehavior], *, expected_revision: int | None = None,
    ) -> list[HostBehavior]:
        if len({item.id for item in behaviors}) != len(behaviors):
            raise ValueError("Behavior IDs must be unique")
        before = await self.records.get(self.RECORD_KEY)
        revision = (before or {}).get("revision", 0)
        if expected_revision is not None and expected_revision != revision:
            raise BehaviorRevisionConflict("Behavior catalog changed; refresh before saving.")
        ordered = sorted(behaviors, key=lambda item: (item.priority, item.id))
        after = {
            "items": [item.model_dump(mode="json") for item in ordered],
            "task_profiles_migrated": True,
            "revision": revision + 1, "updated_by": "administrator", "updated_at": utc_now().isoformat(),
        }
        if before is None:
            try:
                await self.records.create(self.RECORD_KEY, after)
            except Exception as exc:
                # Backends expose different duplicate-create exceptions. Only
                # a confirmed competing record converts the failure to a
                # revision conflict; genuine storage failures stay visible.
                if await self.records.get(self.RECORD_KEY) is not None:
                    raise BehaviorRevisionConflict("Host behavior registry changed; refresh before saving.") from exc
                raise
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise BehaviorRevisionConflict("Host behavior registry changed; refresh before saving.")
        return ordered

    async def selected(self, task: str) -> list[HostBehavior]:
        assignments = await self.records.get("task_model_assignments")
        saved = next((item for item in (assignments or {}).get("items", [])
                      if item.get("task") == task), {})
        membership = saved.get("behavior_ids")
        catalog = await self.list()
        if membership is None:
            selected = (
                {item.id for item in catalog if not item.id.startswith("task-")}
                if task == "reasoning" else set()
            )
            selected.add(f"task-{task}-legacy")
        else:
            selected = set(membership)
        return [item for item in catalog if item.enabled and item.id in selected]

    async def compose(self, core_contract: str, *, task: str = "reasoning") -> str:
        enabled = await self.selected(task)
        if not enabled:
            return core_contract
        lines = ["", "Configured host behaviors:"]
        lines.extend(f"- [{item.id}] {item.instruction}" for item in enabled)
        return core_contract + "\n" + "\n".join(lines)
