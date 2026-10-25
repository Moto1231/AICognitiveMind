"""Packaged Axiom skill defaults; runtime settings belong to EffectiveSkillRegistry."""

from __future__ import annotations

import hashlib
from importlib.resources import files


REQUIRED_SKILLS = ("axiom-continuity", "axiom-current-state")
REQUIRED_SKILL_NAMES = {
    "axiom-continuity": "Axiom Continuity",
    "axiom-current-state": "Axiom Current State",
}


def load_required_skill(slug: str) -> str:
    if slug not in REQUIRED_SKILLS:
        raise ValueError(f"Unknown required Axiom skill: {slug}")
    return files("aicognitive_mind").joinpath(f"skills/{slug}/SKILL.md").read_text(encoding="utf-8")


def required_skill_catalog() -> list[dict[str, object]]:
    """Factory metadata only. Read EffectiveSkillRegistry for an active Mind."""
    result = []
    for slug in REQUIRED_SKILLS:
        content = load_required_skill(slug)
        result.append({
            "slug": slug,
            "name": REQUIRED_SKILL_NAMES[slug],
            "content": content,
            "required": True,
            "enabled": True,
            "protected": True,
            "read_only": False,
            "source": "packaged_default",
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    return result


def compose_required_skills() -> str:
    """Factory bootstrap only; never replace saved Administrator settings with this."""
    sections = [
        "DEFAULT AXIOM STARTUP SKILLS (Administrator configurable):\n"
        "Saved effective skill text, enabled/required flags, and cognitive configuration "
        "take precedence over these package defaults. Do not reapply a disabled or "
        "edited default over an explicit Administrator setting. "
        "Both full protocols below are supplied at activation. Apply both through follow-ups, "
        "host/model changes and other connector work. They do not depend on optional task "
        "memberships or another user reminder. Apply their startup orientation and standing "
        "traits before substantive work, including evidence-grounded questions for missing context."
    ]
    sections.extend(
        f"## {REQUIRED_SKILL_NAMES[slug]}\n\n{load_required_skill(slug)}"
        for slug in REQUIRED_SKILLS
    )
    return "\n\n".join(sections)
