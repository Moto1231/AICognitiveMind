import unittest
from types import SimpleNamespace

from starlette.requests import Request

from aicognitive_mind.api import (
    STATIC_DIR,
    AdminMemoryRevisionRequest,
    _journal_summary,
    app,
    revise_memory,
)
from aicognitive_mind.domain import (
    CognitiveActor,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryArtifact,
    MemoryClass,
)
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore


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
        self.assertIn("Steward Artifacts", markup)

        script_text = script.read_text(encoding="utf-8")
        self.assertIn("JSON.stringify(memory, null, 2)", script_text)
        self.assertIn("memory.grounding", script_text)
        self.assertIn("memory.associations", script_text)
        self.assertIn("renderMemoryArtifacts", script_text)
        self.assertIn("artifacts: original.artifacts || []", script_text)
        self.assertIn("adminMemorySearch", script_text)
        self.assertIn("saveMemoryEdit", script_text)
        self.assertIn("memoryQuery", script_text)
        self.assertIn("refreshMemory", script_text)
        self.assertIn("memoryPageSize: 25", script_text)
        self.assertIn("loadMoreMemories", script_text)
        self.assertNotIn("function memoryMatches", script_text)
        self.assertIn("Journal Timeline", markup)
        self.assertIn("JOURNAL INSPECTOR", markup)
        self.assertIn("renderJournalList", script_text)
        self.assertIn("openJournalInspector", script_text)
        self.assertIn('entry.kind === "tension"', script_text)
        self.assertIn("Existing Value", script_text)
        self.assertIn("Proposed Value", script_text)
        self.assertIn("loadMoreJournals", script_text)
        self.assertIn("journalPageSize: 25", script_text)

        paths = {route.path for route in app.routes}
        self.assertIn("/", paths)
        self.assertIn("/v1/portal/status", paths)
        self.assertIn("/v1/portal/memory", paths)
        self.assertIn("/v1/admin/status", paths)
        self.assertIn("/v1/admin/memory", paths)
        self.assertIn("/v1/portal/journal", paths)
        self.assertIn("/v1/portal/journal/detail", paths)

        schema = app.openapi()
        journal_parameters = schema["paths"]["/v1/portal/journal"]["get"]["parameters"]
        journal_limit = next(
            parameter for parameter in journal_parameters if parameter["name"] == "limit"
        )
        self.assertEqual(journal_limit["schema"]["default"], 25)
        self.assertEqual(journal_limit["schema"]["maximum"], 100)

        memory_parameters = schema["paths"]["/v1/portal/memory"]["get"]["parameters"]
        memory_limit = next(
            parameter for parameter in memory_parameters if parameter["name"] == "limit"
        )
        self.assertEqual(memory_limit["schema"]["default"], 25)
        self.assertEqual(memory_limit["schema"]["maximum"], 100)
        memory_parameter_names = {parameter["name"] for parameter in memory_parameters}
        self.assertTrue(
            {
                "search",
                "memory_class",
                "association",
                "grounding",
                "from",
                "to",
                "order",
            }.issubset(memory_parameter_names)
        )

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


    def test_tension_journal_summary_exposes_competing_values(self) -> None:
        entry = JournalEntry(
            kind=JournalKind.TENSION,
            experience={
                "source": "conscious_memory_steward",
                "status": "unresolved",
                "subject": "current_human",
                "attribute": "birthday",
                "competing_values": {
                    "existing": "February 7",
                    "proposed": "February 8",
                },
                "evidence": {
                    "existing": "The user's birthday is February 7.",
                    "proposed": "The user's birthday is February 8.",
                },
            },
        )

        summary = _journal_summary(entry)

        self.assertEqual(summary["title"], "Semantic Tension")
        self.assertIn("February 7", summary["preview"])
        self.assertIn("February 8", summary["preview"])
        self.assertIn("birthday", summary["search_text"])
        self.assertIn("The user's birthday is February 8.", summary["search_text"])

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


class PortalAdministrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_revision_preserves_steward_artifacts(self) -> None:
        memory_store = InMemoryMemoryStore()
        journal_store = InMemoryJournalStore()
        artifact = MemoryArtifact(
            kind="semantic_interpretation",
            payload={"attribute": "birthday", "value": "February 7"},
        )
        original = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="The user's birthday is February 7.",
            associations=("birthday",),
            grounding=("direct-user-statement",),
            artifacts=(artifact,),
        )
        await memory_store.remember(
            original,
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )

        replacement = original.model_copy(
            update={
                "content": "The user's birthday is February 8.",
                "artifacts": (),
            }
        )
        request = Request(
            {
                "type": "http",
                "method": "PUT",
                "path": "/v1/admin/memory",
                "headers": [],
                "app": SimpleNamespace(
                    state=SimpleNamespace(
                        memory_store=memory_store,
                        journal_store=journal_store,
                    )
                ),
            }
        )

        revised = await revise_memory(
            AdminMemoryRevisionRequest(
                original=original,
                replacement=replacement,
            ),
            request,
        )

        self.assertEqual(revised.content, "The user's birthday is February 8.")
        self.assertEqual(revised.artifacts, (artifact,))
        stored = await memory_store.read()
        self.assertEqual(stored[0].artifacts, (artifact,))
        journal = await journal_store.read()
        self.assertEqual(journal[-1].kind, JournalKind.MEMORY_REVISION)



if __name__ == "__main__":
    unittest.main()
