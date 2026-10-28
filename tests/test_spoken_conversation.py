import asyncio
import base64
import hashlib
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.body import BodyRuntime, BrowserAudioIngress, BrowserAvatarOutput, BrowserVoiceOutput
from aicognitive_mind.domain import InteractionResult
from aicognitive_mind.embodiment import MindBodyBridge
from aicognitive_mind.host_runtime import HostAwareCore, HostAwareInterpreter, HostRuntime
from aicognitive_mind.storage import InMemoryEvidenceStore, InMemoryJournalStore
from aicognitive_mind import api
from fastapi import HTTPException


class StructuredSpeechInterpreter:
    def __init__(self, *, text="Can you hear me?", changes=None):
        self.text, self.changes = text, changes or {}

    async def interpret_automatically(self, percept):
        return "Passive microphone observation."

    async def interpret_spoken_automatically(self, percept):
        evidence = percept.metadata["evidence"]
        return {
            "interpretation": "Grounded speech observation; not a conversational answer.",
            "derived_audio": {
                "source": "local_asr", "transcript": self.text, "model": "synthetic-asr",
                "sha256": evidence["sha256"], "captured_at": evidence["captured_at"],
                "segments": [{"text": self.text, "avg_logprob": -0.2, "no_speech_probability": 0.01}],
                **self.changes,
            },
        }


class SpokenConversationTests(unittest.IsolatedAsyncioTestCase):
    def percept(self):
        return BrowserAudioIngress().accept(
            audio_data_url="data:audio/webm;base64," + base64.b64encode(b"preserved speech").decode(),
            duration_ms=1000,
        )

    def bridge(self, interpreter=None, core=None):
        mouth, face = BrowserVoiceOutput(), BrowserAvatarOutput()
        core = core or SimpleNamespace(interact=AsyncMock(return_value=InteractionResult(
            response_text="Yes, your recording reached me.", occurred_at=datetime.now(UTC),
        )))
        bridge = MindBodyBridge(
            core=core, body=BodyRuntime(voice=mouth, avatar=face),
            interpreter=interpreter or StructuredSpeechInterpreter(),
            evidence=InMemoryEvidenceStore(), journal=InMemoryJournalStore(),
        )
        return bridge, core, mouth, face

    async def test_intentional_speech_uses_actual_transcript_and_queues_reply_once(self):
        bridge, core, mouth, face = self.bridge()
        result = await bridge.perceive(
            self.percept(), express=False, automatic=True, conversation=True,
        )
        self.assertEqual(result.response_text, "Yes, your recording reached me.")
        args = core.interact.await_args
        self.assertEqual(args.args, ("Can you hear me?",))
        self.assertEqual(args.kwargs["source"], "body:audio")
        context = args.kwargs["input_context"]
        self.assertTrue(context["intentional_conversation"])
        self.assertEqual(context["derived_audio"]["sha256"], result.evidence.sha256)
        self.assertEqual(context["speaker_identity"], "unresolved")
        self.assertEqual(context["addressee_identity"], "unresolved")
        self.assertEqual((mouth.consume()).text, result.response_text)
        self.assertEqual((face.consume()).text, result.response_text)
        self.assertIsNone(mouth.consume())
        core.interact.assert_awaited_once()

    async def test_default_audio_stays_passive_even_when_words_are_available(self):
        bridge, core, mouth, _face = self.bridge()
        result = await bridge.perceive(self.percept(), express=False, automatic=True)
        self.assertEqual(result.response_text, "")
        core.interact.assert_not_awaited()
        self.assertIsNone(mouth.consume())

    async def test_empty_and_clearly_uncertain_recognition_do_not_create_conversations(self):
        for text, changes in (
            ("", {}),
            ("Thank you", {"segments": [{"no_speech_probability": 0.8, "avg_logprob": -0.2}]}),
            ("Yes", {"segments": [{"no_speech_probability": 0.1, "avg_logprob": -1.5}]}),
        ):
            with self.subTest(text=text, changes=changes):
                bridge, core, mouth, _face = self.bridge(StructuredSpeechInterpreter(text=text, changes=changes))
                result = await bridge.perceive(self.percept(), automatic=True, conversation=True)
                self.assertEqual(result.response_text, "")
                core.interact.assert_not_awaited()
                self.assertIsNone(mouth.consume())

    async def test_spoken_provenance_mismatch_is_rejected_before_cognition(self):
        for changes in ({"sha256": "0" * 64}, {"captured_at": "2020-01-01T00:00:00Z"}):
            with self.subTest(changes=changes):
                bridge, core, mouth, _face = self.bridge(StructuredSpeechInterpreter(changes=changes))
                with self.assertRaisesRegex(ValueError, "does not match"):
                    await bridge.perceive(self.percept(), automatic=True, conversation=True)
                core.interact.assert_not_awaited()
                self.assertIsNone(mouth.consume())

    async def test_configured_specialist_transcribes_raw_audio_without_parsing_observation_prose(self):
        percept = self.percept()
        evidence = {
            "sha256": hashlib.sha256(b"preserved speech").hexdigest(),
            "captured_at": percept.observed_at.isoformat(),
        }
        percept = percept.model_copy(update={"metadata": {"evidence": evidence}})
        interpreter = HostAwareInterpreter(SimpleNamespace(), SimpleNamespace())
        dispatcher = SimpleNamespace(
            is_configured=AsyncMock(return_value=True),
            transcribe=AsyncMock(return_value="Actual specialist transcript"),
            interpret_percept=AsyncMock(),
        )
        interpreter.task_dispatcher = dispatcher
        details = await interpreter.interpret_spoken_automatically(percept)
        self.assertEqual(details["derived_audio"]["transcript"], "Actual specialist transcript")
        self.assertEqual(details["derived_audio"]["segments"], [])
        self.assertEqual(details["derived_audio"]["source"], "configured_asr")
        self.assertEqual(dispatcher.transcribe.await_args.kwargs["audio_bytes"], b"preserved speech")
        dispatcher.interpret_percept.assert_not_awaited()

    async def test_two_phase_host_handoff_preserves_one_conscious_lifecycle_and_expression(self):
        now = datetime.now(UTC).isoformat()
        service = SimpleNamespace(
            begin_interaction=AsyncMock(return_value={"status": "ready_to_reason"}),
            complete_interaction=AsyncMock(return_value={"status": "interaction_committed", "occurred_at": now}),
        )
        hosts = HostRuntime(SimpleNamespace(mind_id="synthetic-spoken-flow"), service)
        lease = (await hosts.attach("Synthetic shared host", "test"))["lease_token"]
        interpreter = HostAwareInterpreter(SimpleNamespace(), hosts)
        bridge, _core, mouth, face = self.bridge(interpreter, HostAwareCore(SimpleNamespace(), hosts))
        waiting = asyncio.create_task(bridge.perceive(
            self.percept(), express=False, automatic=True, conversation=True,
        ))
        try:
            async def pending_request():
                for _ in range(200):
                    requests = await hosts.records.pending()
                    if requests:
                        return requests[0]
                    await asyncio.sleep(0.005)
                self.fail("Expected a host request")

            passive = await pending_request()
            evidence = passive["input_context"]["evidence"]
            derived = {
                "source": "local_asr", "transcript": "Can you hear me?", "model": "synthetic-asr",
                "sha256": evidence["sha256"], "captured_at": evidence["captured_at"],
                "segments": [{"text": "Can you hear me?", "avg_logprob": -0.2, "no_speech_probability": 0.01}],
            }
            await hosts.records.replace(passive["request_id"], passive, {
                **passive, "input_context": {**passive["input_context"], "derived_audio": derived},
            })
            sensory = await hosts.next_request(lease)
            service.begin_interaction.assert_not_awaited()
            observed = await hosts.complete(lease, sensory["request_id"], "Speech observed.")
            self.assertEqual(observed["derived_audio"], derived)
            service.complete_interaction.assert_not_awaited()
            await pending_request()
            conversational = await hosts.next_request(lease)
            self.assertEqual(conversational["user_message"], "Can you hear me?")
            self.assertEqual(conversational["context"]["source"], "body:audio")
            self.assertEqual(conversational["context"]["input_context"]["derived_audio"], derived)
            service.begin_interaction.assert_awaited_once()
            await hosts.complete(lease, conversational["request_id"], "Yes, your recording reached me.")
            service.complete_interaction.assert_awaited_once()
            self.assertEqual(service.complete_interaction.await_args.kwargs["source"], "body:audio")
            self.assertEqual(service.complete_interaction.await_args.args[0], "Can you hear me?")
            result = await asyncio.wait_for(waiting, timeout=1)
            self.assertEqual((mouth.consume()).text, result.response_text)
            self.assertEqual((face.consume()).text, result.response_text)
            self.assertIsNone(mouth.consume())
        finally:
            waiting.cancel()
            await asyncio.gather(waiting, return_exceptions=True)

    async def test_cancelled_spoken_waiter_retires_owned_request_but_typed_text_stays_persistent(self):
        hosts = HostRuntime(SimpleNamespace(mind_id="synthetic-spoken-cancellation"), SimpleNamespace())
        await hosts.attach("Synthetic cancellation host", "test")
        for intentional, expected in ((True, "cancelled"), (False, "pending")):
            with self.subTest(intentional=intentional):
                task = asyncio.create_task(hosts.submit(
                    "Can you hear me?", source="body:audio" if intentional else "human",
                    input_context={"intentional_conversation": True} if intentional else None,
                ))
                for _ in range(100):
                    rows = await hosts.records.pending()
                    if rows:
                        break
                    await asyncio.sleep(0.001)
                record = max(rows, key=lambda row: row["created"])
                self.assertEqual(record["deadline"] is not None, intentional)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                self.assertEqual((await hosts.records.get(record["request_id"]))["state"], expected)

    async def test_spoken_host_phase_has_a_bounded_timeout(self):
        hosts = HostRuntime(SimpleNamespace(mind_id="synthetic-spoken-timeout"), SimpleNamespace(), timeout=0.01)
        await hosts.attach("Synthetic timeout host", "test")
        with self.assertRaisesRegex(RuntimeError, "Spoken conversation was not completed"):
            await hosts.submit(
                "Can you hear me?", source="body:audio", input_context={"intentional_conversation": True},
            )
        self.assertEqual(await hosts.records.pending(), [])

    async def test_browser_disconnect_cancels_the_spoken_perception_waiter(self):
        cancelled = asyncio.Event()

        async def perceive(*args, **kwargs):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.set()

        runtime = SimpleNamespace(
            browser_ears=SimpleNamespace(adapter=BrowserAudioIngress()),
            mind_body=SimpleNamespace(perceive=perceive),
        )
        request = SimpleNamespace(is_disconnected=AsyncMock(return_value=True))
        payload = api.BrowserAudioObservationRequest(
            audio_data_url="data:audio/webm;base64," + base64.b64encode(b"disconnect speech").decode(),
            duration_ms=1000, conversation=True,
        )
        with patch.object(api, "_request_runtime", return_value=runtime), patch.object(
            api, "_body_presence_scope", return_value=("synthetic", "spoken-disconnect"),
        ):
            with self.assertRaises(HTTPException) as raised:
                await api.receive_browser_audio_observation(payload, request)
        self.assertEqual(raised.exception.status_code, 499)
        self.assertTrue(cancelled.is_set())


if __name__ == "__main__":
    unittest.main()
