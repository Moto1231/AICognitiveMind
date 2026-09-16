import unittest

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.foundation import CONSCIOUS_WORKSPACE_FOUNDATION_KEY
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryFoundationStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class FoundationTests(unittest.IsolatedAsyncioTestCase):
    async def test_revisions_preserve_history_and_activate_latest_version(self) -> None:
        foundation = InMemoryFoundationStore()
        first = await foundation.seed(
            CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
            "Version one",
        )
        second = await foundation.revise(
            CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
            "Version two",
            changed_by="administrator",
        )

        history = await foundation.read_history(CONSCIOUS_WORKSPACE_FOUNDATION_KEY)
        active = await foundation.load_active(CONSCIOUS_WORKSPACE_FOUNDATION_KEY)

        self.assertEqual(first.version, 1)
        self.assertEqual(second.version, 2)
        self.assertEqual([record.version for record in history], [1, 2])
        self.assertFalse(history[0].active)
        self.assertTrue(history[1].active)
        self.assertEqual(active, history[1])

    async def test_core_uses_active_foundation_without_code_change(self) -> None:
        foundation = InMemoryFoundationStore()
        await foundation.seed(
            CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
            "Version one",
        )
        await foundation.revise(
            CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
            "Version two",
            changed_by="administrator",
        )
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            foundation=foundation,
            journal=InMemoryJournalStore(),
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=EchoReasoningEngine(),
        )
        await core.initialize("Genesis")

        result = await core.interact("Hello")

        self.assertEqual(result.response_text, "I heard: Hello")
        active = await foundation.load_active(CONSCIOUS_WORKSPACE_FOUNDATION_KEY)
        self.assertIsNotNone(active)
        self.assertEqual(active.content, "Version two")


if __name__ == "__main__":
    unittest.main()
