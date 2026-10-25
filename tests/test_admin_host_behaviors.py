"""Behavior saves must carry a current revision and preserve competing saves."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from aicognitive_mind import api
from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.host_behaviors import HostBehaviorRegistry
from aicognitive_mind.host_runtime import RuntimeRecords


class AdminHostBehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.records = RuntimeRecords(SimpleNamespace())
        self.registry = HostBehaviorRegistry(self.records)
        self.runtime_patch = patch("aicognitive_mind.api._request_runtime", return_value=SimpleNamespace(
            host_behaviors=self.registry,
        ))
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)
        self.auth_patch = patch("aicognitive_mind.api.require_admin")
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        app = FastAPI()
        app.add_api_route("/behaviors", api.admin_host_behaviors, methods=["GET"])
        app.add_api_route("/behaviors", api.replace_admin_host_behaviors, methods=["PUT"])
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_missing_null_or_stale_revision_cannot_overwrite_the_saved_catalog(self):
        items = (await self.client.get("/behaviors")).json()["items"]
        for revision in ({}, {"expected_revision": None}, {"expected_revision": True}):
            result = await self.client.put("/behaviors", json={"items": [], **revision})
            self.assertEqual(result.status_code, 422, result.text)
        self.assertIsNone(await self.records.get(self.registry.RECORD_KEY))
        saved = await self.client.put("/behaviors", json={"items": items[1:], "expected_revision": 0})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["revision"], 1)
        before = deepcopy(await self.records.get(self.registry.RECORD_KEY))
        stale = await self.client.put("/behaviors", json={"items": [], "expected_revision": 0})
        self.assertEqual(stale.status_code, 409, stale.text)
        self.assertEqual(await self.records.get(self.registry.RECORD_KEY), before)

    async def test_a_competing_initial_create_is_a_409_without_overwriting_the_winner(self):
        actual_create = self.records.create
        winner = {"items": [], "revision": 1, "task_profiles_migrated": True}

        async def competing_create(key, value):
            await actual_create(key, winner)
            raise CommitConflict("A concurrent browser created the record")

        with patch.object(self.records, "create", side_effect=competing_create):
            result = await self.client.put("/behaviors", json={
                "items": (await self.client.get("/behaviors")).json()["items"], "expected_revision": 0,
            })
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(await self.records.get(self.registry.RECORD_KEY), winner)

    async def test_a_real_storage_failure_remains_an_error_without_claiming_a_conflict(self):
        with patch.object(self.records, "create", side_effect=RuntimeError("Storage unavailable")):
            with self.assertRaisesRegex(RuntimeError, "Storage unavailable"):
                await self.registry.replace([], expected_revision=0)
        self.assertIsNone(await self.records.get(self.registry.RECORD_KEY))

