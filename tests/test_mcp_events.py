import asyncio
import base64
import hashlib
import hmac
import json
import socket
import time
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from mcp.shared.exceptions import MCPError

from aicognitive_mind.host_runtime import HostAwareCore, HostRuntime, RuntimeRecords
from aicognitive_mind.mcp_events import (
    EVENT_NAME, STATE_KEY, MessageEvents, SubscribeParams, UnsubscribeParams,
    _callback_target, event_owner, post_webhook,
)

SECRET = "whsec_" + base64.b64encode(bytes(range(32))).decode()
OWNER = {"id": "owner-one", "client_id": "chatgpt", "subject": "mind", "issuer": "https://axiom.example"}


def params(**updates):
    value = {
        "name": EVENT_NAME, "arguments": {},
        "delivery": {"mode": "webhook", "url": "https://chatgpt.example/events/one", "secret": SECRET},
    }
    value.update(updates)
    return SubscribeParams.model_validate(value)


def message(key="message-one", **updates):
    return {
        "kind": "body_request", "request_id": key, "message": "Hello Axiom",
        "body_session": "phone", "priority": 0, "created": time.time(),
        "state": "pending", "claim": "", "claim_until": 0.0, "result": {},
        "deadline": None, "notify_message_event": True, **updates,
    }


class MessageEventTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mind = SimpleNamespace(mind_id="axiom")
        self.records = RuntimeRecords(self.mind)
        self.delivered = []

        async def post(url, secret, event_id, payload, sub_id, previous_secret=None):
            self.delivered.append((url, secret, event_id, deepcopy(payload), sub_id, previous_secret))
            return 200, json.dumps({"challenge": payload.get("challenge")}).encode()

        self.post = AsyncMock(side_effect=post)
        self.events = MessageEvents(self.records, post=self.post)

    async def add(self, **updates):
        return await self.events.subscribe(OWNER, params(**updates))

    async def test_verified_subscription_is_durable_idempotent_and_private(self):
        first = await self.add()
        second = await self.add()
        self.assertEqual(first["id"], second["id"])
        self.assertEqual(self.post.await_count, 1)
        self.assertEqual(self.delivered[0][3]["type"], "verification")
        restored = MessageEvents(RuntimeRecords(self.mind), post=self.post)
        self.assertTrue(await restored.enabled("phone"))
        state = await self.records.get(STATE_KEY)
        self.assertEqual(len(state["subscriptions"]), 1)
        self.assertNotIn("secret", first)
        self.assertNotIn("url", first)

    async def test_failed_challenge_cannot_activate_subscription(self):
        self.events.post = AsyncMock(return_value=(200, b'{"challenge":"wrong"}'))
        with self.assertRaises(MCPError):
            await self.add()
        self.assertFalse(await self.events.enabled())
        self.assertIsNone(await self.records.get(STATE_KEY))

    async def test_invalid_signing_key_is_rejected_before_network(self):
        invalid = params(delivery={"mode": "webhook", "url": "https://chatgpt.example/event", "secret": "whsec_dGlueQ=="})
        with self.assertRaises(ValueError):
            await self.events.subscribe(OWNER, invalid)
        self.post.assert_not_awaited()

    async def test_filter_and_event_payload_only_include_matching_human_messages(self):
        await self.add(arguments={"session_id": "phone"})
        accepted = message()
        ignored = message("sensory", priority=10)
        other = message("other-session", body_session="desktop")
        for request in (accepted, ignored, other):
            await self.records.create(request["request_id"], request)
            await self.events.enqueue(request)
        await self.events.flush()
        deliveries = [item for item in self.delivered if item[3].get("name") == EVENT_NAME]
        self.assertEqual(len(deliveries), 1)
        event = deliveries[0][3]
        self.assertEqual(event["data"]["request_id"], accepted["request_id"])
        self.assertEqual(event["data"]["session_id"], "phone")
        self.assertEqual(event["eventId"], "evt_" + accepted["request_id"])
        self.assertEqual(event["data"]["text"], accepted["message"])
        self.assertEqual(event["data"]["mind_id"], "axiom")

    async def test_transient_failure_survives_restart_and_reuses_event_id(self):
        await self.add()
        request = message()
        await self.records.create(request["request_id"], request)
        await self.events.enqueue(request)
        failed = AsyncMock(return_value=(503, b""))
        self.events.post = failed
        await self.events.flush()
        state = await self.records.get(STATE_KEY)
        delivery = next(iter(state["deliveries"].values()))
        self.assertEqual(delivery["attempts"], 1)
        self.assertEqual(delivery["state"], "pending")
        event_id = delivery["event"]["eventId"]
        before = deepcopy(state)
        for item in state["deliveries"].values():
            item["next_attempt"] = 0
        self.assertTrue(await self.records.replace(STATE_KEY, before, state))
        restored = MessageEvents(RuntimeRecords(self.mind), post=self.post)
        await restored.flush()
        self.assertEqual(self.delivered[-1][2], event_id)
        self.assertEqual((await self.records.get(STATE_KEY))["deliveries"], {})

    async def test_crash_between_queue_and_outbox_is_recovered(self):
        await self.add()
        request = message()
        await self.records.create(request["request_id"], request)
        await MessageEvents(self.records, post=self.post).flush()
        self.assertTrue((await self.records.get(request["request_id"]))["message_event_enqueued"])
        self.assertEqual(self.delivered[-1][3]["data"]["request_id"], request["request_id"])

    async def test_unsubscribe_is_owner_scoped_idempotent_and_cancels_deliveries(self):
        await self.add()
        request = message()
        await self.records.create(request["request_id"], request)
        await self.events.enqueue(request)
        cancel = UnsubscribeParams.model_validate({
            "name": EVENT_NAME, "arguments": {},
            "delivery": {"mode": "webhook", "url": params().delivery.url},
        })
        await self.events.unsubscribe({**OWNER, "id": "different-owner"}, cancel)
        self.assertTrue(await self.events.enabled())
        await self.events.unsubscribe(OWNER, cancel)
        await self.events.unsubscribe(OWNER, cancel)
        self.assertFalse(await self.events.enabled())
        self.assertEqual((await self.records.get(STATE_KEY))["deliveries"], {})

    async def test_expiration_and_revoked_owner_stop_delivery(self):
        await self.add()
        request = message()
        await self.records.create(request["request_id"], request)
        await self.events.enqueue(request)
        self.events.authorized = AsyncMock(return_value=False)
        count = len(self.delivered)
        await self.events.flush()
        self.assertEqual(len(self.delivered), count)
        self.assertFalse(await self.events.enabled())
        await self.add()
        state = await self.records.get(STATE_KEY)
        before = deepcopy(state)
        for sub in state["subscriptions"].values():
            sub["expires_at"] = 0
        await self.records.replace(STATE_KEY, before, state)
        await self.events.flush()
        self.assertFalse(await self.events.enabled())

    async def test_terminal_responses_are_not_retried(self):
        for status in (410, 413):
            with self.subTest(status=status):
                self.events.post = self.post
                await self.add()
                request = message("terminal-" + str(status))
                await self.records.create(request["request_id"], request)
                await self.events.enqueue(request)
                self.events.post = AsyncMock(return_value=(status, b""))
                await self.events.flush()
                count = self.events.post.await_count
                await self.events.flush()
                self.assertEqual(self.events.post.await_count, count)

    async def test_signing_key_rotation_verifies_and_temporarily_signs_both_keys(self):
        await self.add()
        rotated = "whsec_" + base64.b64encode(b"x" * 32).decode()
        await self.add(delivery={"mode": "webhook", "url": params().delivery.url, "secret": rotated})
        self.assertEqual(self.post.await_count, 2)
        request = message()
        await self.records.create(request["request_id"], request)
        await self.events.enqueue(request)
        await self.events.flush()
        self.assertEqual(self.delivered[-1][1], rotated)
        self.assertEqual(self.delivered[-1][5], SECRET)


class CallbackSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_dns_private_loopback_and_mixed_answers_are_blocked(self):
        loop = asyncio.get_running_loop()
        for addresses in (["127.0.0.1"], ["10.0.0.2"], ["169.254.169.254"],
                          ["93.184.216.34", "127.0.0.1"], ["::1"], ["fe80::1"]):
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443)) for ip in addresses]
            with self.subTest(addresses=addresses), patch.object(loop, "getaddrinfo", AsyncMock(return_value=answers)):
                with self.assertRaises(ValueError):
                    await _callback_target("https://callback.example/hook")

    async def test_non_https_credentials_and_nonstandard_ports_are_blocked(self):
        for url in ("http://example.com/hook", "https://user:pass@example.com/hook",
                    "https://example.com:8443/hook", "https://example.com/hook#fragment"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                await _callback_target(url)

    async def test_wire_body_signature_dns_pin_sni_and_no_redirects(self):
        captured = {}

        class Reply:
            status_code = 200

            async def aiter_bytes(self):
                yield b"{}"

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        class Client:
            def __init__(self, **kwargs):
                captured["client"] = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            def stream(self, method, url, **kwargs):
                captured.update({"method": method, "url": url, **kwargs})
                return Reply()

        with patch("aicognitive_mind.mcp_events._callback_target", AsyncMock(
            return_value=("https://93.184.216.34/hook?key=opaque", "callback.example", "callback.example")
        )), patch("aicognitive_mind.mcp_events.httpx.AsyncClient", Client):
            await post_webhook("https://callback.example/hook?key=opaque", SECRET,
                               "evt_one", {"text": "Hello Will"}, "sub_one")
        self.assertEqual(captured["url"], "https://93.184.216.34/hook?key=opaque")
        self.assertEqual(captured["headers"]["Host"], "callback.example")
        self.assertEqual(captured["extensions"]["sni_hostname"], "callback.example")
        self.assertFalse(captured["client"]["follow_redirects"])
        self.assertFalse(captured["client"]["trust_env"])
        headers = captured["headers"]
        signed = b"evt_one." + headers["webhook-timestamp"].encode() + b"." + captured["content"]
        expected = base64.b64encode(hmac.digest(bytes(range(32)), signed, "sha256")).decode()
        self.assertEqual(headers["webhook-signature"], "v1," + expected)
        self.assertEqual(headers["X-MCP-Subscription-Id"], "sub_one")

    def test_another_oauth_account_cannot_read_root_events(self):
        provider = SimpleNamespace(username="mind", required_scope="axiom:mind",
                                   resource_url="https://axiom.example/axiom-mcp")
        token = SimpleNamespace(subject="another-mind", scopes=["axiom:mind"],
                                resource=provider.resource_url)
        with patch("aicognitive_mind.mcp_events.get_access_token", return_value=token):
            with self.assertRaises(MCPError):
                event_owner(provider, "axiom")


class EventMessageHandoffTests(unittest.IsolatedAsyncioTestCase):
    async def test_message_can_wake_without_live_host_and_completes_once(self):
        mind = SimpleNamespace(mind_id="axiom")
        service = SimpleNamespace(complete_interaction=AsyncMock(
            return_value={"occurred_at": "2026-10-18T08:00:00Z"}
        ))
        hosts = HostRuntime(mind, service)
        events = MessageEvents(hosts.records, post=AsyncMock(side_effect=lambda *a: (
            200, json.dumps({"challenge": a[3].get("challenge")}).encode()
        )))
        await events.subscribe(OWNER, params())
        fallback = SimpleNamespace(interact=AsyncMock())
        core = HostAwareCore(fallback, hosts)
        task = asyncio.create_task(core.interact("Hello from the Body"))
        try:
            for _ in range(100):
                pending = await hosts.records.pending()
                if pending:
                    break
                await asyncio.sleep(0.001)
            self.assertEqual(len(pending), 1)
            request_id = pending[0]["request_id"]
            claim = await hosts.claim_incoming_message(request_id)
            self.assertEqual(claim["status"], "claimed")
            self.assertEqual((await hosts.claim_incoming_message(request_id))["status"], "in_progress")
            result = await hosts.complete_incoming_message(claim["claim_token"], request_id, "Hello Will")
            await hosts.complete_incoming_message(claim["claim_token"], request_id, "Hello Will")
            self.assertEqual((await task).response_text, "Hello Will")
            self.assertEqual(result["response_text"], "Hello Will")
            self.assertEqual((await hosts.claim_incoming_message(request_id))["status"], "already_complete")
            service.complete_interaction.assert_awaited_once()
            fallback.interact.assert_not_awaited()
            self.assertIsNone(await hosts.active())
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_event_claim_cannot_take_live_claim_or_use_another_claim_token(self):
        hosts = HostRuntime(SimpleNamespace(mind_id="axiom"), SimpleNamespace())
        request = message(claim="live-host", claim_until=None)
        await hosts.records.create(request["request_id"], request)
        self.assertEqual((await hosts.claim_incoming_message(request["request_id"]))["status"], "in_progress")
        with self.assertRaises(PermissionError):
            await hosts.complete_incoming_message("wrong", request["request_id"], "no")

    async def test_failed_task_can_release_and_message_can_be_reclaimed(self):
        hosts = HostRuntime(SimpleNamespace(mind_id="axiom"), SimpleNamespace())
        request = message()
        await hosts.records.create(request["request_id"], request)
        first = await hosts.claim_incoming_message(request["request_id"])
        await hosts.release_incoming_message(first["claim_token"], request["request_id"])
        second = await hosts.claim_incoming_message(request["request_id"])
        self.assertEqual(second["status"], "claimed")
        self.assertNotEqual(first["claim_token"], second["claim_token"])

    async def test_sensory_request_is_not_claimed_as_human_message(self):
        hosts = HostRuntime(SimpleNamespace(mind_id="axiom"), SimpleNamespace())
        request = message(priority=10)
        await hosts.records.create(request["request_id"], request)
        with self.assertRaises(ValueError):
            await hosts.claim_incoming_message(request["request_id"])


if __name__ == "__main__":
    unittest.main()
