import base64
import unittest
from types import SimpleNamespace
from typing import Any

from aicognitive_mind.body import BrowserAudioIngress, BrowserVisionIngress
from aicognitive_mind.domain import CognitiveMind, MindIdentity, ReasoningRequest
from aicognitive_mind.embodiment import GeminiPerceptInterpreter
from aicognitive_mind.engines import GeminiReasoningEngine


class RecordingTool:
    name = "memory_steward"
    description = "Recall relevant memory."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "focus": {"type": "string"},
        },
        "required": ["action", "focus"],
        "additionalProperties": False,
    }

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append(arguments)
        return {"status": "recalled", "focus": arguments["focus"]}


class FakeGeminiModels:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def generate_content(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("No fake Gemini response remains")
        return self.responses.pop(0)


class FakeGeminiClient:
    def __init__(self, responses: list[Any]) -> None:
        self.models = FakeGeminiModels(responses)
        self.aio = SimpleNamespace(models=self.models)


def data_url(media_type: str, payload: bytes) -> str:
    encoded = base64.b64encode(payload).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


class GeminiProviderV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_reasoning_engine_runs_memory_tool_loop(self) -> None:
        tool = RecordingTool()
        first = SimpleNamespace(
            function_calls=[
                SimpleNamespace(
                    name="memory_steward",
                    args={"action": "recall", "focus": "birthday"},
                    id="call-1",
                )
            ],
            candidates=[
                SimpleNamespace(
                    content=SimpleNamespace(role="model", parts=[]),
                )
            ],
            text="",
        )
        second = SimpleNamespace(
            function_calls=[],
            candidates=[],
            text="I remember the relevant context.",
        )
        client = FakeGeminiClient([first, second])
        engine = GeminiReasoningEngine(
            "test-key",
            model="gemini-3.5-flash",
            client=client,
        )
        request = ReasoningRequest(
            mind=CognitiveMind(identity=MindIdentity(self_name="AICognitiveMind")),
            input_text="What do you remember?",
            system_prompt="Use memory before answering.",
        )

        proposal = await engine.propose(request, tools=(tool,))

        self.assertEqual(proposal.response_text, "I remember the relevant context.")
        self.assertEqual(
            tool.calls,
            [{"action": "recall", "focus": "birthday"}],
        )
        self.assertEqual(len(client.models.calls), 2)
        self.assertEqual(client.models.calls[0]["model"], "gemini-3.5-flash")
        self.assertEqual(
            proposal.diagnostic.implementation["name"],
            "gemini-generate-content",
        )
        self.assertEqual(proposal.diagnostic.implementation["tool_calls"], 1)

    async def test_visual_interpreter_sends_exact_image_bytes(self) -> None:
        response = SimpleNamespace(text="A desk and a window are visible.")
        client = FakeGeminiClient([response])
        interpreter = GeminiPerceptInterpreter(
            "test-key",
            model="gemini-3.5-flash",
            client=client,
        )
        eyes = BrowserVisionIngress()
        percept = eyes.accept(
            image_data_url=data_url("image/jpeg", b"jpeg"),
            width=100,
            height=100,
        )

        interpretation = await interpreter.interpret(percept)

        self.assertEqual(
            interpretation,
            "Visual perception: A desk and a window are visible.",
        )
        call = client.models.calls[0]
        self.assertEqual(call["model"], "gemini-3.5-flash")
        part = call["contents"][0]
        self.assertEqual(part.inline_data.mime_type, "image/jpeg")
        self.assertEqual(part.inline_data.data, b"jpeg")

    async def test_audio_interpreter_sends_exact_audio_bytes(self) -> None:
        response = SimpleNamespace(text="The speaker says hello.")
        client = FakeGeminiClient([response])
        interpreter = GeminiPerceptInterpreter(
            "test-key",
            model="gemini-3.5-flash",
            client=client,
        )
        ears = BrowserAudioIngress()
        percept = ears.accept(
            audio_data_url=data_url("audio/webm", b"audio"),
            duration_ms=800,
        )

        interpretation = await interpreter.interpret(percept)

        self.assertEqual(
            interpretation,
            "Auditory perception: The speaker says hello.",
        )
        call = client.models.calls[0]
        part = call["contents"][0]
        self.assertEqual(part.inline_data.mime_type, "audio/webm")
        self.assertEqual(part.inline_data.data, b"audio")


if __name__ == "__main__":
    unittest.main()
