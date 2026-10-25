"""Administrator-owned skill settings, scoped to the active Mind's runtime records."""

from __future__ import annotations

import hashlib
from importlib.resources import files
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.core_skills import REQUIRED_SKILLS, REQUIRED_SKILL_NAMES
from aicognitive_mind.domain import utc_now


class SkillRevisionConflict(ValueError):
    """The Administrator edited a stale skill revision."""


class SkillConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=120)
    content: str = Field(default="", max_length=200000)
    enabled: bool = True
    required: bool = False
    protected: bool = False


def packaged_skill_defaults() -> list[dict[str, Any]]:
    result = []
    directory = files("aicognitive_mind").joinpath("skills")
    for folder in sorted(directory.iterdir(), key=lambda value: value.name):
        skill = folder.joinpath("SKILL.md")
        if not folder.is_dir() or not skill.is_file():
            continue
        slug = folder.name
        config = SkillConfiguration(
            slug=slug, name=REQUIRED_SKILL_NAMES.get(slug, slug.replace("-", " ").title()),
            content=skill.read_text(encoding="utf-8"),
            required=slug in REQUIRED_SKILLS,
            protected=slug in REQUIRED_SKILLS,
        )
        result.append(config.model_dump())
    return sorted(result, key=lambda item: (
        REQUIRED_SKILLS.index(item["slug"]) if item["slug"] in REQUIRED_SKILLS else len(REQUIRED_SKILLS),
        item["slug"],
    ))


class EffectiveSkillRegistry:
    RECORD_KEY = "effective_skill_overrides"

    def __init__(self, records: Any) -> None:
        self.records = records

    @staticmethod
    def _view(config: dict[str, Any], *, revision: int, source: str, **metadata: Any) -> dict[str, Any]:
        return {
            **config, "revision": revision, "source": source, "read_only": False,
            "sha256": hashlib.sha256(config["content"].encode("utf-8")).hexdigest(),
            **metadata,
        }

    def _effective(self, record: dict[str, Any] | None) -> list[dict[str, Any]]:
        items = {item["slug"]: self._view(item, revision=0, source="packaged_default")
                 for item in packaged_skill_defaults()}
        for saved in (record or {}).get("items", []):
            config = SkillConfiguration.model_validate({
                key: value for key, value in saved.items() if key in SkillConfiguration.model_fields
            }).model_dump()
            items[config["slug"]] = self._view(
                config, revision=saved["revision"], source="mind_override",
                updated_by=saved.get("updated_by"), updated_at=saved.get("updated_at"),
            )
        return list(items.values())

    async def list(self) -> list[dict[str, Any]]:
        return self._effective(await self.records.get(self.RECORD_KEY))

    async def get(self, slug: str) -> dict[str, Any] | None:
        return next((item for item in await self.list() if item["slug"] == slug), None)

    async def startup_contract(self) -> str:
        active = [item for item in await self.list() if item["enabled"] and item["required"]]
        if not active:
            return ""
        return "\n\n".join([
            "Effective Administrator startup skills (saved Mind settings take precedence over package defaults):",
            *(f"## {item['name']} ({item['slug']})\n\n{item['content']}" for item in active),
        ])

    async def save(
        self, slug: str, changes: dict[str, Any], *, expected_revision: int,
    ) -> dict[str, Any]:
        if type(expected_revision) is not int or expected_revision < 0:
            raise SkillRevisionConflict("Refresh the skill configuration before saving.")
        before = await self.records.get(self.RECORD_KEY)
        current = next((item for item in self._effective(before) if item["slug"] == slug), None)
        if expected_revision != (current["revision"] if current else 0):
            raise SkillRevisionConflict("Skill configuration changed; refresh before saving.")
        previous = {key: value for key, value in (current or {}).items()
                    if key in SkillConfiguration.model_fields}
        config = SkillConfiguration.model_validate({**previous, **changes, "slug": slug}).model_dump()
        saved = {
            **config, "revision": expected_revision + 1,
            "updated_by": "administrator", "updated_at": utc_now().isoformat(),
        }
        after = {
            "items": [item for item in (before or {}).get("items", []) if item["slug"] != slug] + [saved],
            "revision": (before or {}).get("revision", 0) + 1,
            "updated_by": saved["updated_by"], "updated_at": saved["updated_at"],
        }
        if before is None:
            try:
                await self.records.create(self.RECORD_KEY, after)
            except Exception as exc:
                # Duplicate-create errors vary by storage provider. Convert
                # only a confirmed competing save into a revision conflict.
                if await self.records.get(self.RECORD_KEY) is not None:
                    raise SkillRevisionConflict("Skill configuration changed; refresh before saving.") from exc
                raise
        else:
            try:
                replaced = await self.records.replace(self.RECORD_KEY, before, after)
            except CommitConflict as exc:
                raise SkillRevisionConflict("Skill configuration changed; refresh before saving.") from exc
            if not replaced:
                raise SkillRevisionConflict("Skill configuration changed; refresh before saving.")
        return self._view(saved, revision=saved["revision"], source="mind_override")
