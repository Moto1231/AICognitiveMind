import unittest
from datetime import UTC, datetime

from aicognitive_mind.domain import SensoryEvidenceReference
from aicognitive_mind.presence import PersonIdentity, Presence, PresenceResolution


def evidence(modality: str = "vision") -> SensoryEvidenceReference:
    return SensoryEvidenceReference(
        sha256="a" * 64,
        captured_at=datetime(2026, 9, 27, 6, 45, tzinfo=UTC),
        modality=modality,
        source="unity-camera" if modality == "vision" else "unity-microphone",
        media_type="image/jpeg" if modality == "vision" else "audio/wav",
        byte_length=128,
    )


class PersonPresenceFoundationTests(unittest.TestCase):
    def test_presence_begins_unknown_without_inventing_identity(self) -> None:
        presence = Presence()
        self.assertEqual(presence.resolution, PresenceResolution.UNKNOWN)
        self.assertIsNone(presence.person)

    def test_presence_accumulates_exact_sensory_evidence(self) -> None:
        reference = evidence()
        presence = Presence().with_evidence(
            evidence=reference,
            observation="A person is visible near the camera.",
        )
        self.assertEqual(len(presence.evidence), 1)
        self.assertEqual(presence.evidence[0].evidence.sha256, reference.sha256)
        self.assertEqual(presence.evidence[0].modality, "vision")

    def test_candidate_is_not_treated_as_resolved_identity(self) -> None:
        will = PersonIdentity(
            name="Will",
            relationship="creator",
            grounding=("human introduction",),
        )
        presence = Presence().candidate(will)
        self.assertEqual(presence.resolution, PresenceResolution.CANDIDATE)
        self.assertEqual(presence.person.name, "Will")

    def test_resolution_requires_sensory_evidence(self) -> None:
        will = PersonIdentity(name="Will", grounding=("human introduction",))
        with self.assertRaisesRegex(ValueError, "sensory evidence"):
            Presence().resolve(will)

    def test_resolution_requires_grounded_known_person(self) -> None:
        ungrounded = PersonIdentity(name="Will")
        presence = Presence().with_evidence(
            evidence=evidence("audio"),
            observation="A speaker is audible.",
        )
        with self.assertRaisesRegex(ValueError, "identity grounding"):
            presence.resolve(ungrounded)

    def test_grounded_person_can_resolve_evidence_backed_presence(self) -> None:
        will = PersonIdentity(
            name="Will",
            aliases=("William",),
            relationship="creator",
            grounding=("human introduction", "established relationship memory"),
        )
        presence = Presence().with_evidence(
            evidence=evidence(),
            observation="Known visual identity evidence was observed.",
        ).resolve(will)

        self.assertEqual(presence.resolution, PresenceResolution.RESOLVED)
        self.assertEqual(presence.person.name, "Will")
        self.assertEqual(presence.person.aliases, ("William",))


if __name__ == "__main__":
    unittest.main()
