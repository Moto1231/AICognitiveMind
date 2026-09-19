import unittest

from aicognitive_mind.api import STATIC_DIR, _journal_summary, app
from aicognitive_mind.domain import JournalEntry, JournalKind


class PortalTests(unittest.TestCase):
    def test_portal_assets_are_packaged_and_routes_are_registered(self) -> None:
        index = STATIC_DIR / "index.html"
        stylesheet = STATIC_DIR / "portal.css"
        script = STATIC_DIR / "portal.js"

        self.assertTrue(index.is_file())
        self.assertTrue(stylesheet.is_file())
        self.assertTrue(script.is_file())

        markup = index.read_text(encoding="utf-8")
        self.assertIn("Administration", markup)
        self.assertIn("MCP", markup)
        self.assertIn("MEMORY INSPECTOR", markup)
        self.assertIn("Raw Record Returned by the Mind", markup)

        script_text = script.read_text(encoding="utf-8")
        self.assertIn("JSON.stringify(memory, null, 2)", script_text)
        self.assertIn("memory.grounding", script_text)
        self.assertIn("memory.associations", script_text)
        self.assertIn("adminMemorySearch", script_text)
        self.assertIn("saveMemoryEdit", script_text)
        self.assertIn("memoryMatches", script_text)
        self.assertIn("Journal Timeline", markup)
        self.assertIn("JOURNAL INSPECTOR", markup)
        self.assertIn("renderJournalList", script_text)
        self.assertIn("openJournalInspector", script_text)

        paths = {route.path for route in app.routes}
        self.assertIn("/", paths)
        self.assertIn("/v1/portal/status", paths)
        self.assertIn("/v1/admin/status", paths)
        self.assertIn("/v1/admin/memory", paths)
        self.assertIn("/v1/portal/journal", paths)
        self.assertIn("/v1/portal/journal/detail", paths)

    def test_interaction_journal_summary_is_compact(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={
                "input": {"content": "When is my birthday?"},
                "expression": {"content": "Your birthday is February 7."},
                "memory_steward": {"large": {"nested": "trace"}},
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Interaction")
        self.assertEqual(summary["preview"], "When is my birthday?")
        self.assertIn("February 7", summary["search_text"])
        self.assertNotIn("memory_steward", summary)

    def test_memory_revision_summary_exposes_before_and_after_text(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.MEMORY_REVISION,
            experience={
                "source": "human_administrator",
                "before": {"content": "The User's birthday is February 7."},
                "after": {"content": "Will's birthday is February 7."},
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Memory Revision")
        self.assertEqual(summary["preview"], "Will's birthday is February 7.")
        self.assertIn("The User's birthday", summary["search_text"])


if __name__ == "__main__":
    unittest.main()
