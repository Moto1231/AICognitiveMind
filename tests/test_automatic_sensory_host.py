import asyncio
import base64
import hashlib
import time
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from aicognitive_mind.body import Percept, SensoryModality
from aicognitive_mind.host_runtime import HostAwareInterpreter, HostRuntime
from aicognitive_mind.task_dispatcher import TaskDispatchError


class AutomaticSensoryHostTests(unittest.IsolatedAsyncioTestCase):
    def make_percept(self, modality="vision", *, payload=b"preserved media"):
        captured_at = datetime(2026, 10, 26, 20, 0, tzinfo=UTC)
        media_type = "image/jpeg" if modality == "vision" else "audio/webm"
        evidence = {
            "sha256": hashlib.sha256(payload).hexdigest(),
            "captured_at": captured_at.isoformat(),
            "media_type": media_type,
            "modality": modality,
            "source": "test camera" if modality == "vision" else "test microphone",
        }
        return Percept(
            modality=SensoryModality(modality),
            source=evidence["source"],
            observed_at=captured_at,
            content_ref=f"data:{media_type};base64," + base64.b64encode(payload).decode(),
            metadata={"evidence": evidence},
        )

    def make_interpreter(self, hosts, *, configured=False, result=None, failure=None):
        interpreter = HostAwareInterpreter(SimpleNamespace(), hosts)
        interpreter.task_dispatcher = SimpleNamespace(
            is_configured=AsyncMock(return_value=configured),
            interpret_percept=AsyncMock(return_value=result, side_effect=failure),
        )
        return interpreter

    async def wait_for_queue(self, runtime, count):
        for _ in range(100):
            rows = await runtime.records.pending()
            if len(rows) == count:
                return rows
            await asyncio.sleep(0.001)
        self.fail(f"Expected {count} queued requests")

    async def test_unassigned_vision_and_audio_use_passive_host_context_with_evidence(self):
        for modality in ("vision", "audio"):
            with self.subTest(modality=modality):
                hosts = SimpleNamespace(
                    active=AsyncMock(return_value={"name": "Connected model"}),
                    submit=AsyncMock(return_value={"response_text": "  Grounded observation.  "}),
                )
                interpreter = self.make_interpreter(hosts)
                percept = self.make_percept(modality)

                result = await interpreter.interpret_automatically(percept, focus="What changed?")

                self.assertEqual(result, "Grounded observation.")
                interpreter.task_dispatcher.is_configured.assert_awaited_once_with(modality)
                interpreter.task_dispatcher.interpret_percept.assert_not_awaited()
                prompt = hosts.submit.await_args.args[0]
                options = hosts.submit.await_args.kwargs
                self.assertIn(f"Interpret this {modality} percept", prompt)
                self.assertIn("What changed?", prompt)
                self.assertEqual(options["priority"], 10)
                self.assertEqual(options["task"], "sensory_interpretation")
                self.assertEqual(options["input_context"]["evidence"], percept.metadata["evidence"])
                self.assertEqual(options["input_context"]["modality"], modality)

    async def test_configured_specialist_remains_authoritative(self):
        hosts = SimpleNamespace(active=AsyncMock(), submit=AsyncMock())
        percept = self.make_percept()
        interpreter = self.make_interpreter(hosts, configured=True, result="Selected model result")

        self.assertEqual(await interpreter.interpret_automatically(percept), "Selected model result")
        interpreter.task_dispatcher.interpret_percept.assert_awaited_once_with(percept, focus=None)
        hosts.active.assert_not_awaited()
        hosts.submit.assert_not_awaited()

    async def test_failed_configured_specialist_does_not_silently_change_routes(self):
        hosts = SimpleNamespace(active=AsyncMock(), submit=AsyncMock())
        interpreter = self.make_interpreter(
            hosts, configured=True, failure=TaskDispatchError("Configured fallback chain failed")
        )

        with self.assertRaisesRegex(RuntimeError, "configured task endpoint.*fallback chain failed"):
            await interpreter.interpret_automatically(self.make_percept())
        hosts.active.assert_not_awaited()
        hosts.submit.assert_not_awaited()

    async def test_no_specialist_or_attached_host_fails_without_enqueuing(self):
        hosts = SimpleNamespace(active=AsyncMock(return_value=None), submit=AsyncMock())
        interpreter = self.make_interpreter(hosts)

        with self.assertRaisesRegex(RuntimeError, "No external reasoning host.*automatic audio"):
            await asyncio.wait_for(
                interpreter.interpret_automatically(self.make_percept("audio")), timeout=0.1
            )
        hosts.submit.assert_not_awaited()

    async def test_large_media_handoff_retains_trusted_locator_and_omits_inline_payload(self):
        hosts = SimpleNamespace(
            active=AsyncMock(return_value={"name": "Connected model"}),
            submit=AsyncMock(return_value={"response_text": "Observed original evidence."}),
        )
        interpreter = self.make_interpreter(hosts)
        percept = self.make_percept(payload=b"x" * 100_000)

        await interpreter.interpret_automatically(percept)

        prompt = hosts.submit.await_args.args[0]
        self.assertNotIn(percept.content_ref, prompt)
        self.assertIn("inline media omitted", prompt)
        self.assertIn(percept.metadata["evidence"]["sha256"], prompt)
        self.assertEqual(
            hosts.submit.await_args.kwargs["input_context"]["evidence"],
            percept.metadata["evidence"],
        )

    async def test_automatic_handoff_requires_preserved_reference(self):
        hosts = SimpleNamespace(active=AsyncMock(return_value={"name": "Connected model"}),
                                submit=AsyncMock())
        interpreter = self.make_interpreter(hosts)
        percept = self.make_percept().model_copy(update={"metadata": {}})
        with self.assertRaisesRegex(RuntimeError, "preserved evidence reference"):
            await interpreter.interpret_automatically(percept)
        hosts.submit.assert_not_awaited()

    async def test_failed_passive_worker_claim_expires_and_can_be_reclaimed(self):
        service = SimpleNamespace(begin_interaction=AsyncMock(), complete_interaction=AsyncMock())
        runtime = HostRuntime(SimpleNamespace(mind_id="reclaim-sensory"), service)
        lease = (await runtime.attach("Connected model", "model-selected"))["lease_token"]
        interpreter = self.make_interpreter(runtime)
        task = asyncio.create_task(interpreter.interpret_automatically(self.make_percept()))
        try:
            await self.wait_for_queue(runtime, 1)
            first = await runtime.next_request(lease)
            claimed = await runtime.records.get(first["request_id"])
            self.assertIsNone(claimed["deadline"])
            self.assertGreater(claimed["claim_until"], time.time())
            self.assertLessEqual(claimed["claim_until"], time.time() + runtime.timeout)
            expired = {**claimed, "claim_until": time.time() - 1}
            self.assertTrue(await runtime.records.replace(first["request_id"], claimed, expired))

            reclaimed = await runtime.next_request(lease)

            self.assertEqual(reclaimed["request_id"], first["request_id"])
            self.assertEqual(reclaimed["context"]["task"], "sensory_interpretation")
            service.begin_interaction.assert_not_awaited()
            await runtime.complete(lease, reclaimed["request_id"], "Recovered observation")
            self.assertEqual(await asyncio.wait_for(task, timeout=1), "Recovered observation")
            service.complete_interaction.assert_not_awaited()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_parallel_passive_claims_keep_human_priority_and_skip_conscious_lifecycle(self):
        service = SimpleNamespace(
            begin_interaction=AsyncMock(return_value={"status": "ready_to_reason"}),
            complete_interaction=AsyncMock(return_value={"occurred_at": "2026-10-26T20:00:00Z"}),
        )
        runtime = HostRuntime(SimpleNamespace(mind_id="parallel-sensory"), service)
        lease = (await runtime.attach("Connected model", "model-selected"))["lease_token"]
        interpreter = self.make_interpreter(runtime)
        tasks = [
            asyncio.create_task(interpreter.interpret_automatically(self.make_percept())),
            asyncio.create_task(interpreter.interpret_automatically(self.make_percept("audio"))),
            asyncio.create_task(runtime.submit("Interpret this vision percept (human input)")),
        ]
        try:
            await self.wait_for_queue(runtime, 3)
            human = await runtime.next_request(lease)
            self.assertEqual(human["user_message"], "Interpret this vision percept (human input)")
            service.begin_interaction.assert_awaited_once_with(
                "Interpret this vision percept (human input)"
            )

            first, second = await asyncio.gather(
                runtime.next_request(lease), runtime.next_request(lease)
            )
            self.assertNotEqual(first["request_id"], second["request_id"])
            for request in (first, second):
                self.assertEqual(request["context"]["task"], "sensory_interpretation")
                self.assertIn("evidence", request["context"]["input_context"])
            service.begin_interaction.assert_awaited_once()
            service.complete_interaction.assert_not_awaited()

            with self.assertRaisesRegex(ValueError, "nonblank observation"):
                await runtime.complete(lease, first["request_id"], "  ")
            with self.assertRaisesRegex(ValueError, "does not accept memory proposals"):
                await runtime.complete(lease, first["request_id"], "Observed", ({"content": "x"},))
            first_result, second_result = await asyncio.gather(
                runtime.complete(lease, first["request_id"], "First grounded observation"),
                runtime.complete(lease, second["request_id"], "Second grounded observation"),
            )
            self.assertEqual(
                await runtime.complete(lease, first["request_id"], "  First grounded observation  "),
                first_result,
            )
            self.assertTrue(first_result["occurred_at"])
            self.assertTrue(second_result["occurred_at"])
            service.complete_interaction.assert_not_awaited()
            await runtime.complete(lease, human["request_id"], "Human response")
            service.complete_interaction.assert_awaited_once()
            results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=1)
            self.assertEqual(set(results[:2]), {"First grounded observation", "Second grounded observation"})
            self.assertEqual(results[2]["response_text"], "Human response")
            self.assertEqual(await runtime.records.pending(), [])
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    unittest.main()
