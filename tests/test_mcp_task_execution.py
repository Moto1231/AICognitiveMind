import base64
import unittest
from types import SimpleNamespace

from aicognitive_mind.mcp_server import execute_task
from aicognitive_mind.task_behaviors import default_task_behaviors


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


if __name__ == "__main__":
    unittest.main()
