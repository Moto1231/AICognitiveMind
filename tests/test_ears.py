import base64
import unittest
from pathlib import Path

from aicognitive_mind.api import app
from aicognitive_mind.body import BodyRuntime, BrowserAudioIngress, SensoryModality


def audio_data_url(
    payload: bytes = b"audio-bytes",
    media_type: str = "audio/webm;codecs=opus",
) -> str:
    return f"data:{media_type};base64," + base64.b64encode(payload).decode("ascii")


class EarsV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_clip_becomes_transient_audio_percept(self) -> None:
        ears = BrowserAudioIngress()

        percept = ears.accept(
            audio_data_url=audio_data_url(),
            duration_ms=1250,
        )

        self.assertEqual(percept.modality, SensoryModality.AUDIO)
        self.assertEqual(percept.source, "browser-microphone")
        self.assertEqual(percept.summary, "Audio clip received from browser microphone.")
        self.assertEqual(percept.metadata["media_type"], "audio/webm")
        self.assertEqual(percept.metadata["duration_ms"], 1250)
        self.assertEqual(percept.metadata["byte_length"], len(b"audio-bytes"))
        self.assertTrue(percept.metadata["transient"])
        self.assertEqual(percept.metadata["transport"], "browser")

    async def test_body_hear_consumes_browser_clip_once(self) -> None:
        ears = BrowserAudioIngress()
        runtime = BodyRuntime(audio=ears)
        ears.accept(
            audio_data_url=audio_data_url(),
            duration_ms=900,
        )

        ready = await ears.status()
        self.assertTrue(ready.available)

        heard = await runtime.hear()
        self.assertEqual(heard.source, "browser-microphone")

        waiting = await ears.status()
        self.assertFalse(waiting.available)
        with self.assertRaisesRegex(RuntimeError, "No browser microphone observation is ready"):
            await runtime.hear()

    async def test_invalid_browser_audio_is_rejected(self) -> None:
        ears = BrowserAudioIngress()

        with self.assertRaisesRegex(ValueError, "base64 audio data URLs only"):
            ears.accept(
                audio_data_url="not-a-data-url",
                duration_ms=100,
            )

        with self.assertRaisesRegex(ValueError, "does not accept media type"):
            ears.accept(
                audio_data_url="data:text/plain;base64,AAAA",
                duration_ms=100,
            )

        with self.assertRaisesRegex(ValueError, "invalid base64"):
            ears.accept(
                audio_data_url="data:audio/webm;base64,not-valid-***",
                duration_ms=100,
            )

        with self.assertRaisesRegex(ValueError, "duration must be positive"):
            ears.accept(
                audio_data_url=audio_data_url(),
                duration_ms=0,
            )

        with self.assertRaisesRegex(ValueError, "30 second"):
            ears.accept(
                audio_data_url=audio_data_url(),
                duration_ms=30_001,
            )

    def test_browser_ears_routes_and_page_exist(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/body/ears", paths)
        self.assertIn("/v1/body/ears/observe", paths)
        self.assertIn("/v1/body/ears/status", paths)
        self.assertIn("/v1/body/ears/hear", paths)

        page = Path("src/aicognitive_mind/static/ears.html").read_text(encoding="utf-8")
        self.assertIn("navigator.mediaDevices.getUserMedia", page)
        self.assertIn("MediaRecorder", page)
        self.assertIn("/v1/body/ears/observe", page)
        self.assertIn("/v1/body/ears/hear", page)
        self.assertIn("BODY CAN HEAR", page)


if __name__ == "__main__":
    unittest.main()
