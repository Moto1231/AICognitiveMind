"""Mind-scoped Administrator overrides for cognitive contract and task foundations."""

from __future__ import annotations

from copy import deepcopy
from importlib.resources import files
import json
from typing import Any

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.domain import utc_now


class CognitiveConfigurationConflict(CommitConflict):
    """The Administrator edited a configuration revision that is no longer current."""


FUNCTION_IDS = ("current_state", "recall", "save", "sleep")
SLEEP_DEFAULTS = {
    "minimum_pattern_memories": 2,
    "minimum_journal_occurrences": 3,
    "max_patterns": 12,
}


def steward_instruction_parts(text: str) -> tuple[str, str, str]:
    common, before, tail = text.partition("## Before reasoning")
    recall, after, tail = tail.partition("## After reasoning")
    save, protocol, tail = tail.partition("## Protocol")
    if not (before and after and protocol):
        return text, "", ""
    return common.rstrip() + "\n\n" + protocol + tail, (before + recall).strip(), (after + save).strip()


def function_defaults() -> dict[str, str]:
    from aicognitive_mind.core_skills import load_required_skill

    steward = files("aicognitive_mind").joinpath("skills/memory-steward/SKILL.md").read_text()
    _, recall, save = steward_instruction_parts(steward)
    return {
        "current_state": load_required_skill("axiom-current-state"),
        "recall": recall,
        "save": save,
        "sleep": json.dumps(SLEEP_DEFAULTS, indent=2),
    }


def sleep_function_settings(value: str) -> dict[str, int]:
    try:
        settings = json.loads(value)
    except (ValueError, TypeError) as exc:
        raise ValueError("Sleep rules must be a JSON object with all three parameters") from exc
    if not isinstance(settings, dict) or settings.keys() != SLEEP_DEFAULTS.keys():
        raise ValueError("Sleep rules must contain exactly: " + ", ".join(SLEEP_DEFAULTS))
    if any(type(number) is not int or not 1 <= number <= 1000 for number in settings.values()):
        raise ValueError("Sleep parameters must be integers from 1 to 1000")
    return settings


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
        "functions": function_defaults(),
    }


class CognitiveConfigurationRegistry:
    RECORD_KEY = "cognitive_configuration"
    EDITABLE_FIELDS = frozenset({"base_contract", "startup_instructions", "task_foundations", "functions"})
    MAX_TEXT_LENGTH = 200_000

    def __init__(self, records: Any) -> None:
        self.records = records

    async def effective(self, *, include_legacy_functions: bool = False) -> dict[str, Any]:
        record = await self.records.get(self.RECORD_KEY)
        snapshot = self._snapshot(record)
        return await self._with_legacy_functions(snapshot) if include_legacy_functions else snapshot

    async def _with_legacy_functions(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Read existing admin overrides without rewriting any saved records."""
        from aicognitive_mind.effective_skills import EffectiveSkillRegistry

        registry = EffectiveSkillRegistry(self.records)
        items = {item["slug"]: item for item in await registry.list() if item["source"] == "mind_override"}
        fallback = {}
        if ledger := items.get("axiom-current-state"):
            fallback["current_state"] = ledger["content"] if ledger["enabled"] else ""
        if steward := items.get("memory-steward"):
            _, recall, save = steward_instruction_parts(steward["content"])
            fallback.update(recall=recall if steward["enabled"] else "",
                            save=save if steward["enabled"] else "")
        snapshot["functions"].update(
            {key: value for key, value in fallback.items() if key not in snapshot["function_overrides"]}
        )
        return snapshot

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
            "functions": {**defaults["functions"], **overrides.get("functions", {})},
            "function_overrides": list(overrides.get("functions", {})),
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
            elif key == "functions":
                if not isinstance(value, dict) or set(value) - set(FUNCTION_IDS):
                    raise ValueError("Functions must use supported IDs")
                if "sleep" in value:
                    sleep_function_settings(value["sleep"])
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
            after[key] = ({**after.get(key, {}), **value} if key in {"task_foundations", "functions"} else value)
        if after == (before or {}):
            return await self._with_legacy_functions(self._snapshot(before))
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
        return await self._with_legacy_functions(self._snapshot(after))
