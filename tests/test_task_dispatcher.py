import unittest
from types import SimpleNamespace

from aicognitive_mind.host_runtime import HostAwareInterpreter
from aicognitive_mind.provider_endpoints import ProviderEndpoint, ProviderEndpointRegistry
from aicognitive_mind.task_dispatcher import TaskDispatchError, TaskModelDispatcher
from aicognitive_mind.task_model_assignments import TaskModelAssignmentRegistry


class FakeRecords:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def create(self, key, value):
        self.values[key] = value

    async def replace(self, key, before, after):
        if self.values.get(key) != before:
            return False
        self.values[key] = after
        return True


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    @property
    def is_error(self):
        return self.status_code >= 400

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response


class TaskModelDispatcherTests(unittest.IsolatedAsyncioTestCase):
    async def configured(self, *, model="vision-arbitrary-model", provider="Local endpoint"):
        records = FakeRecords()
        await ProviderEndpointRegistry(records).replace([
            ProviderEndpoint(
                id="local",
                name="Local endpoint",
                base_url="http://localhost:8000/v1",
                api_key="admin-key",
                models=["model-from-discovery"],
            )
        ])
        assignments = await TaskModelAssignmentRegistry(records).list()
        assignments = [
            item.model_copy(update={"provider": provider, "model": model})
            if item.task == "vision" else item
            for item in assignments
        ]
        await TaskModelAssignmentRegistry(records).replace(assignments)
        return records

    async def test_chat_dispatch_uses_selected_arbitrary_model_and_endpoint(self):
        records = await self.configured()
        client = FakeClient(FakeResponse({
            "choices": [{"message": {"content": "A cat on a chair."}}]
        }))
        dispatcher = TaskModelDispatcher(records, client=client)

        result = await dispatcher.complete_chat(
            "vision",
            [{"role": "user", "content": [
                {"type": "text", "text": "Describe"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA=="}},
            ]}],
        )

        self.assertEqual(result, "A cat on a chair.")
        method, url, kwargs = client.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "http://localhost:8000/v1/chat/completions")
        self.assertEqual(kwargs["json"]["model"], "vision-arbitrary-model")
        self.assertEqual(kwargs["json"]["messages"][0]["role"], "system")
        self.assertIn("IMMUTABLE AXIOM TASK FOUNDATION", kwargs["json"]["messages"][0]["content"])
        self.assertIn("vision-arbitrary-model", kwargs["json"]["messages"][0]["content"])
        self.assertIn("image_url", str(kwargs["json"]["messages"]))
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer admin-key")

    async def test_transcription_uses_assigned_model(self):
        records = await self.configured(model="my-audio-model")
        assignments = await TaskModelAssignmentRegistry(records).list()
        assignments = [
            item.model_copy(update={"provider": "Local endpoint", "model": "my-audio-model"})
            if item.task == "audio" else item
            for item in assignments
        ]
        await TaskModelAssignmentRegistry(records).replace(assignments)
        client = FakeClient(FakeResponse({"text": "Hello there"}))
        dispatcher = TaskModelDispatcher(records, client=client)

        result = await dispatcher.transcribe(
            "audio", filename="clip.webm", audio_bytes=b"audio",
            media_type="audio/webm",
        )

        self.assertEqual(result, "Hello there")
        self.assertEqual(client.calls[0][1], "http://localhost:8000/v1/audio/transcriptions")
        self.assertEqual(client.calls[0][2]["data"]["model"], "my-audio-model")
        self.assertIn("IMMUTABLE AXIOM TASK FOUNDATION", client.calls[0][2]["data"]["prompt"])
        self.assertIn("my-audio-model", client.calls[0][2]["data"]["prompt"])

    async def test_provider_failure_is_reported_without_fallback(self):
        records = await self.configured()
        client = FakeClient(FakeResponse({"error": {"message": "unsupported modality"}}, 400, "unsupported modality"))
        dispatcher = TaskModelDispatcher(records, client=client)

        with self.assertRaisesRegex(TaskDispatchError, "HTTP 400"):
            await dispatcher.complete_chat("vision", [{"role": "user", "content": "test"}])

        self.assertEqual(len(client.calls), 1)

    async def test_host_aware_interpreter_uses_assigned_sensory_dispatcher(self):
        class ActiveHosts:
            async def active(self):
                return True

        class Fallback:
            records = FakeRecords()

        class SelectedDispatcher:
            async def interpret_percept(self, percept, *, focus=None):
                return "Visual perception: selected endpoint result"

        interpreter = HostAwareInterpreter(Fallback(), ActiveHosts())
        interpreter.task_dispatcher = SelectedDispatcher()
        percept = SimpleNamespace(
            modality=SimpleNamespace(value="vision"),
            content_ref="data:image/jpeg;base64,AA==",
        )

        result = await interpreter.interpret(percept)

        self.assertEqual(result, "Visual perception: selected endpoint result")

    async def test_unresolved_provider_is_reported(self):
        records = await self.configured(provider="not-configured")
        dispatcher = TaskModelDispatcher(records, client=FakeClient(FakeResponse({})))

        with self.assertRaisesRegex(TaskDispatchError, "not configured"):
            await dispatcher.complete_chat("vision", [{"role": "user", "content": "test"}])


if __name__ == "__main__":
    unittest.main()
