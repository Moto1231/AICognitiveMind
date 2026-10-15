import unittest

from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.storage import (
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class CurrentStateServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.journal = InMemoryJournalStore()
        self.service = CognitiveMcpService(
            mind=InMemoryMindStore(),
            journal=self.journal,
            memory=InMemoryMemoryStore(),
        )
        await self.service.initialize(
            "Axiom",
            ("Understanding before Recommending", "Preserve continuity of identity"),
        )

    async def test_begin_restores_identity_topic_and_persists_ledger(self) -> None:
        begun = await self.service.begin_interaction(
            "Continue the state ledger work.",
            {
                "summary": "Implement Axiom's current-state ledger",
                "participants": [{
                    "participant_id": "human",
                    "name": "Human",
                    "identity_status": "confirmed",
                    "presence_status": "reported",
                    "grounding": ["current conversation"],
                }],
                "active_speaker": "human",
                "addressee": "human",
                "unresolved_references": ["Implement event-driven invalidation"],
            },
        )

        state = begun["current_state"]
        self.assertEqual(state["fields"]["identity"]["value"]["self_name"], "Axiom")
        self.assertEqual(
            state["fields"]["active_topic"]["value"],
            "Implement Axiom's current-state ledger",
        )
        self.assertEqual(state["fields"]["interlocutor"]["status"], "current")
        persisted = await self.service.read_current_state()
        self.assertEqual(persisted["revision"], state["revision"])

    async def test_events_invalidate_only_affected_fields_and_survive_new_state(self) -> None:
        await self.service.begin_interaction("Start.")
        await self.service.update_current_state(
            "location_changed",
            {
                "values": {
                    "locality": {
                        "value": {"place": "User-confirmed location"},
                        "source": "explicit user statement",
                    }
                }
            },
        )
        await self.service.update_current_state("topic_changed")
        after_event = await self.service.read_current_state()
        self.assertEqual(
            after_event["fields"]["locality"]["value"],
            {"place": "User-confirmed location"},
        )
        self.assertEqual(after_event["fields"]["active_topic"]["status"], "unknown")
        self.assertEqual(after_event["fields"]["identity"]["value"]["self_name"], "Axiom")

        next_state = await self.service.begin_interaction(
            "Continue.",
            {"summary": "Continue the architecture implementation"},
        )
        self.assertEqual(
            next_state["current_state"]["fields"]["locality"]["value"],
            {"place": "User-confirmed location"},
        )
        self.assertEqual(
            next_state["current_state"]["fields"]["active_topic"]["value"],
            "Continue the architecture implementation",
        )


if __name__ == "__main__":
    unittest.main()
