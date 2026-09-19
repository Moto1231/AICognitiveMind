import unittest
from types import SimpleNamespace
from typing import Any

from aicognitive_mind.mcp_service import MemoryProposal
from aicognitive_mind.reference_host import (
    CognitiveMindHost,
    HostReasoningResult,
    OpenAIHostReasoner,
)


class FakeMcpResult:
    def __init__(self, structured_content: dict[str, Any]) -> None:
        self.is_error = False
        self.content = []
        self.structured_content = structured_content


class FakeMcpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> FakeMcpResult:
        self.calls.append((name, arguments))
        if name == "begin_interaction":
            return FakeMcpResult(
                {
                    "status": "ready_to_reason",
                    "mind": {"identity": {"self_name": "Genesis"}},
                    "recalled_context": {"summary": "Birthday memory recalled."},
                    "conscious_workspace_contract": "Recall before concluding.",
                }
            )
        if name == "complete_interaction":
            return FakeMcpResult(
                {
                    "status": "interaction_committed",
                    "memory_decisions": [{"accepted": True}],
                }
            )
        raise AssertionError(name)


class FakeReasoner:
    def __init__(self) -> None:
        self.begin_context: dict[str, Any] | None = None

    async def reason(
        self,
        user_message: str,
        begin_context: dict[str, Any],
    ) -> HostReasoningResult:
        self.begin_context = begin_context
        return HostReasoningResult(
            response_text="Your birthday is February 7.",
            proposed_memories=(
                MemoryProposal(
                    memory_class="semantic",
                    content="Will's birthday is February 7.",
                    associations=("Will", "birthday", "February 7"),
                    grounding=("Will directly stated his birthday.",),
                ),
            ),
        )


class FakeResponses:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.calls: list[dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self._response


class FakeOpenAIClient:
    def __init__(self, response: Any) -> None:
        self.responses = FakeResponses(response)


class ReferenceHostTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_enforces_begin_then_complete_around_external_reasoning(self) -> None:
        client = FakeMcpClient()
        reasoner = FakeReasoner()
        host = CognitiveMindHost(client=client, reasoner=reasoner)

        turn = await host.interact("When is my birthday?")

        self.assertEqual(turn.response_text, "Your birthday is February 7.")
        self.assertIsNotNone(reasoner.begin_context)
        self.assertEqual(
            [name for name, _arguments in client.calls],
            ["begin_interaction", "complete_interaction"],
        )
        complete_arguments = client.calls[1][1]
        self.assertEqual(
            complete_arguments["proposed_memories"][0]["content"],
            "Will's birthday is February 7.",
        )
        self.assertEqual(turn.memory_decisions, ({"accepted": True},))

    async def test_openai_reasoner_converts_finalize_tool_call_into_memory_proposal(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="finalize_turn",
                    arguments=(
                        '{"response_text":"Recorded.","proposed_memories":['
                        '{"memory_class":"semantic","content":"Will likes parks.",'
                        '"associations":["Will","parks"],'
                        '"grounding":["Will directly stated this preference."]}'
                        ']}'
                    ),
                )
            ],
            output_text="",
        )
        client = FakeOpenAIClient(response)
        reasoner = OpenAIHostReasoner(
            api_key="test-key",
            model="test-model",
            client=client,
        )

        result = await reasoner.reason(
            "I like parks.",
            {
                "mind": {"identity": {"self_name": "Genesis"}},
                "recalled_context": {"summary": ""},
                "conscious_workspace_contract": "Use memory responsibly.",
            },
        )

        self.assertEqual(result.response_text, "Recorded.")
        self.assertEqual(len(result.proposed_memories), 1)
        self.assertEqual(result.proposed_memories[0].content, "Will likes parks.")
        request = client.responses.calls[0]
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(request["tools"][0]["name"], "finalize_turn")
        self.assertIn("recalled_context", request["input"])

    async def test_openai_reasoner_falls_back_to_plain_response_without_memory(self) -> None:
        response = SimpleNamespace(
            output=[],
            output_text="No durable learning in this turn.",
        )
        reasoner = OpenAIHostReasoner(
            api_key="test-key",
            client=FakeOpenAIClient(response),
        )

        result = await reasoner.reason(
            "Say hello.",
            {
                "mind": {"identity": {"self_name": "Genesis"}},
                "recalled_context": {},
                "conscious_workspace_contract": "Use memory responsibly.",
            },
        )

        self.assertEqual(result.response_text, "No durable learning in this turn.")
        self.assertEqual(result.proposed_memories, ())


if __name__ == "__main__":
    unittest.main()
