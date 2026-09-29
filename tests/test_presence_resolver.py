import unittest
from datetime import UTC, datetime, timedelta

from aicognitive_mind.domain import SensoryEvidenceReference
from aicognitive_mind.presence import PersonIdentity, PresenceResolution
from aicognitive_mind.presence_resolver import PresenceResolver
from aicognitive_mind.body import BodyRuntime
from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.embodiment import MindBodyBridge
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.storage import InMemoryDiagnosticStore, InMemoryEvidenceStore, InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore


CAPTURED = datetime(2026, 9, 27, 7, 0, tzinfo=UTC)


def evidence(modality: str, *, when: datetime = CAPTURED, digest: str = "a") -> SensoryEvidenceReference:
    return SensoryEvidenceReference(
        sha256=digest * 64,
        captured_at=when,
        modality=modality,
        source="unity-camera" if modality == "vision" else "unity-microphone",
        media_type="image/jpeg" if modality == "vision" else "audio/wav",
        byte_length=128,
    )


class FixedInterpreter:
    async def interpret(self, percept, *, focus=None):
        return "Visual perception: a person is present."


class PresenceResolverTests(unittest.TestCase):
    def test_tracks_multiple_people_without_forcing_identity(self) -> None:
        resolver = PresenceResolver()
        resolver.observe("visual:1", evidence=evidence("vision"), observation="Person on left.")
        resolver.observe("visual:2", evidence=evidence("vision", digest="b"), observation="Person on right.")

        active = resolver.active()
        self.assertEqual(set(active), {"visual:1", "visual:2"})
        self.assertTrue(all(p.resolution == PresenceResolution.UNKNOWN for p in active.values()))

    def test_audio_and_visual_evidence_can_accumulate_on_same_presence(self) -> None:
        resolver = PresenceResolver()
        resolver.observe("person:1", evidence=evidence("vision"), observation="A person is visible.")
        resolver.observe("person:1", evidence=evidence("audio", digest="b"), observation="The person is speaking.")

        presence = resolver.active()["person:1"]
        self.assertEqual(len(presence.evidence), 2)
        self.assertEqual({item.modality for item in presence.evidence}, {"vision", "audio"})

    def test_candidate_remains_distinct_from_resolved(self) -> None:
        resolver = PresenceResolver()
        resolver.observe("person:1", evidence=evidence("vision"), observation="Possible known person.")
        will = PersonIdentity(name="Will", relationship="creator", grounding=("human introduction",))

        candidate = resolver.mark_candidate("person:1", will)
        self.assertEqual(candidate.resolution, PresenceResolution.CANDIDATE)

        resolved = resolver.resolve("person:1", will)
        self.assertEqual(resolved.resolution, PresenceResolution.RESOLVED)

    def test_context_is_structured_and_contains_no_raw_media(self) -> None:
        resolver = PresenceResolver()
        resolver.observe("person:1", evidence=evidence("vision"), observation="Known person visible.")
        resolver.resolve(
            "person:1",
            PersonIdentity(name="Will", aliases=("William",), relationship="creator", grounding=("introduced",)),
        )

        context = resolver.context()
        person = context["present_people"][0]
        self.assertEqual(person["resolution"], "resolved")
        self.assertEqual(person["person"]["name"], "Will")
        self.assertEqual(person["modalities"], ["vision"])
        self.assertNotIn("sha256", str(context))
        self.assertNotIn("payload", str(context))

    def test_stale_presence_can_expire_without_erasing_person_identity(self) -> None:
        resolver = PresenceResolver()
        resolver.observe("person:1", evidence=evidence("vision"), observation="Person present.")
        expired = resolver.expire_before(CAPTURED + timedelta(seconds=1))

        self.assertEqual(expired, ("person:1",))
        self.assertEqual(resolver.active(), {})


class PresenceBridgeContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_resolved_presence_reaches_cognitive_interaction_context(self) -> None:
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=EchoReasoningEngine(),
        )
        await core.initialize("Axiom")
        resolver = PresenceResolver()
        resolver.observe("person:1", evidence=evidence("vision"), observation="Known person visible.")
        resolver.resolve(
            "person:1",
            PersonIdentity(name="Will", relationship="creator", grounding=("introduced",)),
        )
        bridge = MindBodyBridge(
            core=core,
            body=BodyRuntime(),
            interpreter=FixedInterpreter(),
            evidence=InMemoryEvidenceStore(),
            journal=journal,
            presence=resolver,
        )

        await bridge.interact("Hello.")

        entries = await journal.read()
        context = entries[-1].experience["input"]["context"]
        self.assertEqual(context["presence"]["present_people"][0]["person"]["name"], "Will")
        self.assertEqual(context["presence"]["present_people"][0]["resolution"], "resolved")


if __name__ == "__main__":
    unittest.main()
