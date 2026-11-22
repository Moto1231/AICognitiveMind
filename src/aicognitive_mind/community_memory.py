"""Synthetic-only Community Memory core for staged application integration.

The only publishable text is the fixed fixture catalog. The curator can choose
or decline a fixture, never supply text. A host must authenticate and bind
account/Mind/group before using any future adapter; this module is not an
authentication boundary or a production datastore.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Protocol


class SyntheticLesson(StrEnum):
    CHECK_BINDINGS = "check_bindings"
    VALIDATE_IMPORT = "validate_import"


@dataclass(frozen=True, slots=True)
class CommunityDraft:
    lesson: SyntheticLesson
    title: str
    guidance: str


_FIXTURES = MappingProxyType({
    SyntheticLesson.CHECK_BINDINGS: CommunityDraft(
        SyntheticLesson.CHECK_BINDINGS,
        "Check synthetic field bindings",
        "Compare each form binding against the matching interface property and type.",
    ),
    SyntheticLesson.VALIDATE_IMPORT: CommunityDraft(
        SyntheticLesson.VALIDATE_IMPORT,
        "Validate a synthetic import before rollout",
        "Try one reversible change in a disposable test environment before a wider rollout.",
    ),
})


def synthetic_community_draft(lesson: SyntheticLesson) -> CommunityDraft:
    """Resolve an approved synthetic catalog identifier to its immutable lesson."""
    if type(lesson) is not SyntheticLesson:
        raise ValueError("Only enumerated synthetic lesson fixtures are accepted")
    return _FIXTURES[lesson]


@dataclass(frozen=True, slots=True)
class CommunityPrincipal:
    account_id: str
    mind_id: str


@dataclass(frozen=True, slots=True)
class CommunityGrant:
    principal: CommunityPrincipal
    group: str
    opt_in_epoch: int
    membership_epoch: int


class SyntheticCommunityStore(Protocol):
    """Implementations must atomically compare current grant at publish/read."""

    async def current_grant(
        self, principal: CommunityPrincipal, group: str
    ) -> CommunityGrant | None: ...

    async def publish(
        self, principal: CommunityPrincipal, group: str, grant: CommunityGrant,
        lesson: SyntheticLesson,
    ) -> bool: ...

    async def recall(
        self, principal: CommunityPrincipal, group: str
    ) -> tuple[CommunityDraft, ...]: ...


class InMemorySyntheticCommunityStore:
    """Single event-loop fixture store. No network, credentials or persistence."""

    def __init__(self) -> None:
        self._opt_in: dict[CommunityPrincipal, tuple[bool, int]] = {}
        self._members: dict[tuple[CommunityPrincipal, str], tuple[bool, int]] = {}
        self._published: dict[tuple[CommunityPrincipal, str, SyntheticLesson], CommunityGrant] = {}

    def set_opt_in(self, principal: CommunityPrincipal, enabled: bool) -> None:
        """Set the one synthetic principal choice for both contribution and recall."""
        prior, epoch = self._opt_in.get(principal, (False, 0))
        if enabled != prior:
            self._opt_in[principal] = (enabled, epoch + 1)
            if not enabled:
                self._remove(principal)

    def set_membership(self, principal: CommunityPrincipal, group: str, allowed: bool) -> None:
        """Trusted fixture administration, not a user-facing join method."""
        key = (principal, group)
        prior, epoch = self._members.get(key, (False, 0))
        if allowed != prior:
            self._members[key] = (allowed, epoch + 1)
            if not allowed:
                self._remove(principal, group)

    def _remove(self, principal: CommunityPrincipal, group: str | None = None) -> None:
        for key in list(self._published):
            if key[0] == principal and (group is None or key[1] == group):
                del self._published[key]

    def _grant(self, principal: CommunityPrincipal, group: str) -> CommunityGrant | None:
        opted_in, opt_epoch = self._opt_in.get(principal, (False, 0))
        member, member_epoch = self._members.get((principal, group), (False, 0))
        if not opted_in or not member:
            return None
        return CommunityGrant(principal, group, opt_epoch, member_epoch)

    async def current_grant(
        self, principal: CommunityPrincipal, group: str
    ) -> CommunityGrant | None:
        return self._grant(principal, group)

    async def publish(
        self, principal: CommunityPrincipal, group: str, grant: CommunityGrant,
        lesson: SyntheticLesson,
    ) -> bool:
        if (
            type(lesson) is not SyntheticLesson or type(grant) is not CommunityGrant
            or self._grant(principal, group) != grant
        ):
            return False
        key = (principal, group, lesson)
        if key in self._published:
            return False
        self._published[key] = grant
        return True

    async def recall(
        self, principal: CommunityPrincipal, group: str
    ) -> tuple[CommunityDraft, ...]:
        if self._grant(principal, group) is None:
            return ()
        lessons = {
            lesson for (owner, target, lesson), grant in self._published.items()
            if target == group and self._grant(owner, target) == grant
        }
        # Return contents only, without source principals, grant IDs, or private state.
        return tuple(_FIXTURES[lesson] for lesson in sorted(lessons))


@dataclass(frozen=True, slots=True)
class SyntheticSleepResult[PersonalResult]:
    personal: PersonalResult
    newly_published: int


async def sleep_with_synthetic_community[PersonalResult](
    *,
    personal_sleep: Callable[[], Awaitable[PersonalResult]],
    principal: CommunityPrincipal,
    group: str,
    lessons: tuple[SyntheticLesson, ...],
    curate: Callable[[CommunityDraft], Awaitable[bool]],
    store: SyntheticCommunityStore,
) -> SyntheticSleepResult[PersonalResult]:
    """Run personal sleep first, then optionally curate fixed synthetic fixtures.

    Personal exceptions propagate, preventing curation. Curator errors fail
    closed per candidate and do not undo successful personal consolidation.
    Does not copy or write community recall into private memory.
    """
    personal = await personal_sleep()
    # Exclude str values even when equal to str-enum labels; never curate caller text.
    if type(lessons) is not tuple or any(type(lesson) is not SyntheticLesson for lesson in lessons):
        raise ValueError("Only enumerated synthetic lesson fixtures are accepted")
    grant = await store.current_grant(principal, group)
    if grant is None:
        return SyntheticSleepResult(personal, 0)
    published = 0
    for lesson in dict.fromkeys(lessons):
        if await store.current_grant(principal, group) != grant:
            break
        try:
            selected = await curate(_FIXTURES[lesson])
        except Exception:
            continue
        if selected is True:
            # The store must reject a stale grant, including revoke + re-opt-in
            # while the curator is awaiting its decision.
            published += await store.publish(principal, group, grant, lesson)
    return SyntheticSleepResult(personal, published)
