"""Saved Administrator settings must reach the next real runtime request."""

import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aicognitive_mind.cognitive_configuration import CognitiveConfigurationRegistry
from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.core_skills import load_required_skill
from aicognitive_mind.effective_skills import EffectiveSkillRegistry
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.host_behaviors import HostBehaviorRegistry
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.prompts import CONSCIOUS_WORKSPACE_SYSTEM_PROMPT, DEFAULT_STARTUP_INSTRUCTIONS
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore, InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore,
)


SKIP = {"action": "finish", "outcome": "no_recall_needed", "reason": "Context suffices."}
NOTHING = {"action": "finish", "reason": "No stable learning.", "memories": []}


class ScriptedRuntime:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    async def execute(self, context, payload):
        self.calls.append((context, json.loads(json.dumps(payload))))
        return json.dumps(self.responses.pop(0))


class RuntimeAdministratorSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mind = InMemoryMindStore()
        self.journal = InMemoryJournalStore()
        self.memory = InMemoryMemoryStore()
        self.records = RuntimeRecords(self.mind)
        self.service = self.new_service()
        await self.service.initialize("Axiom")

    def new_service(self, *, model_steward=False):
        kwargs = {} if model_steward else {"steward_factory": MemoryStewardTool}
        return CognitiveMcpService(self.mind, self.journal, self.memory, **kwargs)

    async def test_status_reads_saved_routing_with_an_execute_only_model_adapter(self):
        self.service._steward_runtime = SimpleNamespace(execute=AsyncMock())
        status = await self.service.status()
        self.assertEqual(status["provider_routing"]["rotation_timezone"], "UTC")
        tasks = status["provider_routing"]["tasks"]
        self.assertIn("memory_recall", {item["task"] for item in tasks})
        self.service._steward_runtime.execute.assert_not_awaited()

    async def test_disabled_skill_is_not_reasserted_by_a_persisted_old_factory_marker(self):
        legacy_text = (
            "Axiom Continuity is required for every Axiom reasoning interaction. "
            "Apply its full packaged protocol supplied in the mandatory reasoning contract, "
            "including fresh instances and follow-ups. Optional task memberships cannot disable it."
        )
        legacy = {"id": "axiom-continuity", "name": "Axiom Continuity", "instruction": legacy_text,
                  "enabled": True, "priority": 0, "protected": True, "required": True}
        custom = {"id": "custom", "name": "Custom", "instruction": "Preserve this unrelated authored rule."}
        original_record = {"items": [legacy, custom], "task_profiles_migrated": True}
        await self.records.create("host_behaviors", original_record)
        await EffectiveSkillRegistry(self.records).save("axiom-continuity", {
            "enabled": False, "required": False,
        }, expected_revision=0)
        begun = await self.new_service().begin_interaction("Use the effective Administrator settings.")
        prompt = begun["conscious_workspace_contract"]
        self.assertNotIn(legacy_text, prompt)
        self.assertNotIn(load_required_skill("axiom-continuity"), prompt)
        self.assertIn("effective Mind skill configuration", prompt)
        self.assertIn(custom["instruction"], prompt)
        self.assertEqual(await self.records.get("host_behaviors"), original_record)

    async def test_saved_foundations_and_skill_text_reach_fresh_begin_then_disable(self):
        await CognitiveConfigurationRegistry(self.records).save({
            "base_contract": "Administrator base contract marker.",
            "startup_instructions": "Administrator startup marker.",
            "task_foundations": {"reasoning": "Administrator reasoning foundation marker."},
        }, expected_revision=0)
        skills = EffectiveSkillRegistry(self.records)
        await skills.save("axiom-continuity", {
            "content": "Administrator continuity instructions marker.", "protected": False,
        }, expected_revision=0)

        begun = await self.new_service().begin_interaction("Continue the task.")
        prompt = begun["conscious_workspace_contract"]
        for marker in ("base contract", "startup", "reasoning foundation", "continuity instructions"):
            self.assertIn("Administrator " + marker + " marker.", prompt)
        self.assertNotIn(CONSCIOUS_WORKSPACE_SYSTEM_PROMPT, prompt)
        self.assertNotIn(DEFAULT_STARTUP_INSTRUCTIONS, prompt)
        self.assertNotIn(load_required_skill("axiom-continuity"), prompt)

        await skills.save("axiom-continuity", {"enabled": False, "required": False}, expected_revision=1)
        next_begin = await self.new_service().begin_interaction("Use the changed settings.")
        self.assertNotIn("Administrator continuity instructions marker.", next_begin["conscious_workspace_contract"])
        metadata = next(item for item in next_begin["current_state"]["fields"]["skills"]["value"]
                        if item.get("slug") == "axiom-continuity")
        self.assertFalse(metadata["required"])
        self.assertFalse(metadata["enabled"])
        self.assertFalse(metadata["loaded_in_reasoning_contract"])
        self.assertEqual(metadata["revision"], 2)
        self.assertEqual(metadata["source"], "mind_override")
        self.assertNotIn("content", metadata)

    async def test_explicit_empty_foundations_remain_empty_in_mcp_and_direct_core(self):
        await CognitiveConfigurationRegistry(self.records).save({
            "base_contract": "", "startup_instructions": "", "task_foundations": {"reasoning": ""},
        }, expected_revision=0)
        await HostBehaviorRegistry(self.records).replace([], expected_revision=0)
        skills = EffectiveSkillRegistry(self.records)
        for skill in await skills.list():
            await skills.save(skill["slug"], {"enabled": False}, expected_revision=skill["revision"])

        begun = await self.new_service().begin_interaction("Continue with explicit blanks.")
        prompt = begun["conscious_workspace_contract"]
        self.assertNotIn(CONSCIOUS_WORKSPACE_SYSTEM_PROMPT, prompt)
        self.assertNotIn(DEFAULT_STARTUP_INSTRUCTIONS, prompt)
        self.assertNotIn("You are Axiom's reasoning task.", prompt)
        self.assertNotIn("SPEAKER GROUNDING RULE", prompt)
        self.assertNotIn("# Axiom Continuity", prompt)
        self.assertNotIn("# Axiom Current State", prompt)

        engine = EchoReasoningEngine()
        engine.propose = AsyncMock(wraps=engine.propose)
        core = CognitiveCore(self.mind, self.journal, self.memory, InMemoryDiagnosticStore(), engine)
        result = await core.interact("Use saved settings on the direct route.")
        self.assertIn("Use saved settings", result.response_text)
        direct_prompt = engine.propose.await_args.args[0].system_prompt
        self.assertNotIn(CONSCIOUS_WORKSPACE_SYSTEM_PROMPT, direct_prompt)
        self.assertNotIn(DEFAULT_STARTUP_INSTRUCTIONS, direct_prompt)
        self.assertNotIn("You are Axiom's reasoning task.", direct_prompt)
        self.assertNotIn("# Axiom Continuity", direct_prompt)

    async def test_saved_internal_steward_skill_applies_to_recall_and_review_then_disable(self):
        skills = EffectiveSkillRegistry(self.records)
        await skills.save("memory-steward", {
            "content": "Administrator internal Steward marker.",
        }, expected_revision=0)
        runtime = ScriptedRuntime(SKIP, NOTHING)
        service = self.new_service(model_steward=True)
        service._steward_runtime = runtime
        begun = await service.begin_interaction("Use current context.")
        completed = await service.complete_interaction(
            "Use current context.", "Done.", idempotency_key=begun["idempotency_key"],
        )
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(runtime.calls), 2)
        for _, payload in runtime.calls:
            self.assertTrue(payload["messages"][0]["content"].startswith("Administrator internal Steward marker."))
        self.assertNotIn("Administrator internal Steward marker.", begun["conscious_workspace_contract"])

        await skills.save("memory-steward", {"enabled": False}, expected_revision=1)
        fresh_runtime = ScriptedRuntime(SKIP)
        fresh = self.new_service(model_steward=True)
        fresh._steward_runtime = fresh_runtime
        await fresh.begin_interaction("Continue after disabling the extra skill instructions.")
        content = fresh_runtime.calls[0][1]["messages"][0]["content"]
        self.assertTrue(content.startswith("\n\nPHASE SCHEMA:"))
        self.assertNotIn("Administrator internal Steward marker.", content)
        self.assertNotIn("# Memory Steward", content)

