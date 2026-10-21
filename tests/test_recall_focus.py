import unittest
from unittest.mock import AsyncMock, patch

from aicognitive_mind.domain import (
    CognitiveMind, DurableMemory, JournalEntry, JournalKind, MemoryClass, MindIdentity,
)
from aicognitive_mind.memory_steward import MemoryStewardTool, _needs_recent_context, _tokens
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore


MENTIONS = (
    "[@Axiom](plugin://axiom-mind@axiom-local) "
    r"[$axiom-continuity](C:\Users\Example\.codex\skills\axiom-continuity\SKILL.md) "
    "[@GitHub](plugin://github@openai-curated-remote) "
    "[@Render](app://render-connector) "
)


class RecallFocusTests(unittest.IsolatedAsyncioTestCase):
    def test_interface_mentions_do_not_become_search_terms(self) -> None:
        self.assertEqual(_tokens(MENTIONS + "Testing axiom"), {"testing", "axiom"})
        self.assertTrue(_needs_recent_context(MENTIONS + "contine"))

    def test_visible_link_labels_and_explicit_interface_subjects_remain(self) -> None:
        self.assertEqual(
            _tokens("Repair [Mongo retrieval](https://example.test/codex/users/skills)."),
            {"repair", "mongo", "retrieval"},
        )
        self.assertEqual(_tokens("Compare Codex plugin tools"), {"compare", "codex", "plugin", "tools"})
        self.assertIn("cognitive", _tokens("[Cognitive Mind](https://example.test/project_(one))"))

    async def test_recall_preserves_original_focus_and_avoids_identical_second_queries(self) -> None:
        original = MENTIONS + "continue"
        journal = InMemoryJournalStore()
        memory = InMemoryMemoryStore()
        recent = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"input": {"content": "Repair journal retrieval latency"}},
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Axiom")),
            input_text=original, memory=memory, journal=journal,
        )
        candidate_read = AsyncMock(side_effect=[[recent], [], []])
        with patch("aicognitive_mind.retrieval.candidates", candidate_read):
            brief = await tool.invoke({"action": "recall", "focus": original})

        self.assertEqual(brief["context"]["focus"], original)
        self.assertEqual(candidate_read.await_count, 3)
        terms = candidate_read.await_args_list[1].args[1]
        self.assertIn("latency", terms)
        self.assertNotIn("plugin", terms)
        self.assertNotIn("users", terms)

    async def test_new_memory_association_still_triggers_expanded_search(self) -> None:
        journal = InMemoryJournalStore()
        memory = InMemoryMemoryStore()
        remembered = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="Journal retrieval has a latency issue.", associations=("MongoDB",),
        )
        tool = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="Axiom")),
            input_text="Repair journal latency", memory=memory, journal=journal,
        )
        candidate_read = AsyncMock(side_effect=[[], [remembered], [], [remembered], []])
        with patch("aicognitive_mind.retrieval.candidates", candidate_read):
            await tool.invoke({"action": "recall", "focus": "Repair journal latency"})
        self.assertEqual(candidate_read.await_count, 5)
        self.assertIn("mongodb", candidate_read.await_args_list[3].args[1])


if __name__ == "__main__":
    unittest.main()
