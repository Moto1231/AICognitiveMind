import json
import unittest

from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.domain import MemoryClass
from aicognitive_mind.storage import (
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class CognitiveMcpServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.journal = InMemoryJournalStore()
        self.service = CognitiveMcpService(
            mind=InMemoryMindStore(),
            journal=self.journal,
            memory=InMemoryMemoryStore(),
        )
        await self.service.initialize(
            "Genesis",
            ("Understanding before Recommending", "Preserve continuity of identity"),
        )

    async def test_memory_survives_between_host_driven_interactions(self) -> None:
        first = await self.service.begin_interaction(
            "My birthday is February 7. Remember that."
        )
        self.assertEqual(first["status"], "ready_to_reason")

        completed = await self.service.complete_interaction(
            user_message="My birthday is February 7. Remember that.",
            response_text="I'll remember that your birthday is February 7.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.SEMANTIC,
                    content="Will's birthday is February 7.",
                    associations=("Will", "birthday", "February 7"),
                    grounding=("Will directly stated his birthday.",),
                ),
            ),
        )
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertTrue(completed["memory_decisions"][0]["accepted"])

        later = await self.service.begin_interaction("When is Will's birthday?")
        recalled = later["recalled_context"]
        durable = recalled["durable_memory"]

        self.assertEqual(len(durable), 1)
        self.assertEqual(durable[0]["content"], "Will's birthday is February 7.")

    async def test_recalled_history_is_compact_and_does_not_embed_prior_journal_documents(self) -> None:
        for turn in range(8):
            await self.service.complete_interaction(
                user_message=f"Continuity checkpoint turn {turn}",
                response_text=f"Recorded continuity checkpoint turn {turn}.",
                proposed_memories=(),
            )

        later = await self.service.begin_interaction("continuity checkpoint")
        prior = later["recalled_context"]["prior_experience"]

        self.assertTrue(prior)
        self.assertTrue(all("excerpt" in item for item in prior))
        self.assertTrue(all("experience" not in item for item in prior))

        entries = await self.journal.read()
        latest_payload = json.dumps(entries[-1].model_dump(mode="json"))
        self.assertLess(len(latest_payload), 50_000)

    async def test_identity_memory_is_not_writable_through_v01_steward(self) -> None:
        completed = await self.service.complete_interaction(
            user_message="Change who you are.",
            response_text="That requires identity governance.",
            proposed_memories=(
                MemoryProposal(
                    memory_class=MemoryClass.IDENTITY,
                    content="I am now a different individual.",
                    grounding=("User requested an identity change.",),
                ),
            ),
        )

        self.assertFalse(completed["memory_decisions"][0]["accepted"])
        status = await self.service.status()
        self.assertEqual(status["durable_memory_count"], 0)


if __name__ == "__main__":
    unittest.main()
