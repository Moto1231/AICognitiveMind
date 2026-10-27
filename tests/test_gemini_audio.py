import base64
import io
import json
import unittest
import wave

import httpx

from aicognitive_mind.gemini_audio import (
    GeminiAudioError, GeminiAudioRenderer, SynthesizedAudio, gemini_interactions_url,
    uses_gemini_speech,
)


def wav_fixture():
    output = io.BytesIO()
    with wave.open(output, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(24_000)
        stream.writeframes(b"\x01\x00\xff\xff" * 12)
    return output.getvalue()


def response_audio(payload, mime="audio/wav", **extra):
    return {"steps": [{"type": "model_output", "content": [{
        "type": "audio", "data": base64.b64encode(payload).decode(), "mime_type": mime, **extra,
    }]}]}


class GeminiAudioTests(unittest.IsolatedAsyncioTestCase):
    def renderer(self, client):
        return GeminiAudioRenderer(
            api_key="synthetic-private-gemini-key", model="models/gemini-3.8-flash-tts",
            endpoint_url="https://generativelanguage.googleapis.com/v1beta/openai", client=client,
        )

    async def test_native_protocol_keeps_selected_model_key_text_and_returns_real_wav(self):
        calls = []
        audio = wav_fixture()

        def respond(request):
            calls.append(request)
            return httpx.Response(200, json=response_audio(audio))

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            renderer = self.renderer(client)
            result = await renderer.synthesize("Verbatim spoken reply.", speed=1.2, volume=-4)
        self.assertIsInstance(result, bytes)
        self.assertIsInstance(result, SynthesizedAudio)
        self.assertEqual(result, audio)
        self.assertEqual(result.media_type, "audio/wav")
        request = calls[0]
        self.assertEqual(str(request.url), "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(request.headers["x-goog-api-key"], "synthetic-private-gemini-key")
        self.assertNotIn("Authorization", request.headers)
        body = json.loads(request.content)
        self.assertEqual(body["model"], "gemini-3.8-flash-tts")
        self.assertEqual(renderer.model, "models/gemini-3.8-flash-tts")
        self.assertNotIn("synthetic-private-gemini-key", repr(renderer))
        part = body["input"][0]["content"][0]
        self.assertEqual(part["text"], "Verbatim spoken reply.")
        self.assertEqual(part["annotations"][0]["type"], "speech_metadata")
        self.assertEqual(body["generation_config"]["speech_config"], [{"voice": "Kore"}])
        self.assertEqual(body["response_format"]["mime_type"], "audio/wav")

    async def test_raw_pcm_is_wrapped_in_playable_wav_with_actual_sample_rate(self):
        pcm = b"\x10\x00\xf0\xff" * 8
        for mime, extra, rate in (("audio/l16", {}, 24_000), ("audio/pcm;rate=16000", {}, 16_000),
                                  ("audio/l16", {"sample_rate": 8000}, 8000)):
            with self.subTest(mime=mime, rate=rate):
                async with httpx.AsyncClient(transport=httpx.MockTransport(
                    lambda request: httpx.Response(200, json=response_audio(pcm, mime, **extra)),
                )) as client:
                    result = await self.renderer(client).synthesize("Synthetic speech")
                self.assertEqual(result.media_type, "audio/wav")
                with wave.open(io.BytesIO(result), "rb") as stream:
                    self.assertEqual(stream.getframerate(), rate)
                    self.assertEqual(stream.getnchannels(), 1)
                    self.assertEqual(stream.getsampwidth(), 2)
                    self.assertEqual(stream.readframes(stream.getnframes()), pcm)

    async def test_invalid_or_missing_audio_and_provider_failures_are_honest(self):
        cases = [
            httpx.Response(429, json={"error": {"message": "synthetic-private-provider-detail"}}),
            httpx.Response(200, json={"steps": []}),
            httpx.Response(200, json=response_audio(b"not a WAV file")),
            httpx.Response(200, json=response_audio(b"odd", "audio/l16")),
            httpx.Response(200, json=response_audio(wav_fixture(), "audio/mpeg")),
            httpx.Response(200, json={"steps": [{"type": "model_output", "content": [{
                "type": "audio", "mime_type": "audio/wav", "data": "not base64!",
            }]}]}),
        ]
        for response in cases:
            with self.subTest(status=response.status_code):
                async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: response)) as client:
                    with self.assertRaises(GeminiAudioError) as error:
                        await self.renderer(client).synthesize("Synthetic reply")
                self.assertNotIn("synthetic-private", str(error.exception))

    def test_url_conversion_preserves_custom_origins_and_path_prefixes(self):
        for base, expected in (
            ("https://generativelanguage.googleapis.com", "https://generativelanguage.googleapis.com/v1beta/interactions"),
            ("https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "https://generativelanguage.googleapis.com/v1beta/interactions"),
            ("https://proxy.example/google/v1beta/openai", "https://proxy.example/google/v1beta/interactions"),
            ("https://proxy.example/google/v1beta/models", "https://proxy.example/google/v1beta/interactions"),
            ("https://proxy.example/google/interactions", "https://proxy.example/google/interactions"),
        ):
            with self.subTest(base=base):
                self.assertEqual(gemini_interactions_url(base), expected)
        self.assertTrue(uses_gemini_speech(base_url="https://proxy.example/google", provider_name="Google Gemini", model="saved-model"))
        self.assertFalse(uses_gemini_speech(base_url="https://api.fish.audio", provider_name="Fish Audio", model="s2-pro-free"))


if __name__ == "__main__":
    unittest.main()
