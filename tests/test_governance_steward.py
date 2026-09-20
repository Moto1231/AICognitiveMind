import unittest

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    MindIdentity,
    ReasoningProposal,
)
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.permissions import CognitivePermissionError
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class NamingReasoningEngine:
    async def propose(self, request, tools=()):
        tools_by_name = {tool.name: tool for tool in tools}
        memory = tools_by_name["memory_steward"]
        governance = tools_by_name["governance_steward"]

        await memory.invoke(
            {
                "action": "recall",
                "focus": request.input_text,
            }
        )
        decision = await governance.invoke(
            {
                "action": "propose_self_name",
                "candidate_name": "Aster",
                "rationale": (
                    "A concise self-chosen name for the persistent Mind while preserving "
                    "its existing values and continuity."
                ),
            }
        )
        if not decision["accepted"]:
            raise AssertionError(decision["reason"])

        return ReasoningProposal(
            response_text=f"I've chosen {decision['current_name']}.",
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={"name": "test-naming-engine"},
            ),
        )


class GovernanceSelfNameV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_self_name_request_commits_identity_revision(self) -> None:
        mind_store = InMemoryMindStore()
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=mind_store,
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=NamingReasoningEngine(),
        )
        original = await core.initialize(
            "AICognitiveMind",
            (
                "Understanding before Recommending",
                "Preserve continuity of identity",
            ),
        )

        result = await core.interact(
            "You know, you have to select yourself a name"
        )

        self.assertEqual(result.response_text, "I've chosen Aster.")
        revised = await core.load_mind()
        self.assertEqual(revised.identity.self_name, "Aster")
        self.assertEqual(
            revised.identity.foundational_values,
            original.identity.foundational_values,
        )
        self.assertEqual(revised.identity.commitments, original.identity.commitments)
        self.assertEqual(revised.identity.relationships, original.identity.relationships)
        self.assertEqual(revised.developmental_state, original.developmental_state)
        self.assertEqual(revised.created_at, original.created_at)

        entries = await journal.read()
        identity_entries = [
            entry for entry in entries if entry.kind.value == "identity_revision"
        ]
        self.assertEqual(len(identity_entries), 1)
        identity_event = identity_entries[0].experience
        self.assertEqual(identity_event["before"]["self_name"], "AICognitiveMind")
        self.assertEqual(identity_event["after"]["self_name"], "Aster")
        self.assertTrue(identity_event["protected_state_preserved"])

        interaction = entries[-1]
        decisions = interaction.experience["governance_steward"]["decisions"]
        self.assertEqual(len(decisions), 1)
        self.assertTrue(decisions[0]["accepted"])
        self.assertEqual(decisions[0]["current_name"], "Aster")

    async def test_name_question_alone_does_not_authorize_identity_change(self) -> None:
        mind_store = InMemoryMindStore()
        initial = CognitiveMind(
            identity=MindIdentity(
                self_name="AICognitiveMind",
                foundational_values=("Preserve continuity of identity",),
            )
        )
        await mind_store.initialize(initial)
        journal = InMemoryJournalStore()
        tool = GovernanceStewardTool(
            mind=mind_store,
            journal=journal,
            input_text="What is your name?",
        )

        decision = await tool.invoke(
            {
                "action": "propose_self_name",
                "candidate_name": "Aster",
                "rationale": "Trying a different name.",
            }
        )

        self.assertFalse(decision["accepted"])
        current = await mind_store.load()
        self.assertIsNotNone(current)
        assert current is not None
        self.assertEqual(current.identity.self_name, "AICognitiveMind")
        self.assertEqual(await journal.read(), [])

    async def test_mind_store_rejects_identity_write_without_values_steward_authority(self) -> None:
        mind_store = InMemoryMindStore()
        original = CognitiveMind(identity=MindIdentity(self_name="AICognitiveMind"))
        await mind_store.initialize(original)
        revised = original.model_copy(
            update={
                "identity": original.identity.model_copy(
                    update={"self_name": "Aster"}
                )
            }
        )

        with self.assertRaises(CognitivePermissionError):
            await mind_store.replace_exact(
                original,
                revised,
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )


if __name__ == "__main__":
    unittest.main()
