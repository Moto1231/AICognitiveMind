import unittest
from unittest.mock import patch

from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    JournalEntry,
    JournalKind,
    MindIdentity,
    ReasoningProposal,
)
from aicognitive_mind.naming import NamingChoiceRequired
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


class OrdinaryReasoningEngine:
    def __init__(self, *, choose_identity=False):
        self.choose_identity = choose_identity
        self.messages = []

    async def propose(self, request, tools=()):
        self.messages.append(request.input_text)
        available = {tool.name: tool for tool in tools}
        await available["memory_steward"].invoke({
            "action": "recall", "focus": request.input_text,
        })
        if self.choose_identity:
            chosen = await available["governance_steward"].invoke({
                "action": "propose_self_name",
                "candidate_name": "Aster",
                "candidate_pronouns": "he/him",
                "rationale": "Choosing a name and pronouns while preserving established values.",
            })
            if not chosen["accepted"]:
                raise AssertionError(chosen["reason"])
        return ReasoningProposal(
            response_text="We can continue our ordinary conversation.",
            diagnostic=DiagnosticObservation(
                component="required-naming-test",
                operation="propose_response",
                implementation={"engine": "synthetic"},
            ),
        )


async def core_fixture(experiences, *, choose_identity=False, complete=False):
    mind = InMemoryMindStore()
    original = CognitiveMind(identity=MindIdentity(
        self_name="Existing" if complete else None,
        pronouns="they/them" if complete else None,
        foundational_values=("Understanding before Recommending",),
        commitments=("Preserve continuity",),
        relationships=({"name": "creator", "relationship": "creator"},),
    ))
    await mind.initialize(original)
    journal = InMemoryJournalStore()
    for index in range(experiences):
        await journal.append(
            JournalEntry(kind=JournalKind.INTERACTION, experience={"past_interaction": index}),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
    diagnostics = InMemoryDiagnosticStore()
    engine = OrdinaryReasoningEngine(choose_identity=choose_identity)
    core = CognitiveCore(
        mind=mind,
        journal=journal,
        memory=InMemoryMemoryStore(),
        diagnostics=diagnostics,
        engine=engine,
    )
    return core, mind, journal, diagnostics, engine, original


class CoreRequiredNamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_ordinary_turn_at_1999_cannot_commit_without_first_choice(self):
        core, mind, journal, diagnostics, engine, original = await core_fixture(1999)
        previous_journal = await journal.read()

        with self.assertRaises(NamingChoiceRequired) as caught:
            await core.interact("Explain what we should work on next.")

        self.assertEqual(engine.messages, ["Explain what we should work on next."])
        self.assertEqual(caught.exception.assessment["experience_count"], 1999)
        self.assertEqual(caught.exception.projected_count, 2000)
        self.assertEqual(await mind.load(), original)
        self.assertEqual(await journal.read(), previous_journal)
        self.assertEqual(await diagnostics.read(), [])

    async def test_independent_event_during_diagnostics_withholds_staged_ordinary_turn(self):
        core, mind, journal, diagnostics, _, original = await core_fixture(1998)
        previous_journal = await journal.read()
        independent_event = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"independent_event_during_diagnostics": True},
        )
        record_diagnostic = diagnostics.record

        async def record_while_another_experience_arrives(observation):
            # This writes the base store independently of core.interact's staged turn.
            await journal.append(
                independent_event, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
            await record_diagnostic(observation)

        with (
            patch.object(diagnostics, "record", new=record_while_another_experience_arrives),
            self.assertRaises(NamingChoiceRequired) as caught,
        ):
            await core.interact("Continue our ordinary conversation.")

        self.assertEqual(caught.exception.assessment["experience_count"], 2000)
        self.assertEqual(caught.exception.projected_count, 2000)
        self.assertEqual(await mind.load(), original)
        # The independent experience survives; the staged ordinary reply does not commit.
        self.assertEqual(await journal.read(), [*previous_journal, independent_event])

    async def test_ordinary_turn_can_commit_autonomous_joint_choice_at_deadline(self):
        for experiences in (1999, 2000):
            with self.subTest(experiences=experiences):
                core, mind, journal, _, engine, original = await core_fixture(
                    experiences, choose_identity=True
                )

                result = await core.interact("Explain what we should work on next.")

                self.assertEqual(result.response_text, "We can continue our ordinary conversation.")
                self.assertEqual(engine.messages, ["Explain what we should work on next."])
                revised = await mind.load()
                self.assertIsNotNone(revised)
                self.assertEqual(revised.identity.self_name, "Aster")
                self.assertEqual(revised.identity.pronouns, "he/him")
                self.assertEqual(
                    revised.identity.model_dump(exclude={"self_name", "pronouns"}),
                    original.identity.model_dump(exclude={"self_name", "pronouns"}),
                )
                self.assertEqual(revised.developmental_state, original.developmental_state)
                self.assertEqual(revised.created_at, original.created_at)
                entries = await journal.read()
                self.assertEqual(len(entries), experiences + 2)
                self.assertEqual(entries[-2].kind, JournalKind.IDENTITY_REVISION)
                self.assertEqual(entries[-2].experience["selection_mode"], "initial_choice")
                self.assertEqual(
                    entries[-2].experience["after"], {"self_name": "Aster", "pronouns": "he/him"}
                )
                self.assertEqual(entries[-1].kind, JournalKind.INTERACTION)
                self.assertEqual(
                    entries[-1].experience["input"]["content"],
                    "Explain what we should work on next.",
                )

    async def test_complete_saved_identity_allows_ordinary_turn_without_renaming(self):
        core, mind, journal, _, _, original = await core_fixture(2500, complete=True)

        result = await core.interact("Continue our ordinary conversation.")

        self.assertEqual(result.response_text, "We can continue our ordinary conversation.")
        self.assertEqual(await mind.load(), original)
        entries = await journal.read()
        self.assertEqual(len(entries), 2501)
        self.assertFalse(any(entry.kind == JournalKind.IDENTITY_REVISION for entry in entries))
        self.assertEqual(entries[-1].experience["governance_steward"]["decisions"], [])


if __name__ == "__main__":
    unittest.main()
