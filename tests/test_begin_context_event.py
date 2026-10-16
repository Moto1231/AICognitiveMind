import unittest

from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.state_context import CurrentStateLedger
from aicognitive_mind.storage import (
    InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore,
)


class BeginContextTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mind = InMemoryMindStore()
        self.journal = InMemoryJournalStore()
        self.memory = InMemoryMemoryStore()
        self.service = CognitiveMcpService(self.mind, self.journal, self.memory)
        await self.service.initialize("Axiom", ("Preserve continuity of identity",))

    async def test_first_connection_publishes_begin_context_once(self):
        first = await self.service.begin_interaction("Hello.")
        state = first["current_state"]
        self.assertEqual(state["last_event"], "begin_context")
        self.assertEqual(state["fields"]["identity"]["value"]["self_name"], "Axiom")
        self.assertEqual(state["fields"]["mood"]["status"], "unknown")
        self.assertEqual(state["fields"]["who_is_speaking"]["status"], "unknown")
        second = await self.service.begin_interaction("Continue.", {"summary": "New topic"})
        self.assertEqual(second["current_state"]["last_event"], "interaction_started")
        self.assertEqual(second["current_state"]["fields"]["current_context"]["value"], "New topic")

    async def test_identity_may_not_be_blanked(self):
        ledger = CurrentStateLedger.empty()
        with self.assertRaises(ValueError):
            ledger.invalidate("identity", event="speaker_changed")
        with self.assertRaises(ValueError):
            ledger.apply_event("state_refreshed", {"invalidate": ["identity"]})
