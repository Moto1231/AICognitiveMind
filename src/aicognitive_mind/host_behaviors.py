from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HostBehavior(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=4000)
    enabled: bool = True
    priority: int = Field(default=100, ge=0, le=10000)
    protected: bool = False


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


class HostBehaviorRegistry:
    RECORD_KEY = "host_behaviors"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[HostBehavior]:
        record = await self.records.get(self.RECORD_KEY)
        if not record:
            return list(DEFAULT_HOST_BEHAVIORS)
        return [HostBehavior.model_validate(item) for item in record.get("items", [])]

    async def replace(self, behaviors: list[HostBehavior]) -> list[HostBehavior]:
        current = await self.list()
        protected = {item.id: item for item in current if item.protected}
        incoming = {item.id: item for item in behaviors}
        for behavior_id, original in protected.items():
            candidate = incoming.get(behavior_id)
            if candidate is None or not candidate.enabled or candidate.instruction != original.instruction:
                raise ValueError(f"Protected host behavior cannot be removed, disabled, or rewritten: {behavior_id}")
            if not candidate.protected:
                raise ValueError(f"Protected host behavior cannot be unprotected: {behavior_id}")
        ordered = sorted(behaviors, key=lambda item: (item.priority, item.id))
        after = {"items": [item.model_dump(mode="json") for item in ordered]}
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("Host behavior registry changed concurrently; refresh and retry")
        return ordered

    async def compose(self, core_contract: str) -> str:
        enabled = [item for item in await self.list() if item.enabled]
        if not enabled:
            return core_contract
        lines = ["", "Configured host behaviors:"]
        lines.extend(f"- [{item.id}] {item.instruction}" for item in enabled)
        return core_contract + "\n" + "\n".join(lines)
