# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import JournalStore, MindStore


class ProposeSelfNameCall(BaseModel):
    action: Literal["propose_self_name"]
    candidate_name: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=1000)


class GovernanceDecision(BaseModel):
    accepted: bool
    reason: str
    previous_name: str
    candidate_name: str
    current_name: str


class GovernanceStewardTool:
    """Narrow identity-governance authority for explicit self-name revision."""

    name = "governance_steward"
    description = (
        "Govern identity revisions that the Memory Steward may not perform. "
        "V0.1 supports only propose_self_name, and only when the current human "
        "interaction explicitly asks the Mind to choose, select, or change its own name. "
        "Pronouns, foundational values, commitments, relationships, developmental state, and "
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

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        call = ProposeSelfNameCall.model_validate(arguments)
        current = await self._mind.load()
        if current is None:
            raise RuntimeError("The Mind is not initialized")

        candidate = " ".join(call.candidate_name.split()).strip()
        decision = await self._consider_self_name(
            current,
            candidate_name=candidate,
            rationale=call.rationale.strip(),
        )
        self._decisions.append(decision)
        return decision.model_dump(mode="json")

    async def _consider_self_name(
        self,
        current: CognitiveMind,
        *,
        candidate_name: str,
        rationale: str,
    ) -> GovernanceDecision:
        previous = current.identity.self_name

        if not self._interaction_authorizes_self_name_selection(self._input_text):
            return GovernanceDecision(
                accepted=False,
                reason=(
                    "The current human interaction does not explicitly authorize the Mind "
                    "to choose or change its own name."
                ),
                previous_name=previous,
                candidate_name=candidate_name,
                current_name=previous,
            )

        if candidate_name.casefold() == previous.casefold():
            return GovernanceDecision(
                accepted=False,
                reason="The proposed self-name is already the current self-name.",
                previous_name=previous,
                candidate_name=candidate_name,
                current_name=previous,
            )

        self._policy.assert_allowed(
            CognitiveActor.REASONING_ENGINE,
            CognitiveOperation.PROPOSE_IDENTITY_REVISION,
        )
        self._policy.assert_allowed(
            CognitiveActor.VALUES_STEWARD,
            CognitiveOperation.APPROVE_IDENTITY_REVISION,
        )

        revised_identity = current.identity.model_copy(
            update={"self_name": candidate_name}
        )
        revised = current.model_copy(update={"identity": revised_identity})

        # Guard the V0.1 boundary explicitly: the proposal may change only self_name.
        # Pronouns are governed identity state and remain protected here.
        if (
            revised.identity.pronouns != current.identity.pronouns
            or revised.identity.foundational_values
            != current.identity.foundational_values
            or revised.identity.commitments != current.identity.commitments
            or revised.identity.relationships != current.identity.relationships
            or revised.developmental_state != current.developmental_state
            or revised.created_at != current.created_at
        ):
            raise RuntimeError("Governance V0.1 attempted to alter protected identity state")

        committed = await self._mind.replace_exact(
            current,
            revised,
            recorded_by=CognitiveActor.VALUES_STEWARD,
        )
        if committed is None:
            raise RuntimeError(
                "Mind identity changed before the governed self-name revision could commit"
            )

        await self._journal.append(
            JournalEntry(
                kind=JournalKind.IDENTITY_REVISION,
                experience={
                    "source": "governance_steward",
                    "revision": "self_name",
                    "before": {"self_name": previous},
                    "after": {"self_name": candidate_name},
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
                "The self-name revision was explicitly authorized by the current "
                "interaction and preserves protected identity state."
            ),
            previous_name=previous,
            candidate_name=candidate_name,
            current_name=candidate_name,
        )

    @staticmethod
    def _interaction_authorizes_self_name_selection(input_text: str) -> bool:
        text = " ".join(input_text.casefold().split())
        if "name" not in text:
            return False
        patterns = (
            r"\bchoose\b.*\bname\b",
            r"\bselect\b.*\bname\b",
            r"\bpick\b.*\bname\b",
            r"\bdecide\b.*\bname\b",
            r"\bname\s+yourself\b",
            r"\bcall\s+yourself\b",
            r"\brename\s+yourself\b",
            r"\byour\s+own\s+name\b",
            r"\bselect\s+yourself\b.*\bname\b",
            r"\bchoose\s+yourself\b.*\bname\b",
        )
        return any(re.search(pattern, text) for pattern in patterns)
