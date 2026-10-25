from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aicognitive_mind.core_skills import REQUIRED_SKILLS, REQUIRED_SKILL_NAMES


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
            f"{REQUIRED_SKILL_NAMES[slug]} is required for every Axiom reasoning interaction. "
            "Apply its full packaged protocol supplied in the mandatory reasoning contract, "
            "including fresh instances and follow-ups. Optional task memberships cannot disable it."
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
        record = await self.records.get(self.RECORD_KEY)
        items = (
            [HostBehavior.model_validate(item) for item in record.get("items", [])
             if item.get("id") not in REQUIRED_SKILLS]
            if record else [item.model_copy(deep=True) for item in DEFAULT_HOST_BEHAVIORS]
        )
        # Required protocols come from the installed package, including when an
        # older or tampered saved catalog omits, disables or rewrites their rows.
        # Preserve every other record and leave storage unchanged on this read.
        items = [*(item.model_copy(deep=True) for item in REQUIRED_HOST_BEHAVIORS), *items]
        if record and record.get("task_profiles_migrated"):
            return items
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
        return items

    async def replace(self, behaviors: list[HostBehavior]) -> list[HostBehavior]:
        current = await self.list()
        if len({item.id for item in behaviors}) != len(behaviors):
            raise ValueError("Behavior IDs must be unique")
        protected = {item.id: item for item in current if item.protected}
        incoming = {item.id: item for item in behaviors}
        for behavior_id, original in protected.items():
            candidate = incoming.get(behavior_id)
            if behavior_id in REQUIRED_SKILLS and candidate != original:
                raise ValueError(f"Required Axiom behavior cannot be changed: {behavior_id}")
            if candidate is None or not candidate.enabled or candidate.instruction != original.instruction:
                raise ValueError(f"Protected host behavior cannot be removed, disabled, or rewritten: {behavior_id}")
            if not candidate.protected:
                raise ValueError(f"Protected host behavior cannot be unprotected: {behavior_id}")
        ordered = sorted(behaviors, key=lambda item: (item.priority, item.id))
        after = {
            "items": [item.model_dump(mode="json") for item in ordered],
            "task_profiles_migrated": True,
        }
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("Host behavior registry changed concurrently; refresh and retry")
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
        return [item for item in catalog if item.enabled and (
            item.id in selected or (task == "reasoning" and item.protected)
        )]

    async def compose(self, core_contract: str, *, task: str = "reasoning") -> str:
        enabled = await self.selected(task)
        if not enabled:
            return core_contract
        lines = ["", "Configured host behaviors:"]
        lines.extend(f"- [{item.id}] {item.instruction}" for item in enabled)
        return core_contract + "\n" + "\n".join(lines)
