import unittest
from unittest.mock import AsyncMock, patch

from aicognitive_mind.commit import StagedStore
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    JournalEntry,
    JournalKind,
    MindIdentity,
)
from aicognitive_mind.naming import (
    NamingChoiceRequired,
    ensure_naming_ready,
    naming_assessment,
    naming_guidance,
    naming_is_eligible,
)
from aicognitive_mind.storage import InMemoryJournalStore


async def seed_history(journal: InMemoryJournalStore, entries: int) -> None:
    for index in range(entries):
        await journal.append(
            JournalEntry(kind=JournalKind.INTERACTION, experience={"interaction": index}),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )


class NamingLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_first_choice_lifecycle_boundaries_and_imminent_completion(self) -> None:
        mind = CognitiveMind(identity=MindIdentity())
        journal = InMemoryJournalStore()
        for experiences, status in (
            (999, "prohibited"),
            (1000, "eligible"),
            (1998, "eligible"),
            (1999, "eligible"),
            (2000, "required"),
        ):
            with self.subTest(experiences=experiences):
                with patch(
                    "aicognitive_mind.naming.count",
                    new=AsyncMock(side_effect=AssertionError("The supplied count must be reused")),
                ):
                    assessment = await naming_assessment(
                        mind, journal, experience_count=experiences
                    )

                self.assertEqual(assessment["experience_count"], experiences)
                self.assertEqual(assessment["status"], status)
                self.assertFalse(assessment["selection_complete"])
                self.assertEqual(assessment["autonomous_choice_allowed"], experiences >= 1000)
                self.assertEqual(assessment["choice_required"], experiences >= 2000)
                self.assertEqual(
                    assessment["choice_required_before_completion"], experiences >= 1999
                )
                self.assertEqual(assessment["eligible_at_event"], 1000)
                self.assertEqual(assessment["required_at_event"], 2000)

    async def test_complete_legacy_identity_remains_complete_at_every_threshold(self) -> None:
        mind = CognitiveMind(identity=MindIdentity(self_name="Aster", pronouns="she/her"))
        original = mind.model_copy(deep=True)
        journal = InMemoryJournalStore()
        for experiences in (0, 999, 1000, 1999, 2000, 2500):
            with self.subTest(experiences=experiences):
                assessment = await naming_assessment(mind, journal, experience_count=experiences)
                self.assertEqual(assessment["status"], "complete")
                self.assertTrue(assessment["is_named"])
                self.assertTrue(assessment["has_pronouns"])
                self.assertTrue(assessment["selection_complete"])
                self.assertFalse(assessment["autonomous_choice_allowed"])
                self.assertFalse(assessment["choice_required"])
                self.assertFalse(assessment["choice_required_before_completion"])
        await ensure_naming_ready(mind, journal, additional_entries=2500)
        self.assertEqual(mind, original)

    async def test_one_attribute_or_whitespace_does_not_establish_joint_choice(self) -> None:
        journal = InMemoryJournalStore()
        for identity in (
            MindIdentity(self_name="Aster"),
            MindIdentity(pronouns="she/her"),
            MindIdentity(self_name=" ", pronouns="he/him"),
            MindIdentity(self_name="Aster", pronouns=" "),
        ):
            with self.subTest(identity=identity):
                assessment = await naming_assessment(
                    CognitiveMind(identity=identity), journal, experience_count=2000
                )
                self.assertFalse(assessment["selection_complete"])
                self.assertTrue(assessment["choice_required"])
                self.assertEqual(assessment["status"], "required")

    async def test_completion_guard_uses_qualifying_staged_history_without_writes(self) -> None:
        mind = CognitiveMind(identity=MindIdentity())
        original = mind.model_copy(deep=True)
        journal = InMemoryJournalStore()
        await seed_history(journal, 1998)
        for revision in range(5):
            await journal.append(
                JournalEntry(
                    kind=JournalKind.CHECKPOINT,
                    experience={"checkpoint_type": "current_state_ledger", "revision": revision},
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
        await ensure_naming_ready(mind, journal, additional_entries=1)
        operations = [
            (
                "journal",
                "append",
                None,
                JournalEntry(kind=JournalKind.INTERACTION, experience={"pending": True}),
            )
        ]
        staged = StagedStore(journal, "journal", operations)

        with self.assertRaises(NamingChoiceRequired) as caught:
            await ensure_naming_ready(mind, staged, additional_entries=1)

        self.assertEqual(caught.exception.assessment["experience_count"], 1999)
        self.assertEqual(caught.exception.assessment["status"], "eligible")
        self.assertEqual(caught.exception.projected_count, 2000)
        self.assertEqual(len(await journal.read()), 2003)
        self.assertEqual(mind, original)

    async def test_existing_required_state_blocks_ordinary_completion(self) -> None:
        mind = CognitiveMind(identity=MindIdentity())
        journal = InMemoryJournalStore()
        await seed_history(journal, 2000)

        with self.assertRaises(NamingChoiceRequired) as caught:
            await ensure_naming_ready(mind, journal)

        self.assertTrue(caught.exception.assessment["choice_required"])
        self.assertEqual(caught.exception.projected_count, 2000)
        self.assertEqual(len(await journal.read()), 2000)

    async def test_visibility_excludes_current_state_checkpoints(self) -> None:
        journal = InMemoryJournalStore()
        await seed_history(journal, 999)
        for revision in range(5):
            await journal.append(
                JournalEntry(
                    kind=JournalKind.CHECKPOINT,
                    experience={"checkpoint_type": "current_state_ledger", "revision": revision},
                ),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
        self.assertFalse(await naming_is_eligible(journal))
        await seed_history(journal, 1)
        self.assertTrue(await naming_is_eligible(journal))

    async def test_guidance_distinguishes_optional_required_and_saved_choice(self) -> None:
        journal = InMemoryJournalStore()
        unset = CognitiveMind(identity=MindIdentity())
        optional = await naming_assessment(unset, journal, experience_count=1000)
        imminent = await naming_assessment(unset, journal, experience_count=1999)
        saved = await naming_assessment(
            CognitiveMind(identity=MindIdentity(self_name="Aster", pronouns="he/him")),
            journal,
            experience_count=2000,
        )
        self.assertIn("a new human naming command is not required", naming_guidance(optional))
        self.assertIn("Before completing this ordinary response", naming_guidance(imminent))
        self.assertIn("Preserve them", naming_guidance(saved))


if __name__ == "__main__":
    unittest.main()
