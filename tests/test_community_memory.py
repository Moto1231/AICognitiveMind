import asyncio
import unittest
from dataclasses import asdict
from typing import cast

from aicognitive_mind.community_memory import (
    CommunityDraft,
    CommunityGrant,
    CommunityPrincipal,
    InMemorySyntheticCommunityStore,
    SyntheticLesson,
    sleep_with_synthetic_community,
)

ALPHA = CommunityPrincipal("account-alpha", "mind-alpha")
BETA = CommunityPrincipal("account-beta", "mind-beta")
WRONG_MIND = CommunityPrincipal("account-alpha", "not-alpha")
GROUP = "synthetic-group"
PRIVATE = "synthetic-private-marker-not-for-community"
FIXTURE = SyntheticLesson.CHECK_BINDINGS


async def personal() -> dict[str, str]:
    return {"journal": PRIVATE}


async def select(draft: CommunityDraft) -> bool:
    assert PRIVATE not in str(asdict(draft))
    return True


def run(store, *, principal=ALPHA, lessons=(FIXTURE,), curator=select, sleeper=personal):
    return sleep_with_synthetic_community(
        personal_sleep=sleeper, principal=principal, group=GROUP, lessons=lessons,
        curate=curator, store=store,
    )


def join(store, principal=ALPHA):
    store.set_membership(principal, GROUP, True)
    store.set_opt_in(principal, True)


class CommunityMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_off_and_membership_and_mind_gates_both_directions(self):
        store = InMemorySyntheticCommunityStore()
        store.set_membership(ALPHA, GROUP, True)

        async def forbidden(_):
            self.fail("opt-out or wrong Mind reached curator")

        assert (await run(store, curator=forbidden)).newly_published == 0
        join(store)
        assert (await run(store)).newly_published == 1
        store.set_membership(BETA, GROUP, True)
        assert await store.recall(BETA, GROUP) == ()
        store.set_opt_in(BETA, True)
        assert len(await store.recall(BETA, GROUP)) == 1
        assert await store.recall(BETA, "other-group") == ()
        assert await store.recall(WRONG_MIND, GROUP) == ()
        assert (await run(store, principal=WRONG_MIND, curator=forbidden)).newly_published == 0
        store.set_membership(BETA, GROUP, False)
        assert await store.recall(BETA, GROUP) == ()

    async def test_sleep_precedes_curation_and_only_fixture_fields_are_visible(self):
        store = InMemorySyntheticCommunityStore()
        join(store)
        phases = []

        async def sleeper():
            phases.append("personal")
            return await personal()

        async def curator(draft):
            assert phases == ["personal"]
            fields = asdict(draft)
            assert set(fields) == {"lesson", "title", "guidance"}
            markers = (PRIVATE, "account-alpha", "mind-alpha")
            assert all(marker not in str(fields) for marker in markers)
            phases.append("community")
            return True

        result = await run(store, curator=curator, sleeper=sleeper)
        assert phases == ["personal", "community"]
        assert result.personal == {"journal": PRIVATE}
        assert result.newly_published == 1
        assert PRIVATE not in str(await store.recall(ALPHA, GROUP))

        async def failure():
            raise RuntimeError("synthetic failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            await run(store, sleeper=failure, curator=curator)

    async def test_fixed_fixture_only_and_ai_output_cannot_publish_text(self):
        store = InMemorySyntheticCommunityStore()
        join(store)

        async def invalid_output(_):
            return cast(bool, "malicious draft output")

        async def raises(_):
            raise ValueError("sensitive error detail")

        async def declines(_):
            return False

        for curator in (declines, invalid_output, raises):
            assert (await run(store, curator=curator)).newly_published == 0
        with self.assertRaisesRegex(ValueError, "Only enumerated"):
            await run(store, lessons=(cast(SyntheticLesson, "check_bindings"),))
        assert await store.recall(ALPHA, GROUP) == ()

    async def test_revocation_is_current_and_reopt_in_does_not_resurrect_stale_publications(self):
        store = InMemorySyntheticCommunityStore()
        join(store, ALPHA)
        join(store, BETA)
        assert (await run(store)).newly_published == 1

        async def revoke_then_rejoin(_):
            store.set_opt_in(ALPHA, False)
            assert await store.recall(ALPHA, GROUP) == ()
            assert await store.recall(BETA, GROUP) == ()
            store.set_opt_in(ALPHA, True)
            return True

        assert (await run(
            store, lessons=(SyntheticLesson.VALIDATE_IMPORT,), curator=revoke_then_rejoin,
        )).newly_published == 0
        assert await store.recall(BETA, GROUP) == ()

        async def membership_churn(_):
            store.set_membership(ALPHA, GROUP, False)
            store.set_membership(ALPHA, GROUP, True)
            return True

        assert (await run(store, curator=membership_churn)).newly_published == 0
        assert await store.recall(BETA, GROUP) == ()

    async def test_retries_and_duplicate_fixtures_do_not_create_duplicate_publications(self):
        store = InMemorySyntheticCommunityStore()
        join(store)
        assert (await run(store, lessons=(FIXTURE, FIXTURE))).newly_published == 1
        assert (await run(store)).newly_published == 0
        assert len(await store.recall(ALPHA, GROUP)) == 1

    async def test_store_rejects_missing_or_transplanted_grants(self):
        store = InMemorySyntheticCommunityStore()
        assert not await store.publish(ALPHA, GROUP, cast(CommunityGrant, None), FIXTURE)
        join(store, ALPHA)
        join(store, BETA)
        grant = await store.current_grant(ALPHA, GROUP)
        assert grant is not None
        assert not await store.publish(BETA, GROUP, grant, FIXTURE)
        assert not await store.publish(ALPHA, "other", grant, FIXTURE)
        assert await store.recall(BETA, GROUP) == ()

    async def test_concurrent_approvals_publish_only_once(self):
        store = InMemorySyntheticCommunityStore()
        join(store)
        concurrent = asyncio.Event()
        decisions = 0

        async def curator(_):
            nonlocal decisions
            decisions += 1
            if decisions == 2:
                concurrent.set()
            await asyncio.wait_for(concurrent.wait(), timeout=1)
            return True

        results = await asyncio.gather(run(store, curator=curator), run(store, curator=curator))
        assert sorted(result.newly_published for result in results) == [0, 1]
        assert len(await store.recall(ALPHA, GROUP)) == 1
