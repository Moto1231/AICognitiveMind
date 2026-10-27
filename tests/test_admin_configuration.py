"""Administrator edits affect actual scoped identity and runtime cognitive settings."""

import unittest
from copy import deepcopy
from types import SimpleNamespace

import httpx
from fastapi import FastAPI, HTTPException

from aicognitive_mind.admin_configuration import (
    AdministratorIdentityService, IdentityUpdate, create_admin_configuration_router,
)
from aicognitive_mind.cognitive_configuration import (
    CognitiveConfigurationConflict, CognitiveConfigurationRegistry,
)
from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.domain import CognitiveActor, CognitiveMind, JournalKind, MindIdentity
from aicognitive_mind.permissions import CognitiveOperation, CognitivePermissionError, PermissionPolicy
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMindStore
from aicognitive_mind.task_behaviors import TaskBehaviorRegistry, TaskExecutionContext, TaskPromptAssembler


class Records:
    def __init__(self):
        self.values = {}
        self.fail_replace = False

    async def get(self, key):
        return deepcopy(self.values.get(key))

    async def create(self, key, value):
        if key in self.values:
            raise CommitConflict("Already exists")
        self.values[key] = deepcopy(value)

    async def replace(self, key, before, after):
        if self.fail_replace or self.values.get(key) != before:
            return False
        self.values[key] = deepcopy(after)
        return True


class CognitiveConfigurationTests(unittest.IsolatedAsyncioTestCase):
    async def test_overrides_reload_preserve_blanks_and_unedited_task_foundations(self):
        records = Records()
        registry = CognitiveConfigurationRegistry(records)
        original = await registry.effective()
        saved = await registry.save({
            "base_contract": "", "startup_instructions": "",
            "task_foundations": {"coding": "Administrator coding foundation."},
        }, expected_revision=original["revision"])
        self.assertEqual(saved["revision"], 1)
        self.assertEqual(saved["updated_by"], "administrator")
        self.assertTrue(saved["updated_at"])
        self.assertEqual(saved["base_contract"], "")
        self.assertEqual(saved["startup_instructions"], "")
        self.assertEqual(saved["task_foundations"]["vision"], original["task_foundations"]["vision"])
        self.assertEqual(await CognitiveConfigurationRegistry(records).effective(), saved)
        next_saved = await registry.save({"task_foundations": {"vision": ""}}, expected_revision=1)
        self.assertEqual(next_saved["task_foundations"]["coding"], "Administrator coding foundation.")
        self.assertEqual(next_saved["task_foundations"]["vision"], "")
        self.assertEqual(next_saved["base_contract"], "")

    async def test_stale_or_conflicting_edits_do_not_overwrite_saved_configuration(self):
        records = Records()
        registry = CognitiveConfigurationRegistry(records)
        await registry.save({"base_contract": "Current contract"}, expected_revision=0)
        before = deepcopy(records.values)
        with self.assertRaises(CognitiveConfigurationConflict):
            await registry.save({"base_contract": "Stale browser"}, expected_revision=0)
        records.fail_replace = True
        with self.assertRaises(CognitiveConfigurationConflict):
            await registry.save({"base_contract": "Concurrent overwrite"}, expected_revision=1)
        self.assertEqual(records.values, before)

    async def test_invalid_configuration_and_empty_patch_do_not_create_records(self):
        records = Records()
        registry = CognitiveConfigurationRegistry(records)
        for changes in (
            {"identity": {}}, {"updated_by": "someone else"},
            {"task_foundations": {"unsupported": "A rule"}}, {"base_contract": None},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                await registry.save(changes, expected_revision=0)
        self.assertEqual((await registry.save({}, expected_revision=0))["revision"], 0)
        self.assertEqual(records.values, {})

    async def test_effective_foundation_reaches_real_task_prompt_after_reload(self):
        records = Records()
        original = await CognitiveConfigurationRegistry(records).effective()
        marker = "Administrator-owned visual grounding rule."
        await CognitiveConfigurationRegistry(records).save({
            "task_foundations": {"vision": marker},
        }, expected_revision=0)
        prompt = await TaskPromptAssembler(TaskBehaviorRegistry(records)).system_prompt(
            TaskExecutionContext(task="vision"),
        )
        self.assertIn(marker, prompt)
        self.assertNotIn(original["task_foundations"]["vision"], prompt)
        self.assertIn("Administrator configurable", prompt)
        await CognitiveConfigurationRegistry(records).save({
            "task_foundations": {"vision": ""},
        }, expected_revision=1)
        blank = await TaskPromptAssembler(TaskBehaviorRegistry(records)).system_prompt(
            TaskExecutionContext(task="vision"),
        )
        self.assertNotIn(marker, blank)
        self.assertNotIn(original["task_foundations"]["vision"], blank)


class AdministratorIdentityTests(unittest.IsolatedAsyncioTestCase):
    async def make_service(self, journal=None):
        mind = InMemoryMindStore()
        await mind.initialize(CognitiveMind(identity=MindIdentity(
            self_name="Original", foundational_values=("Original value",),
            relationships=({"relationship": "synthetic test relationship"},),
        )))
        journal = journal or InMemoryJournalStore()
        return AdministratorIdentityService(mind, journal), mind, journal

    async def test_edit_changes_actual_identity_and_development_with_atomic_journal(self):
        service, mind, journal = await self.make_service()
        before = await service.read()
        saved = await service.save(IdentityUpdate(
            expected_revision=before["revision"],
            identity={
                "self_name": None, "pronouns": "they/them", "foundational_values": ["New value"],
                "commitments": ["An Administrator commitment"],
            },
            developmental_state="developing",
        ))
        actual = await mind.load()
        self.assertIsNone(actual.identity.self_name)
        self.assertEqual(actual.identity.pronouns, "they/them")
        self.assertEqual(actual.identity.foundational_values, ("New value",))
        self.assertEqual(actual.identity.commitments, ("An Administrator commitment",))
        self.assertEqual(actual.identity.relationships, ({"relationship": "synthetic test relationship"},))
        self.assertEqual(actual.developmental_state, "developing")
        self.assertEqual(saved["created_at"], before["created_at"])
        self.assertNotEqual(saved["revision"], before["revision"])
        self.assertEqual(await AdministratorIdentityService(mind, journal).read(), saved)
        entries = await journal.read()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].kind, JournalKind.IDENTITY_REVISION)
        self.assertEqual(entries[0].experience["authority"], "administrator")
        self.assertEqual(entries[0].experience["before"]["identity"], before["identity"])
        self.assertEqual(entries[0].experience["after"]["identity"], saved["identity"])
        with self.assertRaises(CommitConflict):
            await service.save(IdentityUpdate(expected_revision=before["revision"], identity={"self_name": "Stale"}))
        self.assertEqual(len(await journal.read()), 1)

    async def test_journal_permission_failure_rolls_back_staged_identity(self):
        class FailAdminAudit(PermissionPolicy):
            def assert_allowed(self, actor, operation):
                if actor == CognitiveActor.ADMINISTRATOR and operation == CognitiveOperation.RECORD_JOURNAL:
                    raise CognitivePermissionError("Audit unavailable")
                super().assert_allowed(actor, operation)

        service, mind, journal = await self.make_service(InMemoryJournalStore(FailAdminAudit()))
        original = await mind.load()
        snapshot = await service.read()
        with self.assertRaises(CognitivePermissionError):
            await service.save(IdentityUpdate(expected_revision=snapshot["revision"], identity={"self_name": "Unsaved"}))
        self.assertEqual(await mind.load(), original)
        self.assertEqual(await journal.read(), [])

    def test_ordinary_actors_do_not_gain_administrator_identity_authority(self):
        policy = PermissionPolicy()
        for actor in (CognitiveActor.HUMAN, CognitiveActor.CONSCIOUS_WORKSPACE, CognitiveActor.REASONING_ENGINE):
            with self.subTest(actor=actor), self.assertRaises(CognitivePermissionError):
                policy.assert_allowed(actor, CognitiveOperation.APPROVE_IDENTITY_REVISION)
        policy.assert_allowed(CognitiveActor.ADMINISTRATOR, CognitiveOperation.APPROVE_IDENTITY_REVISION)
        with self.assertRaises(CognitivePermissionError):
            policy.assert_allowed(CognitiveActor.ADMINISTRATOR, CognitiveOperation.WRITE_DURABLE_MEMORY)


class AdministratorRouterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtimes = {}
        for tenant in ("alpha", "beta"):
            mind = InMemoryMindStore()
            await mind.initialize(CognitiveMind(identity=MindIdentity(self_name=tenant)))
            self.runtimes[tenant] = SimpleNamespace(
                mind_store=mind, journal_store=InMemoryJournalStore(), runtime_records=Records(),
            )

        def authorize(request):
            if request.headers.get("X-Admin-Pin") != "synthetic-admin-pin":
                raise HTTPException(401, "Administrator authorization was not accepted")

        def runtime(request):
            return self.runtimes[request.headers.get("X-Test-Tenant", "alpha")]

        app = FastAPI()
        app.include_router(create_admin_configuration_router(authorize, runtime))
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test",
            headers={"X-Admin-Pin": "synthetic-admin-pin"},
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_identity_configuration_is_scoped_and_requires_authorization(self):
        original = (await self.client.get("/v1/admin/identity")).json()
        saved = await self.client.put("/v1/admin/identity", json={
            "expected_revision": original["revision"], "identity": {"self_name": "Edited alpha"},
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["identity"]["self_name"], "Edited alpha")
        beta = await self.client.get("/v1/admin/identity", headers={"X-Test-Tenant": "beta"})
        self.assertEqual(beta.json()["identity"]["self_name"], "beta")
        self.assertEqual(await self.runtimes["beta"].journal_store.read(), [])
        stale = await self.client.put("/v1/admin/identity", json={
            "expected_revision": original["revision"], "identity": {"self_name": "Stale"},
        })
        self.assertEqual(stale.status_code, 409)
        denied = await self.client.get("/v1/admin/identity", headers={"X-Admin-Pin": ""})
        self.assertEqual(denied.status_code, 401)
        self.assertEqual((await self.client.put("/v1/admin/identity", json={
            "expected_revision": saved.json()["revision"], "identity": {"self_name": "Denied"},
        }, headers={"X-Admin-Pin": ""})).status_code, 401)

    async def test_cognitive_settings_patch_cas_and_tenant_separation(self):
        snapshot = (await self.client.get("/v1/admin/cognitive-configuration")).json()
        saved = await self.client.put("/v1/admin/cognitive-configuration", json={
            "expected_revision": snapshot["revision"], "base_contract": "", "task_foundations": {"coding": "Alpha rule"},
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["base_contract"], "")
        beta = (await self.client.get("/v1/admin/cognitive-configuration", headers={"X-Test-Tenant": "beta"})).json()
        self.assertEqual(beta["revision"], 0)
        self.assertEqual(beta["task_foundations"]["coding"], snapshot["task_foundations"]["coding"])
        stale = await self.client.put("/v1/admin/cognitive-configuration", json={
            "expected_revision": snapshot["revision"], "base_contract": "Stale contract",
        })
        self.assertEqual(stale.status_code, 409)
        invalid = await self.client.put("/v1/admin/cognitive-configuration", json={
            "expected_revision": 1, "identity": {"self_name": "Wrong editor"},
        })
        self.assertEqual(invalid.status_code, 422)
        denied = await self.client.get("/v1/admin/cognitive-configuration", headers={"X-Admin-Pin": ""})
        self.assertEqual(denied.status_code, 401)
        denied_save = await self.client.put("/v1/admin/cognitive-configuration", json={
            "expected_revision": 1, "base_contract": "Denied contract",
        }, headers={"X-Admin-Pin": ""})
        self.assertEqual(denied_save.status_code, 401)

    async def test_breaker_settings_are_revisioned_validated_and_tenant_scoped(self):
        snapshot = (await self.client.get("/v1/admin/continuity-settings")).json()
        self.assertEqual(snapshot["revision"], 0)
        self.assertEqual(snapshot["consecutive_failure_limit"], 5)
        self.assertEqual(snapshot["health"]["name"], "The Breaker")
        saved = await self.client.put("/v1/admin/continuity-settings", json={
            "expected_revision": 0,
            "consecutive_failure_limit": 4,
            "rolling_failure_limit": 20,
            "rolling_window_size": 80,
            "provider_request_timeout_seconds": 20,
            "steward_assessment_timeout_seconds": 75,
            "rate_limit_retry_wait_cap_seconds": 10,
        })
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["revision"], 1)
        self.assertEqual(saved.json()["provider_request_timeout_seconds"], 20)
        beta = await self.client.get(
            "/v1/admin/continuity-settings", headers={"X-Test-Tenant": "beta"},
        )
        self.assertEqual(beta.json()["revision"], 0)
        self.assertEqual(beta.json()["consecutive_failure_limit"], 5)
        stale = await self.client.put("/v1/admin/continuity-settings", json={
            "expected_revision": 0, "consecutive_failure_limit": 3,
        })
        self.assertEqual(stale.status_code, 409)
        invalid = await self.client.put("/v1/admin/continuity-settings", json={
            "expected_revision": 1, "rolling_failure_limit": 2,
        })
        self.assertEqual(invalid.status_code, 422)
        denied = await self.client.get(
            "/v1/admin/continuity-settings", headers={"X-Admin-Pin": ""},
        )
        self.assertEqual(denied.status_code, 401)


if __name__ == "__main__":
    unittest.main()
