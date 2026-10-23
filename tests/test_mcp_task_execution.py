import base64
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.mcp_server import execute_task
from aicognitive_mind.task_behaviors import default_task_behaviors
from aicognitive_mind.task_dispatcher import TaskDispatchError


class FakeDispatcher:
    def __init__(self):
        self.assignments = SimpleNamespace()
        self.behaviors = SimpleNamespace(list=self.list_behaviors)
        self.calls = []

    async def assignment(self, task):
        return SimpleNamespace(provider="provider-a", model="model-a")

    async def list_behaviors(self):
        return [
            item.model_copy(update={"revision": 3}) if item.task == "vision" else item
            for item in default_task_behaviors()
        ]

    async def execute(self, context, payload):
        self.calls.append((context, payload))
        return "recognized result"


class McpTaskExecutionTests(unittest.IsolatedAsyncioTestCase):
    def make_context(self, dispatcher):
        state = SimpleNamespace(task_dispatcher=dispatcher)
        return SimpleNamespace(request_context=SimpleNamespace(lifespan_context=state))

    async def test_chat_task_uses_saved_assignment_and_compact_context(self):
        dispatcher = FakeDispatcher()
        result = await execute_task(
            task="vision",
            operation="chat",
            ctx=self.make_context(dispatcher),
            messages=[{"role": "user", "content": "Describe this image."}],
            session_id="session-1",
            state_ref="state-1",
            memory_refs=["memory-1"],
            working_context="Current user is testing vision.",
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["provider"], "provider-a")
        self.assertEqual(result["model"], "model-a")
        context, payload = dispatcher.calls[0]
        self.assertEqual(context.task, "vision")
        self.assertEqual(context.behavior_revision, 3)
        self.assertEqual(context.session_id, "session-1")
        self.assertEqual(context.memory_refs, ("memory-1",))
        self.assertEqual(payload["messages"][0]["content"], "Describe this image.")

    async def test_transcription_decodes_base64_audio(self):
        dispatcher = FakeDispatcher()
        encoded = base64.b64encode(b"sample audio").decode()
        result = await execute_task(
            task="audio",
            operation="transcribe",
            ctx=self.make_context(dispatcher),
            filename="sample.webm",
            media_type="audio/webm",
            audio_base64=encoded,
        )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(dispatcher.calls[0][1]["audio_bytes"], b"sample audio")

    async def test_invalid_audio_base64_is_rejected_before_dispatch(self):
        dispatcher = FakeDispatcher()
        with self.assertRaisesRegex(ValueError, "valid base64"):
            await execute_task(
                task="audio",
                operation="transcribe",
                ctx=self.make_context(dispatcher),
                filename="sample.webm",
                media_type="audio/webm",
                audio_base64="not base64!",
            )
        self.assertEqual(dispatcher.calls, [])

    def voice_context(self, dispatcher):
        ctx = self.make_context(dispatcher)
        ctx.request_context.lifespan_context.storage = SimpleNamespace(mind=object())
        return ctx

    async def test_voice_uses_saved_task_and_returns_portable_audio_without_body(self):
        dispatcher = FakeDispatcher()
        dispatcher.execute = AsyncMock(return_value=b"MP3 audio")
        with patch("aicognitive_mind.mcp_server.VoiceSettings") as settings:
            settings.return_value.read = AsyncMock(
                return_value={
                    "rate": 1.2,
                    "volume": 0.5,
                    "voiceName": "local voice",
                }
            )
            result = await execute_task(
                task="audio_voice",
                operation="synthesize_voice",
                text=" Say this. ",
                ctx=self.voice_context(dispatcher),
            )
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["provider"], "provider-a")
        self.assertEqual(base64.b64decode(result["result"]["audio_base64"]), b"MP3 audio")
        context, payload = dispatcher.execute.await_args.args
        self.assertEqual(context.task, "audio_voice")
        self.assertEqual(
            payload,
            {"operation": "synthesize_voice", "text": "Say this.", "speed": 1.2, "volume": -10.0},
        )

    async def test_unconfigured_voice_does_not_handoff_to_reasoning_host(self):
        dispatcher = FakeDispatcher()
        dispatcher.assignment = AsyncMock(
            return_value=SimpleNamespace(
                provider="",
                model="",
                fallbacks=(),
            )
        )
        ctx = self.voice_context(dispatcher)
        host = SimpleNamespace(active=AsyncMock(), submit=AsyncMock())
        ctx.request_context.lifespan_context.hosts = host
        with patch("aicognitive_mind.mcp_server.VoiceSettings") as settings:
            settings.return_value.read = AsyncMock(
                return_value={
                    "rate": 1.0,
                    "volume": 1.0,
                    "voiceName": "",
                }
            )
            result = await execute_task(
                task="audio_voice", operation="synthesize_voice", text="Hello", ctx=ctx
            )
        self.assertEqual(result["status"], "not_configured")
        host.active.assert_not_awaited()
        host.submit.assert_not_awaited()
        self.assertEqual(dispatcher.calls, [])

    async def test_voice_provider_failure_is_not_an_unconfigured_result(self):
        dispatcher = FakeDispatcher()
        dispatcher.execute = AsyncMock(side_effect=TaskDispatchError("quota exhausted"))
        with patch("aicognitive_mind.mcp_server.VoiceSettings") as settings:
            settings.return_value.read = AsyncMock(return_value={"rate": 1.0, "volume": 1.0})
            result = await execute_task(
                task="audio_voice",
                operation="synthesize_voice",
                text="Hello",
                ctx=self.voice_context(dispatcher),
            )
        self.assertEqual(result["status"], "task_failed")
        self.assertEqual(result["error"], "quota exhausted")

    async def test_voice_validates_task_and_text_before_provider_access(self):
        dispatcher = FakeDispatcher()
        for task, text in [("audio", "hello"), ("audio_voice", " "), ("audio_voice", "a" * 20001)]:
            with self.subTest(task=task, length=len(text)), self.assertRaises(ValueError):
                await execute_task(
                    task=task,
                    operation="synthesize_voice",
                    text=text,
                    ctx=self.voice_context(dispatcher),
                )
        self.assertEqual(dispatcher.calls, [])

    async def test_voice_rejects_empty_or_non_audio_provider_result(self):
        for audio in [b"", "text is not generated audio"]:
            dispatcher = FakeDispatcher()
            dispatcher.execute = AsyncMock(return_value=audio)
            with (
                self.subTest(result_type=type(audio).__name__),
                patch("aicognitive_mind.mcp_server.VoiceSettings") as settings,
            ):
                settings.return_value.read = AsyncMock(return_value={"rate": 1.0, "volume": 1.0})
                with self.assertRaisesRegex(ValueError, "empty, invalid, or oversized"):
                    await execute_task(
                        task="audio_voice",
                        operation="synthesize_voice",
                        text="Hello",
                        ctx=self.voice_context(dispatcher),
                    )


if __name__ == "__main__":
    unittest.main()
