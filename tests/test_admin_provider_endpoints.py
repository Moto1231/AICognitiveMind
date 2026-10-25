"""Full provider catalog edits preserve concurrent existing connections."""

import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

import httpx
from fastapi import FastAPI

from aicognitive_mind import api
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.provider_endpoints import ProviderEndpointRegistry


class AdminProviderEndpointRevisionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.records = RuntimeRecords(SimpleNamespace())
        self.registry = ProviderEndpointRegistry(self.records)
        self.runtime_patch = patch("aicognitive_mind.api._request_runtime", return_value=SimpleNamespace(
            provider_endpoints=self.registry,
        ))
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)
        self.auth_patch = patch("aicognitive_mind.api.require_admin")
        self.auth_patch.start()
        self.addCleanup(self.auth_patch.stop)
        app = FastAPI()
        app.add_api_route("/endpoints", api.admin_provider_endpoints, methods=["GET"])
        app.add_api_route("/endpoints", api.replace_admin_provider_endpoints, methods=["PUT"])
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_stale_profile_batch_cannot_erase_a_new_connection_or_credential_edit(self):
        original = (await self.client.get("/endpoints")).json()
        self.assertEqual(original, {"items": [], "revision": 0})
        current = {"id": "existing", "name": "Existing connection", "base_url": "https://example.test/v1",
                   "api_key": "synthetic-current-key", "model": "current-model"}
        saved = await self.client.put("/endpoints", json={"items": [current], "expected_revision": 0})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["revision"], 1)
        before = deepcopy(await self.records.get(self.registry.RECORD_KEY))
        stale_batch = await self.client.put("/endpoints", json={
            "items": [{"id": "new", "name": "New profile", "base_url": "https://new.example/v1"}],
            "expected_revision": original["revision"],
        })
        self.assertEqual(stale_batch.status_code, 409, stale_batch.text)
        self.assertEqual(await self.records.get(self.registry.RECORD_KEY), before)
        refreshed = (await self.client.get("/endpoints")).json()
        self.assertEqual(refreshed["items"][0]["api_key"], "synthetic-current-key")
        next_save = await self.client.put("/endpoints", json={
            "items": refreshed["items"] + [{"id": "new", "name": "New profile", "base_url": "https://new.example/v1"}],
            "expected_revision": refreshed["revision"],
        })
        self.assertEqual(next_save.status_code, 200, next_save.text)
        self.assertEqual(next_save.json()["revision"], 2)
        self.assertEqual(next_save.json()["items"][0]["api_key"], "synthetic-current-key")

    async def test_legacy_record_and_client_remain_compatible_but_cas_conflicts_are_409(self):
        await self.records.create(self.registry.RECORD_KEY, {"items": []})
        self.assertEqual((await self.client.get("/endpoints")).json()["revision"], 0)
        saved = await self.client.put("/endpoints", json={"items": []})
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertEqual(saved.json()["revision"], 1)
        before = deepcopy(await self.records.get(self.registry.RECORD_KEY))
        with patch.object(self.records, "replace", return_value=False):
            conflict = await self.client.put("/endpoints", json={"items": [], "expected_revision": 1})
        self.assertEqual(conflict.status_code, 409, conflict.text)
        self.assertEqual(await self.records.get(self.registry.RECORD_KEY), before)

    async def test_initial_create_race_reports_409_and_preserves_the_competing_record(self):
        actual_create = self.records.create
        winner = {"items": [], "revision": 1}

        async def competing_create(key, value):
            await actual_create(key, winner)
            raise RuntimeError("Backend duplicate record")

        with patch.object(self.records, "create", side_effect=competing_create):
            result = await self.client.put("/endpoints", json={"items": [], "expected_revision": 0})
        self.assertEqual(result.status_code, 409, result.text)
        self.assertEqual(await self.records.get(self.registry.RECORD_KEY), winner)

