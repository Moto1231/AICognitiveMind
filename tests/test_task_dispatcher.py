import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.host_runtime import HostAwareCore, HostAwareInterpreter
from aicognitive_mind.provider_endpoints import ProviderEndpoint, ProviderEndpointRegistry
from aicognitive_mind.task_dispatcher import TaskDispatchError, TaskModelDispatcher
from aicognitive_mind.task_model_assignments import TaskFallbackAssignment, TaskModelAssignmentRegistry


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


class SequencedFakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


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

    async def test_endpoint_selected_model_overrides_old_task_model_and_covers_fallback(self):
        records = await self.configured(model="obsolete-task-model")
        endpoint_registry = ProviderEndpointRegistry(records)
        endpoints = await endpoint_registry.list()
        await endpoint_registry.replace([
            endpoints[0].model_copy(update={"model": "selected-endpoint-model"}),
            ProviderEndpoint(id="backup", name="Backup", model="backup-bound-model",
                             base_url="https://backup.example/v1"),
        ])
        registry = TaskModelAssignmentRegistry(records)
        assignments = await registry.list()
        await registry.replace([
            item.model_copy(update={"fallbacks": [TaskFallbackAssignment(provider="backup")]})
            if item.task == "vision" else item for item in assignments
        ])
        client = SequencedFakeClient([
            FakeResponse({}, status_code=503, text="temporarily unavailable"),
            FakeResponse({"choices": [{"message": {"content": "Observed."}}]}),
        ])
        result = await TaskModelDispatcher(records, client=client).complete_chat(
            "vision", [{"role": "user", "content": "Describe."}],
        )
        self.assertEqual(result, "Observed.")
        self.assertEqual(client.calls[0][2]["json"]["model"], "selected-endpoint-model")
        self.assertEqual(client.calls[1][2]["json"]["model"], "backup-bound-model")

    async def test_body_reasoning_endpoint_uses_recall_and_commits_after_enabled_fallback(self):
        records = await self.configured()
        endpoints = ProviderEndpointRegistry(records)
        await endpoints.replace([item.model_copy(update={"model": "reasoning-bound-model"})
                                 for item in await endpoints.list()])
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace([
            item.model_copy(update={"provider": "local", "model": ""})
            if item.task == "reasoning" else item for item in await assignments.list()
        ])
        client = FakeClient(FakeResponse({"choices": [{"message": {"content": "A grounded reply."}}]}))
        dispatcher = TaskModelDispatcher(records, client=client)
        service = SimpleNamespace(
            begin_interaction=AsyncMock(return_value={
                "idempotency_key": "body-endpoint-test-key",
                "conscious_workspace_contract": "Axiom interaction contract.",
                "recalled_context": {"fact": "A remembered fact."},
            }),
            complete_interaction=AsyncMock(return_value={
                "status": "interaction_committed", "occurred_at": "2026-10-16T12:00:00Z",
            }),
        )
        hosts = SimpleNamespace(active=AsyncMock(return_value=None),
            message_events_enabled=AsyncMock(return_value=False), records=records, service=service)
        core = SimpleNamespace(interact=AsyncMock())
        with patch("aicognitive_mind.host_runtime.TaskModelDispatcher", return_value=dispatcher), patch(
            "aicognitive_mind.config.body_allow_standalone_fallback_enabled", return_value=True,
        ):
            result = await HostAwareCore(core, hosts).interact("Hello.")
        self.assertEqual(result.response_text, "A grounded reply.")
        self.assertIn("A remembered fact.", client.calls[0][2]["json"]["messages"][0]["content"])
        self.assertEqual(client.calls[0][2]["json"]["model"], "reasoning-bound-model")
        service.complete_interaction.assert_awaited_once_with(
            "Hello.", "A grounded reply.", idempotency_key="body-endpoint-test-key",
            source="human", input_context=None, runtime_source="configured_reasoning_endpoint",
        )
        core.interact.assert_not_awaited()

    async def test_body_keeps_live_reasoning_host_priority_over_endpoint(self):
        hosts = SimpleNamespace(
            active=AsyncMock(return_value={"name": "Codex", "model": "host-model"}),
            submit=AsyncMock(return_value={"response_text": "Host reply.", "occurred_at": "2026-10-16T12:00:00Z"}),
        )
        core = SimpleNamespace(interact=AsyncMock())
        result = await HostAwareCore(core, hosts).interact("Hello.")
        self.assertEqual(result.response_text, "Host reply.")
        hosts.submit.assert_awaited_once_with("Hello.")
        core.interact.assert_not_awaited()

    async def test_body_configured_endpoint_does_not_bypass_fallback_disabled(self):
        hosts = SimpleNamespace(active=AsyncMock(return_value=None))
        core = SimpleNamespace(interact=AsyncMock())
        with patch("aicognitive_mind.config.body_allow_standalone_fallback_enabled", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "fallback is disabled"):
                await HostAwareCore(core, hosts).interact("Hello.")
        core.interact.assert_not_awaited()

    async def test_runtime_contract_dispatches_compact_context_to_stateless_adapter(self):
        records = await self.configured()
        client = FakeClient(FakeResponse({
            "choices": [{"message": {"content": "Observed."}}]
        }))
        dispatcher = TaskModelDispatcher(records, client=client)
        from aicognitive_mind.task_behaviors import TaskExecutionContext

        result = await dispatcher.execute(
            TaskExecutionContext(
                task="vision",
                session_id="session-compact",
                state_ref="state-compact",
                memory_refs=("memory-7",),
            ),
            {"operation": "chat", "messages": [{"role": "user", "content": "Describe."}]},
        )

        self.assertEqual(result, "Observed.")
        prompt = client.calls[0][2]["json"]["messages"][0]["content"]
        self.assertIn("Session reference: session-compact", prompt)
        self.assertIn("Working-state reference: state-compact", prompt)
        self.assertIn("memory-7", prompt)


    async def test_v3_endpoint_with_transcription_operation_suffix_is_normalized(self):
        endpoint = ProviderEndpoint(
            id="eden",
            name="Eden Text-to-speech",
            base_url="https://api.edenai.run/v3/audio/transcriptions",
            api_key="test-key",
        )

        self.assertEqual(
            TaskModelDispatcher._url(endpoint, "audio/transcriptions"),
            "https://api.edenai.run/v3/audio/transcriptions",
        )

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

    async def test_v3_provider_base_url_does_not_duplicate_v1_prefix(self):
        records = await self.configured(model="eden-audio-model")
        endpoints = await ProviderEndpointRegistry(records).list()
        await ProviderEndpointRegistry(records).replace([
            endpoints[0].model_copy(update={"base_url": "https://api.edenai.run/v3"})
        ])
        assignments = await TaskModelAssignmentRegistry(records).list()
        await TaskModelAssignmentRegistry(records).replace([
            item.model_copy(update={"provider": "Local endpoint", "model": "eden-audio-model"})
            if item.task == "audio" else item
            for item in assignments
        ])
        client = FakeClient(FakeResponse({"text": "Recognized speech"}))
        dispatcher = TaskModelDispatcher(records, client=client)

        result = await dispatcher.transcribe(
            "audio", filename="clip.webm", audio_bytes=b"audio",
            media_type="audio/webm",
        )

        self.assertEqual(result, "Recognized speech")
        self.assertEqual(
            client.calls[0][1],
            "https://api.edenai.run/v3/audio/transcriptions",
        )

    async def test_provider_failure_is_reported_without_fallback(self):
        records = await self.configured()
        client = FakeClient(FakeResponse({"error": {"message": "unsupported modality"}}, 400, "unsupported modality"))
        dispatcher = TaskModelDispatcher(records, client=client)

        with self.assertLogs("aicognitive_mind.task_dispatcher", level="ERROR") as captured:
            with self.assertRaisesRegex(TaskDispatchError, "HTTP 400"):
                await dispatcher.complete_chat("vision", [{"role": "user", "content": "test"}])

        self.assertEqual(len(client.calls), 1)
        self.assertIn("task_provider_http_error", captured.output[0])
        self.assertIn("status=400", captured.output[0])

    async def test_chat_retries_configured_task_fallback_after_primary_failure(self):
        records = await self.configured(model="primary-model")
        assignments = await TaskModelAssignmentRegistry(records).list()
        await TaskModelAssignmentRegistry(records).replace([
            item.model_copy(update={
                "fallbacks": [
                    TaskFallbackAssignment(provider="Local endpoint", model="backup-model"),
                    TaskFallbackAssignment(provider="Local endpoint", model="last-resort-model"),
                ],
            }) if item.task == "vision" else item
            for item in assignments
        ])
        client = SequencedFakeClient([
            FakeResponse({"error": {"message": "primary unavailable"}}, 503, "primary unavailable"),
            FakeResponse({"error": {"message": "first fallback unavailable"}}, 503, "first fallback unavailable"),
            FakeResponse({"choices": [{"message": {"content": "Fallback result"}}]}),
        ])
        dispatcher = TaskModelDispatcher(records, client=client)

        with self.assertLogs("aicognitive_mind.task_dispatcher", level="WARNING"):
            result = await dispatcher.complete_chat(
                "vision", [{"role": "user", "content": "Describe"}]
            )

        self.assertEqual(result, "Fallback result")
        self.assertEqual(len(client.calls), 3)
        self.assertEqual(client.calls[0][2]["json"]["model"], "primary-model")
        self.assertEqual(client.calls[1][2]["json"]["model"], "backup-model")
        self.assertEqual(client.calls[2][2]["json"]["model"], "last-resort-model")

    async def test_transcription_retries_configured_task_fallback_after_primary_failure(self):
        records = await self.configured(model="primary-audio")
        assignments = await TaskModelAssignmentRegistry(records).list()
        await TaskModelAssignmentRegistry(records).replace([
            item.model_copy(update={
                "provider": "Local endpoint",
                "model": "primary-audio",
                "fallbacks": [TaskFallbackAssignment(provider="Local endpoint", model="backup-audio")],
            }) if item.task == "audio" else item
            for item in assignments
        ])
        client = SequencedFakeClient([
            FakeResponse({"error": {"message": "primary unavailable"}}, 503, "primary unavailable"),
            FakeResponse({"text": "Fallback transcription"}),
        ])
        dispatcher = TaskModelDispatcher(records, client=client)

        with self.assertLogs("aicognitive_mind.task_dispatcher", level="WARNING"):
            result = await dispatcher.transcribe(
                "audio", filename="clip.webm", audio_bytes=b"audio",
                media_type="audio/webm",
            )

        self.assertEqual(result, "Fallback transcription")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(client.calls[0][2]["data"]["model"], "primary-audio")
        self.assertEqual(client.calls[1][2]["data"]["model"], "backup-audio")

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



    async def test_failed_task_providers_defer_to_connected_reasoning(self):
        class ActiveHosts:
            async def active(self):
                return {"name": "ChatGPT", "model": "GPT-6"}

            async def submit(self, message, *, priority=0):
                self.message = message
                self.priority = priority
                return {"response_text": "The audio contains a short spoken phrase."}

        class Fallback:
            records = FakeRecords()

        class FailedDispatcher:
            async def interpret_percept(self, percept, *, focus=None):
                raise TaskDispatchError("both configured providers failed")

        hosts = ActiveHosts()
        interpreter = HostAwareInterpreter(Fallback(), hosts)
        interpreter.task_dispatcher = FailedDispatcher()
        percept = SimpleNamespace(
            modality=SimpleNamespace(value="audio"),
            observed_at="2026-10-12T12:00:00Z",
            source="test microphone",
            summary="incoming audio",
            metadata={"evidence_ref": "evidence-audio-1"},
            content_ref="data:audio/webm;base64,YXVkaW8=",
            model_dump=lambda mode="json": {
                "modality": "audio",
                "observed_at": "2026-10-12T12:00:00Z",
                "source": "test microphone",
                "summary": "incoming audio",
                "metadata": {"evidence_ref": "evidence-audio-1"},
                "content_ref": "data:audio/webm;base64,YXVkaW8=",
            },
        )

        with self.assertLogs("aicognitive_mind.auth_diagnostics", level="WARNING"):
            result = await interpreter.interpret(percept)

        self.assertEqual(result, "The audio contains a short spoken phrase.")
        self.assertIn("Interpret this audio percept", hosts.message)
        self.assertIn("evidence-audio-1", hosts.message)

    async def test_failed_task_providers_defer_to_body_reasoning_fallback(self):
        class InactiveHosts:
            async def active(self):
                return None

        class Fallback:
            records = FakeRecords()

        class FailedDispatcher:
            async def interpret_percept(self, percept, *, focus=None):
                raise TaskDispatchError("both configured providers failed")

        interpreter = HostAwareInterpreter(Fallback(), InactiveHosts())
        interpreter.task_dispatcher = FailedDispatcher()
        percept = SimpleNamespace(
            modality=SimpleNamespace(value="audio"),
            content_ref="data:audio/webm;base64,YXVkaW8=",
        )

        from unittest.mock import patch
        with patch("aicognitive_mind.config.get_settings") as settings:
            settings.return_value.body_allow_standalone_fallback = True
            with self.assertLogs("aicognitive_mind.auth_diagnostics", level="WARNING"):
                result = await interpreter.interpret(percept)

        self.assertIn("task primary and fallback failed", result)

    async def test_unconfigured_audio_without_host_reports_task_routing_problem(self):
        class InactiveHosts:
            async def active(self):
                return None

        class Fallback:
            records = FakeRecords()

        interpreter = HostAwareInterpreter(Fallback(), InactiveHosts())
        percept = SimpleNamespace(
            modality=SimpleNamespace(value="audio"),
            content_ref="data:audio/webm;base64,YXVkaW8=",
        )

        with self.assertRaisesRegex(
            RuntimeError,
            "Audio & Transcription task has no configured provider/model assignment",
        ):
            await interpreter.interpret(percept)

    async def test_runtime_contract_dispatches_voice_synthesis(self):
        from unittest.mock import AsyncMock
        from aicognitive_mind.task_behaviors import TaskExecutionContext

        records = await self.configured()
        dispatcher = TaskModelDispatcher(records, client=FakeClient(FakeResponse({})))
        dispatcher.synthesize_voice = AsyncMock(return_value=b"speech-audio")

        result = await dispatcher.execute(
            TaskExecutionContext(task="audio_voice"),
            {"operation": "synthesize_voice", "text": "Hello there", "speed": 1.2, "volume": -4.0},
        )

        self.assertEqual(result, b"speech-audio")
        dispatcher.synthesize_voice.assert_awaited_once_with(
            "Hello there", speed=1.2, volume=-4.0
        )

    async def test_runtime_contract_rejects_voice_synthesis_on_other_task(self):
        from aicognitive_mind.task_behaviors import TaskExecutionContext

        records = await self.configured()
        dispatcher = TaskModelDispatcher(records, client=FakeClient(FakeResponse({})))

        with self.assertRaisesRegex(TaskDispatchError, "requires the audio_voice task"):
            await dispatcher.execute(
                TaskExecutionContext(task="audio"),
                {"operation": "synthesize_voice", "text": "Hello there"},
            )

if __name__ == "__main__":
    unittest.main()
