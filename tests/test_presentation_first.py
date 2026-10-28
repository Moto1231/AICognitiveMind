import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aicognitive_mind.host_runtime import HostRuntime
from aicognitive_mind.storage import InMemoryMindStore


class PresentationFirstBodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_body_releases_frozen_response_while_completion_is_settling(self) -> None:
        completion_started = asyncio.Event()
        allow_completion = asyncio.Event()

        async def complete(*args, **kwargs):
            completion_started.set()
            await allow_completion.wait()
            return {
                "status": "interaction_committed",
                "occurred_at": "2026-10-27T12:00:00+00:00",
                "persistence_outcome": {"status": "succeeded"},
                "continuity_health": {"circuit_open": False},
                "presentation": {"allowed": True},
            }

        service = SimpleNamespace(
            begin_interaction=AsyncMock(return_value={
                "status": "ready_to_reason",
                "continuity_health": {"circuit_open": False},
            }),
            complete_interaction=AsyncMock(side_effect=complete),
        )
        host = HostRuntime(InMemoryMindStore(), service, timeout=2)
        lease = await host.attach("presentation-host", "test-model")
        awaiting_body = asyncio.create_task(host.submit("Speak now."))
        request = await host.next_request(lease["lease_token"])
        completing = asyncio.create_task(
            host.complete(lease["lease_token"], request["request_id"], "Frozen answer.")
        )

        await asyncio.wait_for(completion_started.wait(), 0.5)
        delivered = await asyncio.wait_for(awaiting_body, 0.75)
        self.assertEqual(delivered["response_text"], "Frozen answer.")
        self.assertEqual(delivered["persistence_status"], "pending")
        self.assertFalse(completing.done())

        allow_completion.set()
        completed = await asyncio.wait_for(completing, 0.75)
        self.assertEqual(completed["response_text"], "Frozen answer.")
        self.assertEqual(completed["persistence_status"], "succeeded")

    async def test_open_circuit_holds_response_until_recovery_succeeds(self) -> None:
        allow_completion = asyncio.Event()

        async def complete(*args, **kwargs):
            await allow_completion.wait()
            return {
                "status": "interaction_persistence_failed",
                "persistence_outcome": {
                    "status": "failed",
                    "failure_class": "ReviewUnavailable",
                },
                "continuity_health": {"circuit_open": True},
                "presentation": {"allowed": False},
            }

        service = SimpleNamespace(
            begin_interaction=AsyncMock(return_value={
                "status": "ready_to_reason",
                "continuity_health": {"circuit_open": True},
            }),
            complete_interaction=AsyncMock(side_effect=complete),
        )
        host = HostRuntime(InMemoryMindStore(), service, timeout=2)
        lease = await host.attach("recovery-host", "test-model")
        awaiting_body = asyncio.create_task(host.submit("Do not release this yet."))
        request = await host.next_request(lease["lease_token"])
        completing = asyncio.create_task(
            host.complete(lease["lease_token"], request["request_id"], "Held answer.")
        )

        await asyncio.sleep(0.05)
        self.assertFalse(awaiting_body.done())
        allow_completion.set()
        with self.assertRaisesRegex(RuntimeError, "not presented"):
            await completing
        with self.assertRaisesRegex(RuntimeError, "withheld"):
            await asyncio.wait_for(awaiting_body, 0.75)
