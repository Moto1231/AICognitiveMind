"""Canonical required Axiom protocols shared by runtime, Administration and plugins."""

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
    result = []
    for slug in REQUIRED_SKILLS:
        content = load_required_skill(slug)
        result.append({
            "slug": slug,
            "name": REQUIRED_SKILL_NAMES[slug],
            "content": content,
            "required": True,
            "read_only": True,
            "source": "packaged_core",
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        })
    return result


def compose_required_skills() -> str:
    sections = [
        "REQUIRED AXIOM SKILLS (code-owned; active for every Axiom interaction):\n"
        "Both full protocols below are supplied at activation. Apply both through follow-ups, "
        "host/model changes and other connector work. They do not depend on optional task "
        "memberships or another user reminder."
    ]
    sections.extend(
        f"## {REQUIRED_SKILL_NAMES[slug]}\n\n{load_required_skill(slug)}"
        for slug in REQUIRED_SKILLS
    )
    return "\n\n".join(sections)
