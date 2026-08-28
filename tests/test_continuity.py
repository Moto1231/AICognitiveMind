import unittest

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import CognitiveActor, DurableMemory, JournalKind, MemoryClass
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
    MindAlreadyInitializedError,
)


class ContinuityTests(unittest.IsolatedAsyncioTestCase):
    async def test_one_instance_has_one_mind(self) -> None:
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=InMemoryJournalStore(),
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=EchoReasoningEngine(),
        )
        await core.initialize("Genesis", ("understanding-before-recommending",))

        with self.assertRaises(MindAlreadyInitializedError):
            await core.initialize("Someone Else")

    async def test_identity_and_journal_survive_engine_swap(self) -> None:
        mind_store = InMemoryMindStore()
        journal = InMemoryJournalStore()
        diagnostics = InMemoryDiagnosticStore()
        memory = InMemoryMemoryStore()

        core_a = CognitiveCore(
            mind=mind_store,
            journal=journal,
            memory=memory,
            diagnostics=diagnostics,
            engine=EchoReasoningEngine(diagnostic_name="engine-a", prefix="A considered"),
        )
        mind = await core_a.initialize(
            self_name="Genesis",
            foundational_values=("understanding-before-recommending",),
        )
        first = await core_a.interact("Remember how we began.")

        core_b = CognitiveCore(
            mind=mind_store,
            journal=journal,
            memory=memory,
            diagnostics=diagnostics,
            engine=EchoReasoningEngine(diagnostic_name="engine-b", prefix="B considered"),
        )
        second = await core_b.interact("Who is thinking now?")

        restored = await core_b.load_mind()
        entries = await core_b.read_journal()
        observations = await diagnostics.read()

        self.assertEqual(restored, mind)
        self.assertEqual(first.response_text, "A considered: Remember how we began.")
        self.assertEqual(second.response_text, "B considered: Who is thinking now?")
        self.assertEqual(
            [entry.kind for entry in entries],
            [JournalKind.INITIALIZATION, JournalKind.INTERACTION, JournalKind.INTERACTION],
        )
        self.assertNotIn("engine-a", str([entry.model_dump() for entry in entries]))
        self.assertNotIn("engine-b", str([entry.model_dump() for entry in entries]))
        self.assertEqual(
            [observation.implementation["name"] for observation in observations],
            ["engine-a", "engine-b"],
        )

    async def test_cognitive_documents_have_no_domain_identifiers(self) -> None:
        memory = InMemoryMemoryStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=InMemoryJournalStore(),
            memory=memory,
            diagnostics=InMemoryDiagnosticStore(),
            engine=EchoReasoningEngine(),
        )
        mind = await core.initialize("Genesis")
        await memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="mir.ai Technology contains the Digital Genesis framework.",
                associations=("mir.ai Technology", "Digital Genesis"),
                grounding=("established-project-context",),
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        await core.interact("Hello.")
        journal = await core.read_journal()
        memories = await core.read_memory()

        cognitive_documents = [
            mind.model_dump(),
            *[entry.model_dump() for entry in journal],
            *[memory.model_dump() for memory in memories],
        ]
        identifier_keys = {
            key
            for document in cognitive_documents
            for key in self._all_keys(document)
            if key == "id" or key.endswith("_id")
        }
        self.assertEqual(identifier_keys, set())

    def _all_keys(self, value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {
                nested_key
                for nested_value in value.values()
                for nested_key in self._all_keys(nested_value)
            }
        if isinstance(value, (list, tuple)):
            return {
                nested_key
                for nested_value in value
                for nested_key in self._all_keys(nested_value)
            }
        return set()


if __name__ == "__main__":
    unittest.main()
