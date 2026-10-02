import unittest
from datetime import UTC, datetime

from aicognitive_mind.domain import SensoryEvidenceReference
from aicognitive_mind.person_registry import PersonRegistry
from aicognitive_mind.presence import PersonIdentity, Presence


class FakeRecords:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def create(self, key, value):
        if key in self.data:
            raise ValueError("duplicate")
        self.data[key] = value

    async def replace(self, key, before, after):
        if self.data.get(key) != before:
            return False
        self.data[key] = after
        return True


class PersonRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_persists_exact_evidence_across_registry_instances(self):
        records = FakeRecords()
        identity = PersonIdentity(name="Test person", grounding=("confirmed introduction",))
        first = PersonRegistry(records)
        person = await first.remember(identity)
        evidence = SensoryEvidenceReference(
            sha256="b" * 64,
            captured_at=datetime(2026, 10, 2, tzinfo=UTC),
            modality="vision",
            source="test-camera",
            media_type="image/jpeg",
            byte_length=42,
        )
        presence = Presence().with_evidence(
            evidence=evidence, observation="Confirmed visual observation"
        ).resolve(identity)
        linked = await first.link(person.person_id, presence)
        recovered = await PersonRegistry(records).get(person.person_id)
        self.assertEqual(len(linked.encounters), 1)
        self.assertEqual(recovered.encounters[0].evidence[0].sha256, evidence.sha256)
        self.assertEqual(recovered.encounters[0].observations, ("Confirmed visual observation",))

    async def test_rejects_unresolved_and_mismatched_presence(self):
        registry = PersonRegistry(FakeRecords())
        identity = PersonIdentity(name="One", grounding=("introduction",))
        person = await registry.remember(identity)
        with self.assertRaisesRegex(ValueError, "resolved"):
            await registry.link(person.person_id, Presence())
        other = PersonIdentity(name="Two", grounding=("different introduction",))
        evidence = SensoryEvidenceReference(
            sha256="c" * 64,
            captured_at=datetime(2026, 10, 2, tzinfo=UTC),
            modality="audio",
            source="test-microphone",
            media_type="audio/wav",
            byte_length=42,
        )
        presence = Presence().with_evidence(evidence=evidence, observation="Speaker").resolve(other)
        with self.assertRaisesRegex(ValueError, "match"):
            await registry.link(person.person_id, presence)

    async def test_requires_grounded_identity(self):
        with self.assertRaisesRegex(ValueError, "grounding"):
            await PersonRegistry(FakeRecords()).remember(PersonIdentity(name="Unknown"))


if __name__ == "__main__":
    unittest.main()
