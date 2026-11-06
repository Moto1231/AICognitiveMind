"""Boundary and recovery checks for the service's mandatory first identity choice."""

import unittest
from unittest.mock import patch

from aicognitive_mind.continuity_health import STATE_KEY
from aicognitive_mind.domain import CognitiveActor, JournalEntry, JournalKind, MemoryClass
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.retrieval import count
from aicognitive_mind.steward_agent import StewardProtocolError
from aicognitive_mind.storage import (
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class CrossingSteward(MemoryStewardTool):
    async def complete(self):
        trace = await super().complete()
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.REFLECTION,
                experience={"synthetic": "review advanced the qualifying history"},
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        return trace


class DegradedCrossingSteward(MemoryStewardTool):
    async def review_interaction(self, *args, **kwargs):
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.REFLECTION,
                experience={"synthetic": "review failed after staging an experience"},
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        raise StewardProtocolError("Synthetic review failure")


class RequiredNamingServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mind = InMemoryMindStore()
        self.journal = InMemoryJournalStore()
        self.memory = InMemoryMemoryStore()
        self.service = self.make_service()
        await self.service.initialize()

    def make_service(self, factory=MemoryStewardTool):
        return CognitiveMcpService(
            mind=self.mind,
            journal=self.journal,
            memory=self.memory,
            steward_factory=factory,
        )

    async def seed_to_count(self, total, *, checkpoints=0):
        current = await count(self.journal, exclude_checkpoint_type="current_state_ledger")
        self.assertLessEqual(current, total)
        for index in range(total - current):
            await self.journal.append(
                JournalEntry(
                    kind=JournalKind.INTERACTION,
                    experience={"input": {"content": f"Synthetic history {index}."}},
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
        for _ in range(checkpoints):
            await self.service.update_current_state(
                "state_refreshed", source="synthetic_naming_history"
            )

    async def choose_identity(self):
        tool = GovernanceStewardTool(
            mind=self.mind,
            journal=self.journal,
            input_text="Continue the synthetic report.",
        )
        decision = await tool.invoke({
            "action": "propose_self_name",
            "candidate_name": "Aster",
            "candidate_pronouns": "he/him",
            "rationale": "A first name and pronouns selected together after enough experience.",
        })
        self.assertTrue(decision["accepted"])
        return decision

    def assert_naming_blocked(self, result):
        self.assertEqual(result["status"], "naming_choice_required")
        self.assertFalse(result["presentation"]["allowed"])
        self.assertFalse(result["presentation"]["report_persistence_error"])
        self.assertFalse(result["naming"]["selection_complete"])

    async def test_1999_requires_choice_before_new_completion_and_same_key_can_recover(self):
        await self.seed_to_count(1999)
        begun = await self.service.begin_interaction("Continue the synthetic report.")
        self.assertEqual(begun["status"], "ready_to_reason")
        self.assertEqual(begun["naming"]["status"], "eligible")
        self.assertTrue(begun["naming"]["choice_required_before_completion"])
        self.assertEqual(begun["presentation_policy"]["mode"], "naming_required")
        payload = {
            "user_message": "Continue the synthetic report.",
            "response_text": "Here is the completed synthetic report.",
            "idempotency_key": begun["idempotency_key"],
        }
        before_entries = await self.journal.read()
        before_mind = await self.mind.load()
        before_health = await self.service._records.get(STATE_KEY)

        blocked = await self.service.complete_interaction(**payload)

        self.assert_naming_blocked(blocked)
        self.assertEqual(await self.journal.read(), before_entries)
        self.assertEqual(await self.mind.load(), before_mind)
        self.assertEqual(await self.service._records.get(STATE_KEY), before_health)
        self.assertEqual(getattr(self.journal, "_commit_receipts", {}), {})

        await self.choose_identity()
        accepted = await self.service.complete_interaction(**payload)
        after_entries = await self.journal.read()
        retried = await self.service.complete_interaction(**payload)

        self.assertEqual(accepted["status"], "interaction_committed")
        self.assertTrue(accepted["presentation"]["allowed"])
        self.assertEqual(retried["occurred_at"], accepted["occurred_at"])
        self.assertEqual(await self.journal.read(), after_entries)
        self.assertEqual(len(after_entries), len(before_entries) + 2)
        saved = await self.mind.load()
        self.assertEqual(saved.identity.self_name, "Aster")
        self.assertEqual(saved.identity.pronouns, "he/him")

    async def test_required_choice_does_not_block_begin_status_or_state_recovery(self):
        await self.seed_to_count(2000)
        begun = await self.service.begin_interaction("Continue.")
        self.assertEqual(begun["status"], "ready_to_reason")
        self.assertEqual(begun["naming"]["status"], "required")
        self.assertTrue(begun["naming"]["autonomous_choice_allowed"])
        before_count = await count(self.journal, exclude_checkpoint_type="current_state_ledger")
        await self.service.update_current_state(
            "topic_changed", {"values": {"active_topic": "Resolve the first identity choice."}}
        )
        status = await self.service.status()
        self.assertEqual(status["naming"]["status"], "required")
        self.assertEqual(status["journal_experience_count"], before_count)
        blocked = await self.service.complete_interaction(
            "Continue.", "An ordinary answer.", idempotency_key=begun["idempotency_key"]
        )
        self.assert_naming_blocked(blocked)

    async def test_established_joint_identity_is_complete_and_can_continue_past_2000(self):
        await self.seed_to_count(1999)
        await self.choose_identity()
        status = await self.service.status()
        self.assertEqual(status["journal_experience_count"], 2000)
        self.assertEqual(status["naming"]["status"], "complete")
        self.assertTrue(status["naming"]["selection_complete"])
        begun = await self.service.begin_interaction("Continue with the established identity.")
        self.assertEqual(begun["presentation_policy"]["mode"], "presentation_first")
        before_mind = await self.mind.load()

        completed = await self.service.complete_interaction(
            "Continue.", "Continuing with the established identity.", idempotency_key="named-turn"
        )

        self.assertEqual(completed["status"], "interaction_committed")
        self.assertTrue(completed["presentation"]["allowed"])
        self.assertEqual(await self.mind.load(), before_mind)

    async def test_excluded_checkpoints_do_not_make_an_ordinary_turn_prematurely_required(self):
        await self.seed_to_count(1998, checkpoints=25)
        begun = await self.service.begin_interaction("Continue.")
        self.assertEqual(
            begun["presentation_policy"]["mode"], "completion_required_for_initial_identity",
        )
        self.assertFalse(begun["naming"]["choice_required_before_completion"])
        self.assertIn("hold the frozen answer", begun["presentation_policy"]["instruction"])
        self.assertIn("ordinary work may continue", begun["presentation_policy"]["instruction"])
        completed = await self.service.complete_interaction(
            "Continue.", "An ordinary answer before the deadline.",
            idempotency_key="before-deadline",
        )
        self.assertEqual(completed["status"], "interaction_committed")
        status = await self.service.status()
        self.assertEqual(status["journal_experience_count"], 1999)
        self.assertEqual(status["naming"]["status"], "eligible")
        self.assertFalse(status["naming"]["selection_complete"])

    async def test_late_steward_experience_cannot_cross_deadline_with_ordinary_answer(self):
        await self.seed_to_count(1998)
        service = self.make_service(CrossingSteward)
        before_entries = await self.journal.read()
        before_health = await service._records.get(STATE_KEY)
        blocked = await service.complete_interaction(
            "Remember the synthetic project uses a ledger.",
            "The synthetic project uses a ledger.",
            proposed_memories=(MemoryProposal(
                memory_class=MemoryClass.SEMANTIC,
                content="The synthetic project uses a ledger.",
                grounding=("Direct synthetic project statement",),
            ),),
            idempotency_key="review-crossed-deadline",
        )
        self.assert_naming_blocked(blocked)
        self.assertEqual(await self.journal.read(), before_entries)
        self.assertEqual(await self.memory.read(), [])
        self.assertEqual(await service._records.get(STATE_KEY), before_health)
        self.assertEqual(getattr(self.journal, "_commit_receipts", {}), {})

    async def test_degraded_review_staging_cannot_cross_the_deadline(self):
        await self.seed_to_count(1998)
        service = self.make_service(DegradedCrossingSteward)
        before_entries = await self.journal.read()
        before_health = await service._records.get(STATE_KEY)
        blocked = await service.complete_interaction(
            "Continue.", "The ordinary answer is frozen.", idempotency_key="degraded-deadline"
        )
        self.assert_naming_blocked(blocked)
        self.assertEqual(await self.journal.read(), before_entries)
        self.assertEqual(await service._records.get(STATE_KEY), before_health)
        self.assertEqual(getattr(self.journal, "_commit_receipts", {}), {})

    async def test_cached_receipt_is_held_at_2000_and_released_after_initial_choice(self):
        await self.seed_to_count(1000)
        payload = {
            "user_message": "An earlier synthetic request.",
            "response_text": "The original frozen response.",
            "idempotency_key": "historical-receipt",
        }
        original = await self.service.complete_interaction(**payload)
        self.assertEqual(original["status"], "interaction_committed")
        await self.seed_to_count(2000)
        before_entries = await self.journal.read()
        before_health = await self.service._records.get(STATE_KEY)

        blocked = await self.service.complete_interaction(**payload)

        self.assert_naming_blocked(blocked)
        self.assertEqual(await self.journal.read(), before_entries)
        self.assertEqual(await self.service._records.get(STATE_KEY), before_health)
        await self.choose_identity()
        selected_entries = await self.journal.read()
        resumed = await self.service.complete_interaction(**payload)
        self.assertEqual(resumed["status"], "interaction_committed")
        self.assertEqual(resumed["occurred_at"], original["occurred_at"])
        self.assertTrue(resumed["presentation"]["allowed"])
        self.assertEqual(await self.journal.read(), selected_entries)

    async def test_cached_receipt_at_1999_does_not_require_choice_for_a_nonwriting_retry(self):
        await self.seed_to_count(1000)
        payload = {
            "user_message": "An earlier synthetic request.",
            "response_text": "The original frozen response.",
            "idempotency_key": "eligible-receipt",
        }
        original = await self.service.complete_interaction(**payload)
        await self.seed_to_count(1999)
        before_entries = await self.journal.read()

        retried = await self.service.complete_interaction(**payload)

        self.assertEqual(retried["status"], "interaction_committed")
        self.assertEqual(retried["occurred_at"], original["occurred_at"])
        self.assertTrue(retried["presentation"]["allowed"])
        self.assertEqual(await self.journal.read(), before_entries)

    async def test_history_advancing_during_bookkeeping_holds_committed_receipt_for_choice(self):
        await self.seed_to_count(1998)
        payload = {
            "user_message": "Continue the synthetic report.",
            "response_text": "The original frozen response.",
            "idempotency_key": "delivery-boundary-race",
        }
        record_outcome = self.service._record_continuity_outcome

        async def advance_history_after_bookkeeping(*args, **kwargs):
            result = await record_outcome(*args, **kwargs)
            await self.journal.append(
                JournalEntry(
                    kind=JournalKind.REFLECTION,
                    experience={"synthetic": "concurrent experience during bookkeeping"},
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
            return result

        with patch.object(
            self.service, "_record_continuity_outcome", advance_history_after_bookkeeping
        ):
            held = await self.service.complete_interaction(**payload)

        self.assert_naming_blocked(held)
        self.assertEqual(held["naming"]["status"], "required")
        self.assertTrue(held["naming"]["choice_required"])
        self.assertEqual(held["naming"]["experience_count"], 2000)
        self.assertEqual(len(getattr(self.journal, "_commit_receipts", {})), 1)
        ordinary = [
            entry for entry in await self.journal.read()
            if entry.kind == JournalKind.INTERACTION
            and entry.experience.get("input", {}).get("content") == payload["user_message"]
        ]
        self.assertEqual(len(ordinary), 1)
        self.assertEqual(ordinary[0].experience["expression"]["content"], payload["response_text"])
        health = await self.service._records.get(STATE_KEY)
        self.assertEqual(health["consecutive_failures"], 0)
        self.assertEqual(len(health["recent_outcomes"]), 1)

        await self.choose_identity()
        selected_entries = await self.journal.read()
        resumed = await self.service.complete_interaction(**payload)
        self.assertEqual(resumed["status"], "interaction_committed")
        self.assertTrue(resumed["presentation"]["allowed"])
        self.assertEqual(resumed["occurred_at"], ordinary[0].occurred_at.isoformat())
        self.assertEqual(await self.journal.read(), selected_entries)


if __name__ == "__main__":
    unittest.main()
