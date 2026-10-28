"""Mind-scoped Administrator settings for The Breaker.

The effective settings are revisioned independently from cognitive content.  A
bounded operational snapshot binds one revision to each interaction key so an
Administrator edit made mid-turn cannot change that turn's persistence policy.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.domain import utc_now


class ContinuitySettingsConflict(CommitConflict):
    """The Administrator edited a settings revision that is no longer current."""


class ContinuitySettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consecutive_failure_limit: int = Field(default=5, ge=1, le=20, strict=True)
    rolling_failure_limit: int = Field(default=35, ge=1, le=500, strict=True)
    rolling_window_size: int = Field(default=100, ge=20, le=500, strict=True)
    provider_request_timeout_seconds: float = Field(default=30, ge=1, le=120)
    steward_assessment_timeout_seconds: float = Field(default=60, ge=5, le=300)
    rate_limit_retry_wait_cap_seconds: float = Field(default=45, ge=0, le=120)

    @model_validator(mode="after")
    def validate_thresholds(self) -> ContinuitySettings:
        if self.rolling_failure_limit < self.consecutive_failure_limit:
            raise ValueError("rolling_failure_limit must be at least consecutive_failure_limit")
        if self.rolling_failure_limit > self.rolling_window_size:
            raise ValueError("rolling_failure_limit cannot exceed rolling_window_size")
        return self


class ContinuitySettingsRegistry:
    RECORD_KEY = "continuity_settings"
    SNAPSHOT_KEY = "continuity_settings_interactions"
    SNAPSHOT_LIMIT = 500
    EDITABLE_FIELDS = frozenset(ContinuitySettings.model_fields)

    def __init__(self, records: Any) -> None:
        self.records = records

    @staticmethod
    def defaults() -> dict[str, int | float]:
        return ContinuitySettings().model_dump(mode="json")

    @classmethod
    def _snapshot(cls, record: dict[str, Any] | None) -> dict[str, Any]:
        values = cls.defaults() | {
            key: value for key, value in (record or {}).items() if key in cls.EDITABLE_FIELDS
        }
        settings = ContinuitySettings.model_validate(values)
        return {
            "revision": (record or {}).get("revision", 0),
            **settings.model_dump(mode="json"),
            "defaults": cls.defaults(),
            "source": "administrator_override" if record else "packaged_default",
            "updated_by": (record or {}).get("updated_by"),
            "updated_at": (record or {}).get("updated_at"),
        }

    async def effective(self) -> dict[str, Any]:
        return self._snapshot(await self.records.get(self.RECORD_KEY))

    async def save(self, changes: dict[str, Any], *, expected_revision: int) -> dict[str, Any]:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a nonnegative integer")
        unknown = set(changes) - self.EDITABLE_FIELDS
        if unknown:
            raise ValueError("Unsupported continuity settings: " + ", ".join(sorted(unknown)))
        before = await self.records.get(self.RECORD_KEY)
        revision = (before or {}).get("revision", 0)
        if revision != expected_revision:
            raise ContinuitySettingsConflict("The Breaker settings changed; refresh before saving")
        effective = self._snapshot(before)
        values = {key: effective[key] for key in self.EDITABLE_FIELDS} | changes
        validated = ContinuitySettings.model_validate(values).model_dump(mode="json")
        if all(effective[key] == validated[key] for key in self.EDITABLE_FIELDS):
            return effective
        after = {
            **validated,
            "revision": revision + 1,
            "updated_by": "administrator",
            "updated_at": utc_now().isoformat(),
        }
        if before is None:
            try:
                await self.records.create(self.RECORD_KEY, after)
            except Exception as exc:
                if await self.records.get(self.RECORD_KEY) is not None:
                    raise ContinuitySettingsConflict(
                        "The Breaker settings changed; refresh before saving"
                    ) from exc
                raise
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise ContinuitySettingsConflict("The Breaker settings changed; refresh before saving")
        return self._snapshot(after)

    async def capture(self, interaction_id: str) -> dict[str, Any]:
        if not isinstance(interaction_id, str) or not interaction_id:
            raise ValueError("interaction_id must be a nonblank string")
        settings = await self.effective()
        captured = {
            "interaction_id": interaction_id,
            "captured_at": utc_now().isoformat(),
            **{key: settings[key] for key in ("revision", *self.EDITABLE_FIELDS)},
        }
        for _ in range(8):
            current = await self.records.get(self.SNAPSHOT_KEY)
            base = deepcopy(current or {"kind": self.SNAPSHOT_KEY, "items": []})
            items = [
                item for item in base.get("items", [])
                if item.get("interaction_id") != interaction_id
            ]
            items.append(captured)
            updated = {**base, "items": items[-self.SNAPSHOT_LIMIT:]}
            if current is None:
                try:
                    await self.records.create(self.SNAPSHOT_KEY, updated)
                except Exception:
                    if await self.records.get(self.SNAPSHOT_KEY) is not None:
                        continue
                    raise
                return self._captured_snapshot(captured)
            if await self.records.replace(self.SNAPSHOT_KEY, current, updated):
                return self._captured_snapshot(captured)
        raise CommitConflict("Interaction continuity settings changed concurrently; retry")

    async def for_interaction(self, interaction_id: str) -> dict[str, Any]:
        record = await self.records.get(self.SNAPSHOT_KEY) or {}
        captured = next(
            (
                item for item in reversed(record.get("items", []))
                if item.get("interaction_id") == interaction_id
            ),
            None,
        )
        return self._captured_snapshot(captured) if captured else await self.effective()

    @classmethod
    def _captured_snapshot(cls, captured: dict[str, Any]) -> dict[str, Any]:
        settings = ContinuitySettings.model_validate({
            key: captured[key] for key in cls.EDITABLE_FIELDS
        })
        return {
            "revision": captured.get("revision", 0),
            **settings.model_dump(mode="json"),
            "source": "interaction_snapshot",
            "captured_at": captured.get("captured_at"),
        }
