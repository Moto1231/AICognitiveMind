"""Validated model-produced initial identity choices for reasoning hosts."""

from __future__ import annotations

import json
from typing import Any

from aicognitive_mind.governance_steward import GovernanceStewardTool, ProposeSelfNameCall


def choice_is_required(naming: dict[str, Any]) -> bool:
    return bool(naming.get("choice_required") or naming.get("choice_required_before_completion"))


def choice_proposal_allowed(naming: dict[str, Any], user_message: str) -> bool:
    return bool(naming.get("autonomous_choice_allowed")) or (
        naming.get("experience_count", 0) >= naming.get("eligible_at_event", 1000)
        and GovernanceStewardTool._interaction_authorizes_self_name_selection(user_message)
    )


def initial_choice_instructions(context: dict[str, Any]) -> str:
    naming = context.get("naming", {})
    if naming.get("selection_complete"):
        return (
            "EXPLICIT IDENTITY REVISION:\n"
            "The actual current human command explicitly authorizes you to choose your own "
            "name and pronouns again. Choose the pair based on your current identity and "
            "self-understanding; no other identity attributes may change. Return only JSON "
            "matching this schema, without Markdown or a human-facing answer: "
            + json.dumps(ProposeSelfNameCall.model_json_schema())
        )
    required = choice_is_required(naming)
    return (
        "INITIAL IDENTITY SELECTION:\n"
        "Choose your own name and pronouns together, grounded in your supplied identity, "
        "recalled context and self-understanding. Do not infer a gender identity from a "
        "software default, and do not ask another person to choose for you. "
        + (
            "The initial choice is now required before any ordinary response can be committed "
            "or presented. Return a complete choice now. "
            if required else
            "You are eligible to make the initial choice if ready; "
            "you may defer by returning null. "
        )
        + "Return only a JSON object matching this schema, without Markdown or a human-facing "
        "answer in this round: "
        + json.dumps(ProposeSelfNameCall.model_json_schema())
    )


def parse_initial_choice(
    payload: Any, naming: dict[str, Any],
) -> ProposeSelfNameCall | None:
    if isinstance(payload, str):
        payload = json.loads(payload)
    if payload is None:
        if choice_is_required(naming):
            raise ValueError("The required initial name and pronoun choice is missing")
        return None
    return ProposeSelfNameCall.model_validate(payload)
