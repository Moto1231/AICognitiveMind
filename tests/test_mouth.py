import unittest
from pathlib import Path

from aicognitive_mind.api import app
from aicognitive_mind.body import (
    BodyRuntime,
    BrowserVoiceOutput,
    ExpressionIntent,
    ExpressionModality,
)


class MouthV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_voice_output_normalizes_transient_expression_intent(self) -> None:
        mouth = BrowserVoiceOutput()

        await mouth.speak(
            ExpressionIntent(
                modality=ExpressionModality.VOICE,
                text="  Hello world.  ",
                metadata={
                    "rate": 1.2,
                    "pitch": 0.9,
                    "volume": 0.8,
                    "voice_name": "Example Voice",
                },
            )
        )

        intent = mouth.consume()
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.modality, ExpressionModality.VOICE)
        self.assertEqual(intent.text, "Hello world.")
        self.assertEqual(intent.metadata["rate"], 1.2)
        self.assertEqual(intent.metadata["pitch"], 0.9)
        self.assertEqual(intent.metadata["volume"], 0.8)
        self.assertEqual(intent.metadata["voice_name"], "Example Voice")
        self.assertTrue(intent.metadata["transient"])
        self.assertEqual(intent.metadata["transport"], "browser-speech-synthesis")
        self.assertIsNone(mouth.consume())

    async def test_body_runtime_preserves_voice_metadata(self) -> None:
        mouth = BrowserVoiceOutput()
        runtime = BodyRuntime(voice=mouth)
        original = ExpressionIntent(
            modality=ExpressionModality.VOICE,
            text="Good morning.",
            metadata={"rate": 0.95, "pitch": 1.1, "volume": 1.0},
        )

        await runtime.speak_intent(original)

        delivered = mouth.consume()
        self.assertIsNotNone(delivered)
        assert delivered is not None
        self.assertEqual(delivered.text, "Good morning.")
        self.assertEqual(delivered.metadata["rate"], 0.95)
        self.assertEqual(delivered.metadata["pitch"], 1.1)

    async def test_mouth_rejects_non_voice_intent(self) -> None:
        mouth = BrowserVoiceOutput()
        runtime = BodyRuntime(voice=mouth)

        with self.assertRaisesRegex(ValueError, "voice ExpressionIntent"):
            await runtime.speak_intent(
                ExpressionIntent(
                    modality=ExpressionModality.AVATAR,
                    text="Not a mouth command.",
                )
            )

    async def test_mouth_rejects_empty_text_and_invalid_parameters(self) -> None:
        mouth = BrowserVoiceOutput()

        with self.assertRaisesRegex(ValueError, "requires text"):
            await mouth.speak(
                ExpressionIntent(
                    modality=ExpressionModality.VOICE,
                    text="   ",
                )
            )

        with self.assertRaisesRegex(ValueError, "rate must be between"):
            await mouth.speak(
                ExpressionIntent(
                    modality=ExpressionModality.VOICE,
                    text="Too fast.",
                    metadata={"rate": 11},
                )
            )

        with self.assertRaisesRegex(ValueError, "pitch must be between"):
            await mouth.speak(
                ExpressionIntent(
                    modality=ExpressionModality.VOICE,
                    text="Bad pitch.",
                    metadata={"pitch": -0.1},
                )
            )

        with self.assertRaisesRegex(ValueError, "volume must be between"):
            await mouth.speak(
                ExpressionIntent(
                    modality=ExpressionModality.VOICE,
                    text="Too loud.",
                    metadata={"volume": 1.1},
                )
            )

    async def test_mouth_status_reports_browser_speech_adapter(self) -> None:
        mouth = BrowserVoiceOutput()

        status = await mouth.status()

        self.assertEqual(status.device, "mouth")
        self.assertTrue(status.available)
        self.assertIn("browser speech", status.detail or "")

    def test_mouth_routes_and_browser_speech_surface_exist(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/body/mouth", paths)
        self.assertIn("/v1/body/mouth/speak", paths)
        self.assertIn("/v1/body/mouth/status", paths)
        self.assertIn("/v1/body/mouth/next", paths)

        markup = Path("src/aicognitive_mind/static/mouth.html").read_text(encoding="utf-8")
        self.assertIn("speechSynthesis", markup)
        self.assertIn("SpeechSynthesisUtterance", markup)
        self.assertIn("/v1/body/mouth/speak", markup)
        self.assertIn("/v1/body/mouth/next", markup)
        self.assertIn("MOUTH RECEIVED VOICE INTENT", markup)


if __name__ == "__main__":
    unittest.main()
