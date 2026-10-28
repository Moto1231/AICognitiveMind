import unittest
from unittest.mock import patch

import httpx

from aicognitive_mind.fish_audio import FishAudioRenderer


class FishAudioRendererTests(unittest.IsolatedAsyncioTestCase):
    async def test_official_origin_and_versioned_bases_reach_the_documented_tts_route(self):
        for base in (
            "https://api.fish.audio", "https://api.fish.audio/",
            "https://api.fish.audio/tts", "https://api.fish.audio/v1",
            "https://api.fish.audio/v1/", "https://api.fish.audio/v1/tts",
        ):
            with self.subTest(base=base):
                requests = []

                def handle(request):
                    requests.append(request)
                    return httpx.Response(200, content=b"synthetic-mp3")

                client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
                with patch("aicognitive_mind.fish_audio.httpx.AsyncClient", return_value=client):
                    result = await FishAudioRenderer(
                        api_key="synthetic-fish-key", endpoint_url=base,
                    ).synthesize("Synthetic voice test.")

                self.assertEqual(result, b"synthetic-mp3")
                self.assertEqual(str(requests[0].url), "https://api.fish.audio/v1/tts")
                self.assertEqual(requests[0].headers["model"], "s2.1-pro-free")

    async def test_custom_provider_path_and_query_are_preserved(self):
        requests = []

        def handle(request):
            requests.append(request)
            return httpx.Response(200, content=b"synthetic-mp3")

        client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
        with patch("aicognitive_mind.fish_audio.httpx.AsyncClient", return_value=client):
            await FishAudioRenderer(
                api_key="synthetic-proxy-key",
                endpoint_url="https://voice.example/custom/v1?route=speech",
            ).synthesize("Synthetic proxy test.")

        self.assertEqual(str(requests[0].url), "https://voice.example/custom/v1/tts?route=speech")
