import unittest
from copy import deepcopy

from aicognitive_mind.host_behaviors import BehaviorRevisionConflict, HostBehavior, HostBehaviorRegistry
from aicognitive_mind.core_skills import REQUIRED_SKILLS


class FakeRecords:
    def __init__(self):
        self.value = None
        self.assignments = None

    async def get(self, key):
        return self.value if key == "host_behaviors" else self.assignments if key == "task_model_assignments" else None

    async def create(self, key, value):
        self.value = deepcopy(value)

    async def replace(self, key, before, after):
        if self.value != before:
            return False
        self.value = deepcopy(after)
        return True


class HostBehaviorRegistryTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def legacy_factory_marker():
        return HostBehavior(
            id="axiom-continuity", name="Axiom Continuity", priority=0, protected=True, required=True,
            instruction=(
                "Axiom Continuity is required for every Axiom reasoning interaction. "
                "Apply its full packaged protocol supplied in the mandatory reasoning contract, "
                "including fresh instances and follow-ups. Optional task memberships cannot disable it."
            ),
        )

    async def test_only_exact_old_factory_markers_are_reconciled_without_writing_storage(self):
        records = FakeRecords()
        legacy = self.legacy_factory_marker()
        custom = HostBehavior(id="custom", name="Custom", instruction="Keep this authored instruction.")
        records.value = {"items": [legacy.model_dump(), custom.model_dump()], "task_profiles_migrated": True}
        before = deepcopy(records.value)
        items, revision = await HostBehaviorRegistry(records).snapshot()
        self.assertEqual(revision, 0)
        self.assertIn("effective Mind skill configuration", items[0].instruction)
        self.assertNotIn("Optional task memberships cannot disable it", items[0].instruction)
        self.assertEqual(items[1], custom)
        self.assertEqual(records.value, before)

    async def test_admin_saved_or_edited_legacy_marker_text_is_never_migrated(self):
        for metadata, changes in (
            ({"revision": 1, "updated_by": "administrator"}, {}),
            ({}, {"instruction": "My intentional custom rule."}),
            ({}, {"name": "My marker name"}),
            ({}, {"enabled": False}),
        ):
            records = FakeRecords()
            marker = self.legacy_factory_marker().model_copy(update=changes)
            records.value = {"items": [marker.model_dump()], "task_profiles_migrated": True, **metadata}
            with self.subTest(metadata=metadata, changes=changes):
                self.assertEqual(await HostBehaviorRegistry(records).list(), [marker])

    async def test_saved_legacy_catalog_is_authoritative_without_inserting_package_rows(self):
        records = FakeRecords()
        custom = HostBehavior(id="custom", name="My custom behavior", instruction="Keep this exact instruction.")
        records.value = {"items": [custom.model_dump()], "task_profiles_migrated": True}
        before = deepcopy(records.value)
        registry = HostBehaviorRegistry(records)
        self.assertEqual(await registry.list(), [custom])
        self.assertEqual(records.value, before)
        await registry.replace([custom], expected_revision=0)
        self.assertEqual(await HostBehaviorRegistry(records).list(), [custom])

    async def test_administrator_can_edit_disable_unprotect_or_remove_every_default(self):
        records = FakeRecords()
        registry = HostBehaviorRegistry(records)
        items, revision = await registry.snapshot()
        self.assertTrue(set(REQUIRED_SKILLS).issubset({item.id for item in items}))
        for item in items:
            item.name = "Administrator name: " + item.id
            item.instruction = "Administrator replacement."
            item.enabled = item.required = item.protected = False
            item.priority = 99
        await registry.replace(items, expected_revision=revision)
        reloaded, revision = await HostBehaviorRegistry(records).snapshot()
        self.assertEqual(reloaded, sorted(items, key=lambda item: (item.priority, item.id)))
        self.assertTrue(all(not item.enabled and not item.protected and not item.required for item in reloaded))
        self.assertEqual(revision, 1)
        self.assertEqual(records.value["updated_by"], "administrator")
        self.assertTrue(records.value["updated_at"])
        await registry.replace([], expected_revision=revision)
        self.assertEqual(await HostBehaviorRegistry(records).list(), [])
        self.assertEqual(await registry.compose("CORE"), "CORE")

    async def test_catalog_revision_rejects_a_stale_browser_draft_without_mutation(self):
        records = FakeRecords()
        registry = HostBehaviorRegistry(records)
        original, version = await registry.snapshot()
        await registry.replace(original[1:], expected_revision=version)
        saved = deepcopy(records.value)
        with self.assertRaises(BehaviorRevisionConflict):
            await registry.replace(original, expected_revision=version)
        self.assertEqual(records.value, saved)

    async def test_explicit_empty_membership_deselects_even_required_protected_rows(self):
        records = FakeRecords()
        registry = HostBehaviorRegistry(records)
        self.assertTrue(await registry.selected("reasoning"))
        records.assignments = {"items": [{"task": "reasoning", "behavior_ids": []}]}
        self.assertEqual(await registry.selected("reasoning"), [])
        self.assertEqual(await registry.compose("CORE"), "CORE")

    async def test_returned_defaults_are_isolated_and_ordinary_disabled_behavior_is_not_composed(self):
        registry = HostBehaviorRegistry(FakeRecords())
        items = await registry.list()
        items[0].instruction = "Unpersisted draft"
        self.assertNotIn("Unpersisted draft", (await registry.list())[0].instruction)
        items = await registry.list()
        items.append(HostBehavior(id="concise", name="Concise", instruction="Be concise.", enabled=False))
        await registry.replace(items)
        contract = await registry.compose("CORE")
        self.assertIn("ground-recalled-context", contract)
        self.assertNotIn("Be concise.", contract)


if __name__ == "__main__":
    unittest.main()
