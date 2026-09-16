import json
from typing import Any, Protocol

import httpx
from openai import AsyncOpenAI

from aicognitive_mind.domain import (
    DiagnosticObservation,
    ReasoningProposal,
    ReasoningRequest,
)
from aicognitive_mind.tooling import ReasoningTool


class ReasoningEngine(Protocol):
    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal: ...


class EchoReasoningEngine:
    """Deterministic implementation used without making it part of the mind."""

    def __init__(self, diagnostic_name: str = "echo-a", prefix: str = "I heard") -> None:
        self._diagnostic_name = diagnostic_name
        self._prefix = prefix

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        for tool in tools:
            if tool.name == "memory_steward":
                await tool.invoke({"action": "recall", "focus": request.input_text})

        response = f"{self._prefix}: {request.input_text}"
        return ReasoningProposal(
            response_text=response,
            diagnostic=DiagnosticObservation(
                component="reasoning_engine",
                operation="propose_response",
                implementation={
                    "name": self._diagnostic_name,
                    "model": "deterministic-echo",
                    "proposal": response,
                    "tools_exposed": [tool.name for tool in tools],
                },
            ),
        )


class OpenAIReasoningEngine:
    """OpenAI-backed reasoning process; identity and memory remain outside the model."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-terra",
        max_tool_rounds: int = 8,
        base_url: str | None = None,
        supports_previous_response_id: bool = True,
        diagnostic_name: str = "openai-responses",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._max_tool_rounds = max_tool_rounds
        self._supports_previous_response_id = supports_previous_response_id
        self._diagnostic_name = diagnostic_name

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        tools_by_name = {tool.name: tool for tool in tools}
        api_tools = [
            {
                "type": "function",
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.input_schema,
                "strict": False,
            }
            for tool in tools
        ]

        response = await self._client.responses.create(
            model=self._model,
            instructions=request.system_prompt,
            input=request.input_text,
            tools=api_tools,
        )
        tool_calls = 0

        for _ in range(self._max_tool_rounds):
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                response_text = response.output_text.strip()
                if not response_text:
                    output_details = [
                        item.model_dump(exclude_none=True) for item in response.output
                    ]
                    raise RuntimeError(
                        "Reasoning engine returned no response text; "
                        f"status={response.status!r}, output={output_details!r}"
                    )
                return ReasoningProposal(
                    response_text=response_text,
                    diagnostic=DiagnosticObservation(
                        component="reasoning_engine",
                        operation="propose_response",
                        implementation={
                            "name": self._diagnostic_name,
                            "model": self._model,
                            "response_id": response.id,
                            "tool_calls": tool_calls,
                            "tools_exposed": [tool.name for tool in tools],
                        },
                    ),
                )

            outputs: list[dict[str, Any]] = []
            for call in calls:
                tool = tools_by_name.get(call.name)
                if tool is None:
                    raise RuntimeError(f"Reasoning engine requested unknown tool: {call.name}")
                arguments = json.loads(call.arguments)
                result = await tool.invoke(arguments)
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result),
                    }
                )
                tool_calls += 1

            if self._supports_previous_response_id:
                response = await self._client.responses.create(
                    model=self._model,
                    instructions=request.system_prompt,
                    previous_response_id=response.id,
                    input=outputs,
                    tools=api_tools,
                )
            else:
                prior_output = [
                    item.model_dump(exclude_none=True) for item in response.output
                ]
                response = await self._client.responses.create(
                    model=self._model,
                    instructions=request.system_prompt,
                    input=[*prior_output, *outputs],
                    tools=api_tools,
                )

        raise RuntimeError("Reasoning engine exceeded the maximum number of tool rounds")


class OllamaReasoningEngine:
    """Local Ollama reasoning process using Ollama's native tool-calling API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "qwen3:1.7b",
        max_tool_rounds: int = 8,
    ) -> None:
        self._chat_url = f"{base_url.removesuffix('/v1').rstrip('/')}/api/chat"
        self._model = model
        self._max_tool_rounds = max_tool_rounds

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        tools_by_name = {tool.name: tool for tool in tools}
        api_tools = [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
            }
            for tool in tools
        ]
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": request.system_prompt},
            {"role": "user", "content": request.input_text},
        ]
        tool_calls = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            for _ in range(self._max_tool_rounds):
                api_response = await client.post(
                    self._chat_url,
                    json={
                        "model": self._model,
                        "messages": messages,
                        "tools": api_tools,
                        "think": False,
                        "stream": False,
                    },
                )
                api_response.raise_for_status()
                response_data = api_response.json()
                message = response_data.get("message", {})
                calls = message.get("tool_calls") or []

                if not calls:
                    response_text = str(message.get("content") or "").strip()
                    if not response_text:
                        raise RuntimeError(
                            "Ollama returned neither tool calls nor response text; "
                            f"message={message!r}"
                        )
                    return ReasoningProposal(
                        response_text=response_text,
                        diagnostic=DiagnosticObservation(
                            component="reasoning_engine",
                            operation="propose_response",
                            implementation={
                                "name": "ollama-native-chat",
                                "model": self._model,
                                "tool_calls": tool_calls,
                                "tools_exposed": [tool.name for tool in tools],
                            },
                        ),
                    )

                messages.append(message)
                for call in calls:
                    function = call.get("function", {})
                    name = function.get("name")
                    tool = tools_by_name.get(name)
                    if tool is None:
                        raise RuntimeError(
                            f"Reasoning engine requested unknown tool: {name}"
                        )
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    result = await tool.invoke(arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_name": name,
                            "content": json.dumps(result),
                        }
                    )
                    tool_calls += 1

        raise RuntimeError("Reasoning engine exceeded the maximum number of tool rounds")
