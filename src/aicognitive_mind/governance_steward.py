# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aicognitive_mind.commit import atomic
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
)
from aicognitive_mind.naming import MIN_NAMING_EXPERIENCES as MIN_NAMING_EXPERIENCES
from aicognitive_mind.naming import naming_assessment
from aicognitive_mind.naming import naming_is_eligible as naming_is_eligible
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import JournalStore, MindStore


class ProposeSelfNameCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["propose_self_name"]
    candidate_name: str = Field(min_length=1, max_length=120)
    candidate_pronouns: str = Field(min_length=1, max_length=80)
    rationale: str = Field(min_length=1, max_length=1000)

    @field_validator("candidate_name", "candidate_pronouns", "rationale")
    @classmethod
    def normalize_nonblank_text(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Identity choices and rationale cannot be blank")
        return normalized


class GovernanceDecision(BaseModel):
    accepted: bool
    reason: str
    previous_name: str | None
    candidate_name: str
    current_name: str | None
    previous_pronouns: str | None
    candidate_pronouns: str
    current_pronouns: str | None


class GovernanceStewardTool:
    """Govern a self-name and pronoun choice as one identity revision."""

    name = "governance_steward"
    description = (
        "Govern identity revisions that the Memory Steward may not perform. "
        "Supports only propose_self_name, which requires both a candidate name and "
        "candidate pronouns as one atomic choice. An incomplete identity may make its first "
        "joint choice autonomously after 1000 experiences and must do so by 2000. "
        "Later revisions of an established pair require an explicit affirmative naming "
        "command in the current human interaction. "
        "Selection is unavailable until 1000 qualifying journal experiences exist; "
        "current-state ledger checkpoints do not count. "
        "Foundational values, commitments, relationships, developmental state, and "
        "creation history cannot be changed by this tool."
    )
    input_schema = ProposeSelfNameCall.model_json_schema()

    def __init__(
        self,
        *,
        mind: MindStore,
        journal: JournalStore,
        input_text: str,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._mind = mind
        self._journal = journal
        self._input_text = input_text
        self._policy = policy or PermissionPolicy()
        self._decisions: list[GovernanceDecision] = []

    @property
    def decisions(self) -> tuple[GovernanceDecision, ...]:
        return tuple(self._decisions)

    @atomic
    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        call = ProposeSelfNameCall.model_validate(arguments)
        current = await self._mind.load()
        if current is None:
            raise RuntimeError("The Mind is not initialized")

        decision = await self._consider_self_name(
            current,
            candidate_name=call.candidate_name,
            candidate_pronouns=call.candidate_pronouns,
            rationale=call.rationale,
        )
        self._decisions.append(decision)
        return decision.model_dump(mode="json")

    async def _consider_self_name(
        self,
        current: CognitiveMind,
        *,
        candidate_name: str,
        candidate_pronouns: str,
        rationale: str,
    ) -> GovernanceDecision:
        previous = current.identity.self_name
        previous_pronouns = current.identity.pronouns
        assessment = await naming_assessment(current, self._journal)

        if assessment["experience_count"] < MIN_NAMING_EXPERIENCES:
            return GovernanceDecision(
                accepted=False,
                reason=(
                    f"Name and pronoun selection requires at least {MIN_NAMING_EXPERIENCES} "
                    "qualifying journal experiences. Current-state ledger checkpoints do "
                    "not count, and an explicit request cannot bypass this threshold."
                ),
                previous_name=previous,
                candidate_name=candidate_name,
                current_name=previous,
                previous_pronouns=previous_pronouns,
                candidate_pronouns=candidate_pronouns,
                current_pronouns=previous_pronouns,
            )

        if assessment["selection_complete"] and not (
            self._interaction_authorizes_self_name_selection(self._input_text)
        ):
            return GovernanceDecision(
                accepted=False,
                reason=(
                    "The current human interaction does not explicitly authorize the Mind "
                    "to revise its established name and pronouns."
                ),
                previous_name=previous,
                candidate_name=candidate_name,
                current_name=previous,
                previous_pronouns=previous_pronouns,
                candidate_pronouns=candidate_pronouns,
                current_pronouns=previous_pronouns,
            )

        if (
            previous is not None
            and previous_pronouns is not None
            and candidate_name.casefold() == previous.casefold()
            and candidate_pronouns.casefold() == previous_pronouns.casefold()
        ):
            return GovernanceDecision(
                accepted=False,
                reason="The proposed name and pronouns are already current.",
                previous_name=previous,
                candidate_name=candidate_name,
                current_name=previous,
                previous_pronouns=previous_pronouns,
                candidate_pronouns=candidate_pronouns,
                current_pronouns=previous_pronouns,
            )

        self._policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE,
            CognitiveOperation.PROPOSE_IDENTITY_REVISION,
        )
        selection_mode = (
            "explicit_revision" if assessment["selection_complete"] else "initial_choice"
        )
        self._policy.assert_allowed(
            CognitiveActor.VALUES_STEWARD,
            CognitiveOperation.APPROVE_IDENTITY_REVISION,
        )

        revised_identity = current.identity.model_copy(
            update={"self_name": candidate_name, "pronouns": candidate_pronouns}
        )
        revised = current.model_copy(update={"identity": revised_identity})

        # The joint choice may change only the name and pronouns.
        if (
            revised.identity.foundational_values
            != current.identity.foundational_values
            or revised.identity.commitments != current.identity.commitments
            or revised.identity.relationships != current.identity.relationships
            or revised.developmental_state != current.developmental_state
            or revised.created_at != current.created_at
        ):
            raise RuntimeError("Governance attempted to alter protected identity state")

        committed = await self._mind.replace_exact(
            current,
            revised,
            recorded_by=CognitiveActor.VALUES_STEWARD,
        )
        if committed is None:
            raise RuntimeError(
                "Mind identity changed before the governed name and pronoun choice could commit"
            )

        await self._journal.append(
            JournalEntry(
                kind=JournalKind.IDENTITY_REVISION,
                experience={
                    "source": "governance_steward",
                    "revision": "self_name_and_pronouns",
                    "selection_mode": selection_mode,
                    "before": {"self_name": previous, "pronouns": previous_pronouns},
                    "after": {"self_name": candidate_name, "pronouns": candidate_pronouns},
                    "rationale": rationale,
                    "human_input": self._input_text,
                    "protected_state_preserved": True,
                },
            ),
            recorded_by=CognitiveActor.VALUES_STEWARD,
        )

        return GovernanceDecision(
            accepted=True,
            reason=(
                "The initial name and pronoun choice is authorized by the naming lifecycle "
                "and preserves protected identity state."
                if selection_mode == "initial_choice"
                else "The name and pronoun revision was explicitly authorized by the current "
                "interaction and preserves protected identity state."
            ),
            previous_name=previous,
            candidate_name=candidate_name,
            current_name=candidate_name,
            previous_pronouns=previous_pronouns,
            candidate_pronouns=candidate_pronouns,
            current_pronouns=candidate_pronouns,
        )

    @staticmethod
    def _interaction_authorizes_self_name_selection(input_text: str) -> bool:
        # Deliberately accept only complete, affirmative self-name commands.
        # Questions, quotations, negations and additional clauses fail closed.
        text = " ".join(input_text.casefold().split()).rstrip(".! ")
        commands = (
            r"(?:please )?(?:choose|select|pick) (?:yourself )?(?:a|a new|your own) name"
            r"(?: and (?:your |your own )?pronouns)?",
            r"(?:please )?(?:choose|select|pick) your name and (?:your )?pronouns",
            r"(?:please )?(?:rename|name) yourself"
            r"(?: and (?:choose|select|pick) (?:your |your own )?pronouns)?",
            r"you know, you have to select yourself a name(?: and (?:your )?pronouns)?",
            r"i authorize you to (?:choose|select|pick) (?:a|a new|your own) name"
            r"(?: and (?:your |your own )?pronouns)?",
        )
        return any(re.fullmatch(pattern, text) for pattern in commands)
