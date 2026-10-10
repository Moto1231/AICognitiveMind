import unittest
from types import SimpleNamespace
from typing import Any

from aicognitive_mind.host_context import HostWorkingContext
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
                    "idempotency_key": "turn-key",
                    "mind": {"identity": {"self_name": "Genesis"}},
                    "recalled_context": {"summary": "Birthday memory recalled."},
                    "conscious_workspace_contract": "Recall before concluding.",
                    "host_working_context": arguments["host_working_context"],
                }
            )
        if name == "complete_interaction":
            return FakeMcpResult(
                {
                    "status": "interaction_committed",
                    "memory_decisions": [{"accepted": True}],
                    "host_working_context": arguments["host_working_context"],
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
            working_context=HostWorkingContext(
                summary="Discussing Will's birthday.",
                participants=({
                    "participant_id": "user",
                    "name": "Will",
                    "identity_status": "confirmed",
                    "presence_status": "reported",
                    "grounding": ("The user identified themself as Will.",),
                }, {
                    "participant_id": "person-2",
                    "name": None,
                    "identity_status": "unresolved",
                    "presence_status": "referenced",
                    "grounding": (),
                },),
                active_speaker="user",
                addressee="person-2",
                unresolved_references=("he",),
            ),
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
        self.assertEqual(complete_arguments["idempotency_key"], "turn-key")
        self.assertEqual(
            complete_arguments["host_working_context"]["summary"],
            "Discussing Will's birthday.",
        )
        inventory = reasoner.begin_context["current_situation_inventory"]
        self.assertEqual(
            inventory["current_turn"],
            {"content": "When is my birthday?", "source": "human_input"},
        )
        self.assertIn("camera", inventory["unavailable_sensors"])
        self.assertIn("working_directory", inventory["host_runtime"])
        self.assertEqual(turn.memory_decisions, ({"accepted": True},))

    async def test_host_passes_its_updated_context_into_the_next_turn(self) -> None:
        client = FakeMcpClient()
        host = CognitiveMindHost(client=client, reasoner=FakeReasoner())

        await host.interact("We are discussing Will.")
        await host.interact("When is his birthday?")

        second_begin = client.calls[2][1]
        self.assertEqual(
            second_begin["host_working_context"]["summary"],
            "Discussing Will's birthday.",
        )
        self.assertEqual(
            second_begin["host_working_context"]["active_speaker"], "user"
        )
        self.assertEqual(second_begin["host_working_context"]["addressee"], "person-2")
        self.assertEqual(
            second_begin["host_working_context"]["unresolved_references"], ["he"]
        )
        self.assertEqual(
            second_begin["host_working_context"]["participants"][1]["identity_status"],
            "unresolved",
        )

    async def test_a_new_host_session_does_not_inherit_another_context(self) -> None:
        first_client = FakeMcpClient()
        first_host = CognitiveMindHost(client=first_client, reasoner=FakeReasoner())
        await first_host.interact("We are discussing Will.")

        second_client = FakeMcpClient()
        second_reasoner = FakeReasoner()
        second_host = CognitiveMindHost(client=second_client, reasoner=second_reasoner)
        await second_host.interact("Who is speaking?")

        initial_context = second_client.calls[0][1]["host_working_context"]
        self.assertEqual(initial_context["summary"], "")
        self.assertEqual(initial_context["participants"], [])

    async def test_openai_reasoner_converts_finalize_tool_call_into_memory_proposal(self) -> None:
        response = SimpleNamespace(
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="finalize_turn",
                    arguments=(
                        '{"response_text":"Recorded.","working_context":'
                        '{"summary":"Parks are the current topic.","participants":[],'
                        '"active_speaker":null,"addressee":null,"unresolved_references":[]},'
                        '"proposed_memories":['
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
        self.assertIn("First orient from current_situation_inventory", request["instructions"])

    async def test_openai_reasoner_requires_a_structured_context_update(self) -> None:
        response = SimpleNamespace(
            output=[],
            output_text="No durable learning in this turn.",
        )
        reasoner = OpenAIHostReasoner(
            api_key="test-key",
            client=FakeOpenAIClient(response),
        )

        with self.assertRaisesRegex(RuntimeError, "required finalize_turn context"):
            await reasoner.reason(
                "Say hello.",
                {
                    "mind": {"identity": {"self_name": "Genesis"}},
                    "recalled_context": {},
                    "conscious_workspace_contract": "Use memory responsibly.",
                },
            )


if __name__ == "__main__":
    unittest.main()
