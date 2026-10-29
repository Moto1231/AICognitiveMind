"""Saved Administrator settings win over packaged defaults across runtime reloads."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from aicognitive_mind.effective_skills import EffectiveSkillRegistry, SkillRevisionConflict, packaged_skill_defaults
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.task_model_assignments import TASK_LABELS
from aicognitive_mind.task_skill_defaults import core_task_skill_slug


class FakeMind:
    pass


class EffectiveSkillTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_packaged_skills_are_editable_and_saved_settings_survive_new_defaults(self):
        records = RuntimeRecords(FakeMind())
        registry = EffectiveSkillRegistry(records)
        defaults = await registry.list()
        self.assertEqual(
            {item["slug"] for item in defaults},
            {"axiom-continuity", "axiom-current-state", "memory-steward"}
            | {core_task_skill_slug(task) for task in TASK_LABELS},
        )
        for item in [value for value in defaults if not value["required_tasks"]]:
            self.assertFalse(item["read_only"])
            saved = await registry.save(item["slug"], {
                "name": "Administrator: " + item["name"], "content": "",
                "enabled": False, "required": False, "protected": False,
            }, expected_revision=0)
            self.assertEqual(saved["revision"], 1)
        changed = packaged_skill_defaults()
        for item in changed:
            item.update(content="New package defaults", enabled=True, required=True, protected=True)
        with patch("aicognitive_mind.effective_skills.packaged_skill_defaults", return_value=changed):
            reloaded = await EffectiveSkillRegistry(records).list()
        edited = [item for item in reloaded if item["slug"] in {
            "axiom-continuity", "axiom-current-state", "memory-steward",
        }]
        self.assertTrue(all(item["content"] == "" and not item["enabled"] and not item["required"]
                            and not item["protected"] and item["source"] == "mind_override" for item in edited))
        self.assertTrue(all(item["updated_by"] == "administrator" and item["updated_at"] for item in edited))

    async def test_legacy_task_text_surfaces_as_required_core_skill_then_normal_override(self):
        records = RuntimeRecords(FakeMind())
        await records.create("cognitive_configuration", {
            "revision": 7,
            "task_foundations": {"vision": "Existing Administrator vision instructions."},
            "updated_by": "administrator",
        })
        registry = EffectiveSkillRegistry(records)
        slug = core_task_skill_slug("vision")
        migrated = await registry.get(slug)
        self.assertEqual(migrated["content"], "Existing Administrator vision instructions.")
        self.assertEqual(migrated["source"], "legacy_task_instruction")
        self.assertEqual(migrated["required_tasks"], ["vision"])
        saved = await registry.save(slug, {
            "content": "Edited in Skills.", "enabled": False, "protected": False,
            "required": True, "required_tasks": [],
        }, expected_revision=7)
        self.assertEqual(saved["content"], "Edited in Skills.")
        self.assertTrue(saved["enabled"])
        self.assertTrue(saved["protected"])
        self.assertFalse(saved["required"])
        self.assertEqual(saved["required_tasks"], ["vision"])

    async def test_task_contract_keeps_core_first_and_optional_skills_in_selected_order(self):
        registry = EffectiveSkillRegistry(RuntimeRecords(FakeMind()))
        await registry.save("alpha", {"name": "Alpha", "content": "Alpha instructions."}, expected_revision=0)
        await registry.save("beta", {"name": "Beta", "content": "Beta instructions."}, expected_revision=0)
        contract = await registry.task_contract("coding", ["beta", "alpha"])
        self.assertLess(contract.index("task-coding-core"), contract.index("Beta (beta)"))
        self.assertLess(contract.index("Beta (beta)"), contract.index("Alpha (alpha)"))
        self.assertIn("[required]", contract)

    async def test_new_custom_configuration_and_internal_skill_round_trip(self):
        registry = EffectiveSkillRegistry(RuntimeRecords(FakeMind()))
        saved = await registry.save("custom", {
            "name": "My skill", "content": "Administrator instructions.", "required": True,
        }, expected_revision=0)
        self.assertEqual(await registry.get("custom"), saved)
        internal = await registry.get("memory-steward")
        saved_internal = await registry.save("memory-steward", {"content": "Different review guidance."},
                                             expected_revision=internal["revision"])
        self.assertEqual((await registry.get("memory-steward"))["content"], saved_internal["content"])

    async def test_stale_revision_and_record_cas_conflict_leave_saved_data_unchanged(self):
        records = RuntimeRecords(FakeMind())
        registry = EffectiveSkillRegistry(records)
        await registry.save("axiom-continuity", {"content": "Saved"}, expected_revision=0)
        before = deepcopy(await records.get(registry.RECORD_KEY))
        with self.assertRaises(SkillRevisionConflict):
            await registry.save("axiom-continuity", {"content": "Stale"}, expected_revision=0)
        with patch.object(records, "replace", return_value=False), self.assertRaises(SkillRevisionConflict):
            await registry.save("axiom-continuity", {"content": "Concurrent"}, expected_revision=1)
        self.assertEqual(await records.get(registry.RECORD_KEY), before)

    async def test_different_mind_records_never_share_overrides(self):
        alpha = EffectiveSkillRegistry(RuntimeRecords(FakeMind()))
        beta = EffectiveSkillRegistry(RuntimeRecords(FakeMind()))
        await alpha.save("axiom-continuity", {"content": "Alpha private setting", "enabled": False}, expected_revision=0)
        self.assertNotEqual((await alpha.get("axiom-continuity"))["content"],
                            (await beta.get("axiom-continuity"))["content"])
        self.assertTrue((await beta.get("axiom-continuity"))["enabled"])

    async def test_competing_initial_create_converts_backend_duplicate_to_revision_conflict(self):
        records = RuntimeRecords(FakeMind())
        registry = EffectiveSkillRegistry(records)
        actual_create = records.create
        winner = {"items": [], "revision": 1}

        async def competing_create(key, value):
            await actual_create(key, winner)
            # Mongo/Surreal duplicate errors are not CommitConflict subclasses.
            raise RuntimeError("Backend duplicate record")

        with patch.object(records, "create", side_effect=competing_create):
            with self.assertRaises(SkillRevisionConflict):
                await registry.save("axiom-continuity", {"content": "Stale initial edit"}, expected_revision=0)
        self.assertEqual(await records.get(registry.RECORD_KEY), winner)

    async def test_unconfirmed_initial_storage_failure_is_not_relabelled_a_conflict(self):
        records = RuntimeRecords(FakeMind())
        registry = EffectiveSkillRegistry(records)
        with patch.object(records, "create", side_effect=RuntimeError("Storage unavailable")):
            with self.assertRaisesRegex(RuntimeError, "Storage unavailable"):
                await registry.save("axiom-continuity", {"content": "Unsaved"}, expected_revision=0)
        self.assertIsNone(await records.get(registry.RECORD_KEY))
