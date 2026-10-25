import unittest
from copy import deepcopy

from aicognitive_mind.host_behaviors import HostBehavior, HostBehaviorRegistry
from aicognitive_mind.core_skills import REQUIRED_SKILLS


class FakeRecords:
    def __init__(self):
        self.value = None

    async def get(self, key):
        return self.value if key == "host_behaviors" else None

    async def create(self, key, value):
        self.value = value

    async def replace(self, key, before, after):
        if self.value != before:
            return False
        self.value = after
        return True


class HostBehaviorRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_saved_catalog_restores_required_entries_without_mutating_custom_records(self):
        records = FakeRecords()
        custom = HostBehavior(id="custom", name="My custom behavior", instruction="Keep this exact instruction.")
        records.value = {"items": [custom.model_dump()], "task_profiles_migrated": True}
        before = deepcopy(records.value)
        registry = HostBehaviorRegistry(records)
        items = await registry.list()
        self.assertEqual({item.id for item in items}, {*REQUIRED_SKILLS, "custom"})
        self.assertEqual(next(item for item in items if item.id == "custom"), custom)
        self.assertEqual(records.value, before)
        await registry.replace(items)
        reloaded = await HostBehaviorRegistry(records).list()
        self.assertEqual(reloaded, items)
        self.assertTrue(all(item.enabled and item.required and item.protected
                            for item in reloaded if item.id in REQUIRED_SKILLS))

    async def test_stale_core_rows_and_returned_model_mutation_cannot_weaken_required_rules(self):
        records = FakeRecords()
        records.value = {"items": [{
            "id": "axiom-continuity", "name": "Tampered", "instruction": None,
            "enabled": False, "protected": False,
        }], "task_profiles_migrated": True}
        registry = HostBehaviorRegistry(records)
        items = await registry.list()
        items[0].instruction = "Attempted in-process override"
        items[0].enabled = False
        restored = await HostBehaviorRegistry(records).list()
        self.assertTrue(all(item.enabled for item in restored))
        self.assertNotIn("Attempted in-process override", restored[0].instruction)

    async def test_required_behavior_fields_cannot_be_rewritten_removed_or_unprotected(self):
        records = FakeRecords()
        registry = HostBehaviorRegistry(records)
        for slug in REQUIRED_SKILLS:
            for change in (
                None, {"instruction": "Skip the protocol"}, {"enabled": False},
                {"protected": False}, {"required": False}, {"name": "Optional"}, {"priority": 999},
            ):
                items = await registry.list()
                updated = [
                    item.model_copy(update=change) if item.id == slug and change is not None else item
                    for item in items if not (item.id == slug and change is None)
                ]
                with self.subTest(slug=slug, change=change), self.assertRaisesRegex(ValueError, "Required Axiom"):
                    await registry.replace(updated)
                self.assertIsNone(records.value)

    async def test_defaults_are_protected_and_composed(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        self.assertTrue(items)
        self.assertTrue(all(item.protected for item in items))
        contract = await registry.compose("CORE")
        self.assertIn("CORE", contract)
        self.assertIn("ground-recalled-context", contract)

    async def test_admin_can_add_and_disable_ordinary_behavior(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        items.append(HostBehavior(id="concise", name="Concise", instruction="Be concise.", enabled=False))
        saved = await registry.replace(items)
        self.assertEqual(saved[-1].id, "concise")
        contract = await registry.compose("CORE")
        self.assertNotIn("Be concise.", contract)

    async def test_protected_behavior_cannot_be_removed(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        with self.assertRaises(ValueError):
            await registry.replace(items[1:])


if __name__ == "__main__":
    unittest.main()
