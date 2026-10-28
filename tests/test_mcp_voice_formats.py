import base64
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.mcp_server import mcp


class DeclaredAudio(bytes):
    media_type = "audio/wav"


class McpVoiceFormatTests(unittest.IsolatedAsyncioTestCase):
    async def test_provider_audio_type_survives_the_native_task_result(self):
        execute = mcp._tool_manager.get_tool("execute_task").fn
        for audio, media_type in ((DeclaredAudio(b"RIFF synthetic WAV"), "audio/wav"),
                                  (b"synthetic MP3", "audio/mpeg")):
            with self.subTest(media_type=media_type):
                dispatcher = SimpleNamespace(
                    assignment=AsyncMock(return_value=SimpleNamespace(
                        provider="synthetic-voice", model="synthetic-tts", fallbacks=(),
                    )),
                    behaviors=SimpleNamespace(list=AsyncMock(return_value=[
                        SimpleNamespace(task="audio_voice", revision=1)
                    ])),
                    execute=AsyncMock(return_value=audio),
                )
                state = SimpleNamespace(task_dispatcher=dispatcher,
                                        storage=SimpleNamespace(mind=object()))
                settings = SimpleNamespace(read=AsyncMock(return_value={"rate": 1, "volume": 1}))
                with patch("aicognitive_mind.mcp_server.request_state", return_value=state), patch(
                    "aicognitive_mind.mcp_server.VoiceSettings", return_value=settings,
                ):
                    result = await execute(task="audio_voice", operation="synthesize_voice",
                                           text="Synthetic speech test.", ctx=object())
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["result"]["media_type"], media_type)
                self.assertEqual(base64.b64decode(result["result"]["audio_base64"]), audio)
