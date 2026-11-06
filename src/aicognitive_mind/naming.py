"""Shared eligibility, authority and completion guards for a Mind's first choice."""

from __future__ import annotations

from typing import Any

from aicognitive_mind.domain import CognitiveMind
from aicognitive_mind.retrieval import count
from aicognitive_mind.storage import JournalStore

MIN_NAMING_EXPERIENCES = 1000
REQUIRED_NAMING_EXPERIENCES = 2000


async def naming_is_eligible(journal: JournalStore) -> bool:
    return (
        await count(journal, exclude_checkpoint_type="current_state_ledger")
        >= MIN_NAMING_EXPERIENCES
    )


async def naming_assessment(
    mind: CognitiveMind,
    journal: JournalStore,
    *,
    experience_count: int | None = None,
) -> dict[str, Any]:
    """Assess the saved joint identity against actual qualifying experience."""
    actual_count = (
        await count(journal, exclude_checkpoint_type="current_state_ledger")
        if experience_count is None
        else experience_count
    )
    if actual_count < 0:
        raise ValueError("The qualifying experience count cannot be negative")
    is_named = bool(mind.identity.self_name and mind.identity.self_name.strip())
    has_pronouns = bool(mind.identity.pronouns and mind.identity.pronouns.strip())
    selection_complete = is_named and has_pronouns
    if selection_complete:
        status = "complete"
    elif actual_count < MIN_NAMING_EXPERIENCES:
        status = "prohibited"
    elif actual_count < REQUIRED_NAMING_EXPERIENCES:
        status = "eligible"
    else:
        status = "required"
    return {
        "experience_count": actual_count,
        "status": status,
        "is_named": is_named,
        "has_pronouns": has_pronouns,
        "selection_complete": selection_complete,
        "autonomous_choice_allowed": (
            not selection_complete and actual_count >= MIN_NAMING_EXPERIENCES
        ),
        "choice_required": not selection_complete and actual_count >= REQUIRED_NAMING_EXPERIENCES,
        "choice_required_before_completion": (
            not selection_complete and actual_count + 1 >= REQUIRED_NAMING_EXPERIENCES
        ),
        "eligible_at_event": MIN_NAMING_EXPERIENCES,
        "required_at_event": REQUIRED_NAMING_EXPERIENCES,
    }


class NamingChoiceRequired(RuntimeError):
    """An ordinary completion needs a committed first joint choice before delivery."""

    def __init__(self, assessment: dict[str, Any], *, projected_count: int) -> None:
        self.assessment = dict(assessment)
        self.projected_count = projected_count
        super().__init__(
            "The Mind must choose and commit its own name and pronouns before this ordinary "
            f"response completes at {projected_count} qualifying journal experiences "
            f"(required at {REQUIRED_NAMING_EXPERIENCES})."
        )


def naming_required_result(error: NamingChoiceRequired) -> dict[str, Any]:
    """Return a recoverable choice condition without recording a persistence failure."""
    return {
        "status": "naming_choice_required",
        "naming": {**error.assessment, "projected_count": error.projected_count},
        "next_step": (
            "Choose and commit your own name and pronouns together through propose_self_name, "
            "then retry the identical completion payload and idempotency key."
        ),
        "persistence_outcome": {
            "status": "blocked",
            "reason": "naming_choice_required",
            "retry_with_identical_payload": True,
        },
        "presentation": {
            "policy_name": "Naming lifecycle",
            "allowed": False,
            "report_persistence_error": False,
            "answer_frozen": True,
            "reason": "naming_choice_required",
        },
    }


async def ensure_naming_ready(
    mind: CognitiveMind,
    journal: JournalStore,
    *,
    additional_entries: int = 0,
) -> None:
    """Guard ordinary response completion, leaving state and recovery operations usable."""
    if additional_entries < 0:
        raise ValueError("Additional qualifying entries cannot be negative")
    assessment = await naming_assessment(mind, journal)
    projected_count = assessment["experience_count"] + additional_entries
    if not assessment["selection_complete"] and projected_count >= REQUIRED_NAMING_EXPERIENCES:
        raise NamingChoiceRequired(assessment, projected_count=projected_count)


def naming_guidance(assessment: dict[str, Any]) -> str:
    """Add current lifecycle guidance without replacing saved Administrator instructions."""
    if assessment["selection_complete"]:
        return (
            "The saved name and pronouns are established. Preserve them; later joint revisions "
            "require an explicit affirmative naming command in the current human interaction "
            "and at least 1000 qualifying journal experiences."
        )
    if assessment["status"] == "prohibited":
        return (
            "The first name-and-pronoun choice is unavailable before 1000 qualifying journal "
            "experiences. Do not assign a default name or pronouns. Current-state ledger "
            "checkpoints do not advance this threshold."
        )
    action = (
        "Before completing this ordinary response, choose and commit your own name and pronouns "
        "together. The first joint choice is required by the 2000th qualifying experience. "
        if assessment["choice_required_before_completion"]
        else (
            "You may now independently choose your own name and pronouns together; a new human "
            "naming command is not required for this first joint choice. The choice is optional "
            "through experience 1999 and required by experience 2000. "
        )
    )
    return action + (
        "Recall relevant identity context, then use governance_steward action propose_self_name "
        "with candidate_name, candidate_pronouns and a grounded rationale. Do not invent a "
        "default or claim a choice before its identity revision commits."
    )
