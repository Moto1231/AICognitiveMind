import base64
import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aicognitive_mind.api import app
from aicognitive_mind.body import (
    BodyRuntime,
    BrowserAudioIngress,
    BrowserAvatarOutput,
    BrowserVisionIngress,
    BrowserVoiceOutput,
)
from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.embodiment import (
    MindBodyBridge,
    OpenAIPerceptInterpreter,
)
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.storage import (
    InMemoryDiagnosticStore,
    InMemoryEvidenceStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


def data_url(media_type: str, payload: bytes) -> str:
    return f"data:{media_type};base64," + base64.b64encode(payload).decode("ascii")


class FixedInterpreter:
    def __init__(self, text: str) -> None:
        self.text = text
        self.percepts = []

    async def interpret(self, percept):
        self.percepts.append(percept)
        return self.text


class FailingInterpreter:
    async def interpret(self, percept):
        raise RuntimeError("interpretation failed")


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(output_text="A desk and a window are visible.")


class FakeTranscriptions:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(text="Hello from the microphone.")


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()
        self.audio = SimpleNamespace(transcriptions=FakeTranscriptions())


class MindBodyIntegrationV01Tests(unittest.IsolatedAsyncioTestCase):
    async def _core(self):
        journal = InMemoryJournalStore()
        core = CognitiveCore(
            mind=InMemoryMindStore(),
            journal=journal,
            memory=InMemoryMemoryStore(),
            diagnostics=InMemoryDiagnosticStore(),
            engine=EchoReasoningEngine(),
        )
        await core.initialize("AICognitiveMind")
        return core, journal

    async def test_visual_percept_crosses_mind_and_returns_through_body_outputs(self) -> None:
        core, journal = await self._core()
        eyes = BrowserVisionIngress()
        mouth = BrowserVoiceOutput()
        face = BrowserAvatarOutput()
        body = BodyRuntime(vision=eyes, voice=mouth, avatar=face)
        interpreter = FixedInterpreter("Visual perception: A person is standing by a window.")
        evidence = InMemoryEvidenceStore()
        bridge = MindBodyBridge(
            core=core,
            body=body,
            interpreter=interpreter,
            evidence=evidence,
            journal=journal,
        )

        eyes.accept(
            image_data_url=data_url("image/jpeg", b"jpeg"),
            width=640,
            height=480,
        )

        result = await bridge.see()

        self.assertEqual(
            result.interpretation,
            "Visual perception: A person is standing by a window.",
        )
        self.assertEqual(
            result.response_text,
            "I heard: Visual perception: A person is standing by a window.",
        )
        self.assertEqual(result.evidence.media_type, "image/jpeg")
        self.assertEqual(result.evidence.sha256, hashlib.sha256(b"jpeg").hexdigest())

        preserved = await evidence.find_exact(
            sha256=result.evidence.sha256,
            captured_at=result.evidence.captured_at,
        )
        self.assertIsNotNone(preserved)
        assert preserved is not None
        self.assertEqual(base64.b64decode(preserved.payload_base64), b"jpeg")

        mouth_intent = mouth.consume()
        face_intent = face.consume()
        self.assertIsNotNone(mouth_intent)
        self.assertIsNotNone(face_intent)
        assert mouth_intent is not None
        assert face_intent is not None
        self.assertEqual(mouth_intent.text, result.response_text)
        self.assertEqual(face_intent.text, result.response_text)

        entries = await journal.read()
        interaction = entries[-1]
        input_document = interaction.experience["input"]
        self.assertEqual(input_document["source"], "body:vision")
        self.assertEqual(input_document["context"]["modality"], "vision")
        self.assertEqual(input_document["context"]["source"], "browser-camera")
        self.assertEqual(
            input_document["context"]["evidence"]["sha256"],
            hashlib.sha256(b"jpeg").hexdigest(),
        )
        self.assertNotIn("content_ref", str(input_document))
        self.assertNotIn("data:image", str(input_document))

    async def test_audio_percept_crosses_same_mind_body_bridge(self) -> None:
        core, journal = await self._core()
        ears = BrowserAudioIngress()
        mouth = BrowserVoiceOutput()
        face = BrowserAvatarOutput()
        body = BodyRuntime(audio=ears, voice=mouth, avatar=face)
        evidence = InMemoryEvidenceStore()
        bridge = MindBodyBridge(
            core=core,
            body=body,
            interpreter=FixedInterpreter("Auditory perception: Good morning."),
            evidence=evidence,
            journal=journal,
        )

        ears.accept(
            audio_data_url=data_url("audio/webm", b"audio"),
            duration_ms=800,
        )

        result = await bridge.hear()

        self.assertEqual(result.sensory_modality.value, "audio")
        self.assertEqual(result.evidence.media_type, "audio/webm")
        self.assertEqual(result.evidence.sha256, hashlib.sha256(b"audio").hexdigest())
        self.assertEqual(result.response_text, "I heard: Auditory perception: Good morning.")
        entries = await journal.read()
        self.assertEqual(entries[-1].experience["input"]["source"], "body:audio")

    async def test_evidence_survives_even_when_interpretation_fails(self) -> None:
        core, journal = await self._core()
        eyes = BrowserVisionIngress()
        evidence = InMemoryEvidenceStore()
        body = BodyRuntime(vision=eyes)
        bridge = MindBodyBridge(
            core=core,
            body=body,
            interpreter=FailingInterpreter(),
            evidence=evidence,
            journal=journal,
        )

        percept = eyes.accept(
            image_data_url=data_url("image/jpeg", b"failed-interpretation-image"),
            width=320,
            height=240,
        )

        with self.assertRaisesRegex(RuntimeError, "interpretation failed"):
            await bridge.see()

        sha256 = hashlib.sha256(b"failed-interpretation-image").hexdigest()
        preserved = await evidence.find_exact(
            sha256=sha256,
            captured_at=percept.observed_at,
        )
        self.assertIsNotNone(preserved)
        entries = await journal.read()
        sensory = entries[-1]
        self.assertEqual(sensory.kind.value, "sensory_evidence")
        self.assertEqual(sensory.experience["status"], "admitted")
        self.assertEqual(sensory.experience["evidence"]["sha256"], sha256)

    async def test_openai_interpreter_sends_image_as_multimodal_input(self) -> None:
        client = FakeOpenAIClient()
        interpreter = OpenAIPerceptInterpreter(
            "test-key",
            vision_model="test-vision-model",
            client=client,
        )
        eyes = BrowserVisionIngress()
        percept = eyes.accept(
            image_data_url=data_url("image/jpeg", b"jpeg"),
            width=100,
            height=100,
        )

        interpretation = await interpreter.interpret(percept)

        self.assertEqual(interpretation, "Visual perception: A desk and a window are visible.")
        request = client.responses.calls[0]
        self.assertEqual(request["model"], "test-vision-model")
        content = request["input"][0]["content"]
        self.assertEqual(content[1]["type"], "input_image")
        self.assertTrue(content[1]["image_url"].startswith("data:image/jpeg;base64,"))

    async def test_openai_interpreter_transcribes_audio_on_mind_side(self) -> None:
        client = FakeOpenAIClient()
        interpreter = OpenAIPerceptInterpreter(
            "test-key",
            vision_model="test-vision-model",
            transcription_model="test-transcription-model",
            client=client,
        )
        ears = BrowserAudioIngress()
        percept = ears.accept(
            audio_data_url=data_url("audio/webm", b"audio"),
            duration_ms=500,
        )

        interpretation = await interpreter.interpret(percept)

        self.assertEqual(interpretation, "Auditory perception: Hello from the microphone.")
        request = client.audio.transcriptions.calls[0]
        self.assertEqual(request["model"], "test-transcription-model")
        filename, payload, media_type = request["file"]
        self.assertEqual(filename, "percept.webm")
        self.assertEqual(payload, b"audio")
        self.assertEqual(media_type, "audio/webm")

    def test_live_body_routes_and_browser_surface_exist(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/body/live", paths)
        self.assertIn("/v1/mind/body/see", paths)
        self.assertIn("/v1/mind/body/hear", paths)
        self.assertIn("/v1/evidence/{sha256}", paths)
        self.assertIn("/v1/evidence/{sha256}/metadata", paths)

        markup = Path("src/aicognitive_mind/static/live_body.html").read_text(
            encoding="utf-8"
        )
        self.assertIn("/v1/body/eyes/observe", markup)
        self.assertIn("/v1/mind/body/see", markup)
        self.assertIn("/v1/body/ears/observe", markup)
        self.assertIn("/v1/mind/body/hear", markup)
        self.assertIn("/v1/body/face/next", markup)
        self.assertIn("/v1/body/mouth/next", markup)
        self.assertIn("MIND ↔ BODY LOOP COMPLETE", markup)
        self.assertIn("Open evidence artifact", markup)
        self.assertIn("/v1/evidence/", markup)


if __name__ == "__main__":
    unittest.main()
