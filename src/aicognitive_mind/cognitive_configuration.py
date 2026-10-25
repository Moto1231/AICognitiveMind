"""Mind-scoped Administrator overrides for cognitive contract and task foundations."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.domain import utc_now


class CognitiveConfigurationConflict(CommitConflict):
    """The Administrator edited a configuration revision that is no longer current."""


def cognitive_configuration_defaults() -> dict[str, Any]:
    # Lazy imports avoid coupling the task foundation declarations to their reader.
    from aicognitive_mind.prompts import (
        CONSCIOUS_WORKSPACE_SYSTEM_PROMPT,
        DEFAULT_STARTUP_INSTRUCTIONS,
    )
    from aicognitive_mind.task_behaviors import TASK_FOUNDATIONS

    return {
        "base_contract": CONSCIOUS_WORKSPACE_SYSTEM_PROMPT,
        "startup_instructions": DEFAULT_STARTUP_INSTRUCTIONS,
        "task_foundations": dict(TASK_FOUNDATIONS),
    }


class CognitiveConfigurationRegistry:
    RECORD_KEY = "cognitive_configuration"
    EDITABLE_FIELDS = frozenset({"base_contract", "startup_instructions", "task_foundations"})
    MAX_TEXT_LENGTH = 200_000

    def __init__(self, records: Any) -> None:
        self.records = records

    async def effective(self) -> dict[str, Any]:
        record = await self.records.get(self.RECORD_KEY)
        return self._snapshot(record)

    @staticmethod
    def _snapshot(record: dict[str, Any] | None) -> dict[str, Any]:
        defaults = cognitive_configuration_defaults()
        overrides = record or {}
        foundations = {**defaults["task_foundations"], **overrides.get("task_foundations", {})}
        return {
            "revision": overrides.get("revision", 0),
            "base_contract": overrides.get("base_contract", defaults["base_contract"]),
            "startup_instructions": overrides.get("startup_instructions", defaults["startup_instructions"]),
            "task_foundations": foundations,
            "defaults": defaults,
            "source": "administrator_override" if record else "packaged_default",
            "updated_by": overrides.get("updated_by"),
            "updated_at": overrides.get("updated_at"),
        }

    async def save(self, changes: dict[str, Any], *, expected_revision: int) -> dict[str, Any]:
        if type(expected_revision) is not int or expected_revision < 0:
            raise ValueError("expected_revision must be a nonnegative integer")
        unknown = set(changes) - self.EDITABLE_FIELDS
        if unknown:
            raise ValueError("Unsupported cognitive configuration fields: " + ", ".join(sorted(unknown)))
        defaults = cognitive_configuration_defaults()
        for key, value in changes.items():
            if key == "task_foundations":
                if not isinstance(value, dict) or set(value) - set(defaults["task_foundations"]):
                    raise ValueError("Task foundations must use supported task IDs")
                texts = value.values()
            else:
                texts = (value,)
            if any(not isinstance(text, str) or len(text) > self.MAX_TEXT_LENGTH for text in texts):
                raise ValueError(f"{key} must contain text of at most {self.MAX_TEXT_LENGTH} characters")
        before = await self.records.get(self.RECORD_KEY)
        revision = (before or {}).get("revision", 0)
        if revision != expected_revision:
            raise CognitiveConfigurationConflict("Cognitive configuration changed; refresh before saving")
        after = deepcopy(before or {})
        for key, value in changes.items():
            after[key] = ({**after.get(key, {}), **value} if key == "task_foundations" else value)
        if after == (before or {}):
            return self._snapshot(before)
        after.update(
            revision=revision + 1, updated_by="administrator", updated_at=utc_now().isoformat(),
        )
        if before is None:
            try:
                await self.records.create(self.RECORD_KEY, after)
            except Exception as exc:
                # Duplicate creation is a stale revision, including backends that
                # expose a provider-specific duplicate-record exception.
                if await self.records.get(self.RECORD_KEY) is not None:
                    raise CognitiveConfigurationConflict(
                        "Cognitive configuration changed; refresh before saving"
                    ) from exc
                raise
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise CognitiveConfigurationConflict("Cognitive configuration changed; refresh before saving")
        return self._snapshot(after)
