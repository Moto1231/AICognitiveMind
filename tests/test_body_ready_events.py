"""Passive sensory events wake a worker without fabricating human interaction."""

import asyncio
import base64
import json
import time
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aicognitive_mind.host_runtime import HostRuntime
from aicognitive_mind.mcp_events import MessageEvents, SubscribeParams, STATE_KEY


SECRET = "whsec_" + base64.b64encode(b"synthetic-callback-signing-key-32!").decode()
OWNER = {"id": "synthetic-owner", "client_id": "client", "subject": "mind", "issuer": "https://example.test"}
EVIDENCE = {"sha256": "f" * 64, "captured_at": "2026-10-26T20:00:00Z", "media_type": "image/jpeg"}


class BodyReadyEventsTests(unittest.IsolatedAsyncioTestCase):
    def runtime(self):
        return HostRuntime(SimpleNamespace(mind_id="mind"), SimpleNamespace(
            begin_interaction=AsyncMock(), complete_interaction=AsyncMock(),
        ))

    def sensory(self, key="sensory-one", **updates):
        now = time.time()
        return {
            "kind": "body_request", "request_id": key, "priority": 10,
            "task": "sensory_interpretation", "state": "pending", "body_session": "phone",
            "message": "Media prompt must not appear in the wake notification",
            "created": now, "deadline": now + 120, "claim": "", "claim_until": 0,
            "input_context": {"modality": "vision", "source": "camera", "evidence": deepcopy(EVIDENCE)},
            "result": {}, **updates,
        }

    async def subscribe(self, runtime, delivered, name="sensory.ready"):
        async def post(url, secret, event_id, payload, sub_id, previous_secret=None):
            delivered.append(deepcopy(payload))
            return 200, json.dumps({"challenge": payload.get("challenge")}).encode()

        events = MessageEvents(runtime.records, post=post)
        await events.subscribe(OWNER, SubscribeParams.model_validate({
            "name": name, "arguments": {},
            "delivery": {"mode": "webhook", "url": "https://example.test/callback", "secret": SECRET},
        }))
        return events

    async def test_sensory_events_are_distinct_filtered_metadata_with_original_locator(self):
        runtime = self.runtime()
        delivered = []
        events = await self.subscribe(runtime, delivered)
        await self.subscribe(runtime, delivered, "message.created")
        sensory = self.sensory()
        human = {**self.sensory("human"), "priority": 0, "message": "Hello"}
        human.pop("task")
        for request in (sensory, human):
            await runtime.records.create(request["request_id"], request)
            await events.enqueue(request)
        await events.flush()
        sent = [event for event in delivered if "name" in event]
        self.assertEqual({event["name"] for event in sent}, {"sensory.ready", "message.created"})
        event = next(event for event in sent if event["name"] == "sensory.ready")
        self.assertEqual(event["data"]["evidence"], EVIDENCE)
        self.assertNotIn("text", event["data"])
        self.assertNotIn(sensory["message"], str(event))
        self.assertTrue(await runtime.sensory_events_enabled())
        self.assertTrue(await runtime.message_events_enabled())

    async def test_event_worker_can_complete_passive_job_without_host_or_conscious_lifecycle(self):
        runtime = self.runtime()
        delivered = []
        await self.subscribe(runtime, delivered)
        task = asyncio.create_task(runtime.submit(
            "Preserved frame", priority=10, task="sensory_interpretation",
            input_context=self.sensory()["input_context"],
        ))
        try:
            for _ in range(100):
                pending = await runtime.records.pending()
                if pending:
                    break
                await asyncio.sleep(0.001)
            request_id = pending[0]["request_id"]
            self.assertIsNone(await runtime.active())
            with self.assertRaises(ValueError):
                await runtime.claim_incoming_message(request_id)
            claim = await runtime.claim_incoming_sensory(request_id)
            self.assertEqual(claim["status"], "claimed")
            self.assertEqual(claim["context"]["input_context"]["evidence"], EVIDENCE)
            self.assertEqual((await runtime.claim_incoming_sensory(request_id))["status"], "in_progress")
            with self.assertRaises(PermissionError):
                await runtime.complete_incoming_sensory("wrong", request_id, "A red mug.")
            first = await runtime.complete_incoming_sensory(claim["claim_token"], request_id, "A red mug.")
            self.assertEqual(await runtime.complete_incoming_sensory(
                claim["claim_token"], request_id, "A red mug.",
            ), first)
            self.assertEqual((await asyncio.wait_for(task, 1))["response_text"], "A red mug.")
            runtime.service.begin_interaction.assert_not_awaited()
            runtime.service.complete_interaction.assert_not_awaited()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_ready_receiver_renews_lease_and_only_returns_unclaimed_identifiers(self):
        runtime = self.runtime()
        runtime.REQUEST_WAIT_SECONDS = 0
        lease = (await runtime.attach("Synthetic receiver", "configured-model"))["lease_token"]
        host = await runtime.records.get("active_host")
        await runtime.records.replace("active_host", host, {**host, "last_heartbeat_at": 0})
        sensory = self.sensory()
        human = {**self.sensory("human"), "priority": 0}
        human.pop("task")
        claimed = self.sensory("already-claimed", claim="another-worker", claim_until=time.time() + 90)
        for request in (sensory, human, claimed):
            await runtime.records.create(request["request_id"], request)
        result = await runtime.ready_events(lease)
        self.assertEqual([request["kind"] for request in result["requests"]], ["human", "sensory"])
        self.assertEqual(set(result["requests"][0]), {"request_id", "kind", "created", "deadline"})
        self.assertNotIn("Media prompt", str(result))
        self.assertIsNotNone(await runtime.active())
        self.assertEqual((await runtime.ready_events(lease, ("human", "sensory-one")))["requests"], [])
        with self.assertRaises(PermissionError):
            await runtime.ready_events("wrong")
        with self.assertRaises(ValueError):
            await runtime.ready_events(lease, tuple(str(i) for i in range(513)))

    async def test_terminal_sensory_events_are_not_delivered_or_reclaimed(self):
        runtime = self.runtime()
        delivered = []
        events = await self.subscribe(runtime, delivered)
        request = self.sensory()
        await runtime.records.create(request["request_id"], request)
        await events.enqueue(request)
        current = await runtime.records.get(request["request_id"])
        self.assertTrue(await runtime.records.replace(
            request["request_id"], current, {**current, "state": "cancelled"},
        ))
        count = len(delivered)
        await events.flush()
        self.assertEqual(len(delivered), count)
        self.assertEqual((await runtime.claim_incoming_sensory(request["request_id"]))["status"], "cancelled")
        self.assertEqual((await runtime.records.get(STATE_KEY))["deliveries"], {})

    async def test_ready_receiver_only_rearms_after_real_terminal_state(self):
        runtime = self.runtime()
        runtime.REQUEST_WAIT_SECONDS = 0
        lease = (await runtime.attach("Synthetic receiver", "configured-model"))["lease_token"]
        pending = self.sensory("a" * 32, claim="busy-worker", claim_until=time.time() + 60)
        complete = self.sensory("b" * 32, state="complete")
        expired = self.sensory("c" * 32, deadline=time.time() - 1)
        cancelled = self.sensory("d" * 32, state="cancelled")
        missing = "e" * 32
        for request in (pending, complete, expired, cancelled):
            await runtime.records.create(request["request_id"], request)
        ids = tuple(request["request_id"] for request in (pending, complete, expired, cancelled)) + (missing,)
        result = await runtime.ready_events(lease, ids)
        self.assertEqual(result["requests"], [])
        self.assertEqual(set(result["finished_request_ids"]), set(ids) - {pending["request_id"]})
        self.assertEqual((await runtime.records.get(pending["request_id"]))["claim"], "busy-worker")


if __name__ == "__main__":
    unittest.main()
