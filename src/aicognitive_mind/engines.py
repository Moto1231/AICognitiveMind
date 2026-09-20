import json
from typing import Any, Protocol

import httpx
from google import genai
from google.genai import types as genai_types
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


GEMINI_FLASH_PREFERENCE = (
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
)


async def resolve_gemini_model(
    api_key: str,
    requested_model: str | None = None,
    *,
    client: Any | None = None,
) -> str:
    """Resolve a usable Flash model from the models visible to this Gemini project."""

    active_client = client or genai.Client(api_key=api_key)
    pager = await active_client.aio.models.list(config={"page_size": 100})

    available: dict[str, Any] = {}
    async for model in pager:
        raw_name = str(getattr(model, "name", "") or "")
        name = raw_name.removeprefix("models/")
        if not name:
            continue

        actions = {
            str(action).lower()
            for action in (getattr(model, "supported_actions", None) or [])
        }
        if actions and "generatecontent" not in actions:
            continue
        available[name] = model

    if requested_model and requested_model.lower() != "auto":
        requested = requested_model.removeprefix("models/")
        if requested in available:
            return requested

    for candidate in GEMINI_FLASH_PREFERENCE:
        if candidate in available:
            return candidate

    fallback = sorted(
        name
        for name in available
        if name.startswith("gemini-")
        and "flash" in name
        and all(
            excluded not in name
            for excluded in ("image", "live", "tts", "transcribe", "native-audio")
        )
    )
    if fallback:
        return fallback[-1]

    visible = ", ".join(sorted(available)[:12]) or "none"
    raise RuntimeError(
        "This Gemini API key/project exposes no general-purpose Flash model "
        f"that supports generateContent. Visible models: {visible}"
    )


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
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key)
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
                    raise RuntimeError("Reasoning engine returned no response text")
                return ReasoningProposal(
                    response_text=response_text,
                    diagnostic=DiagnosticObservation(
                        component="reasoning_engine",
                        operation="propose_response",
                        implementation={
                            "name": "openai-responses",
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

            response = await self._client.responses.create(
                model=self._model,
                instructions=request.system_prompt,
                previous_response_id=response.id,
                input=outputs,
                tools=api_tools,
            )

        raise RuntimeError("Reasoning engine exceeded the maximum number of tool rounds")


class GeminiReasoningEngine:
    """Gemini-backed reasoning process; identity and memory remain outside the model."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-3.5-flash",
        max_tool_rounds: int = 8,
        client: Any | None = None,
    ) -> None:
        self._client = client or genai.Client(api_key=api_key)
        self._model = model
        self._max_tool_rounds = max_tool_rounds

    async def propose(
        self,
        request: ReasoningRequest,
        tools: tuple[ReasoningTool, ...] = (),
    ) -> ReasoningProposal:
        tools_by_name = {tool.name: tool for tool in tools}
        declarations = [
            genai_types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters_json_schema=tool.input_schema,
            )
            for tool in tools
        ]
        configured_tools = (
            [genai_types.Tool(function_declarations=declarations)]
            if declarations
            else None
        )
        config = genai_types.GenerateContentConfig(
            system_instruction=request.system_prompt,
            tools=configured_tools,
            automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        contents: list[Any] = [
            genai_types.Content(
                role="user",
                parts=[genai_types.Part.from_text(text=request.input_text)],
            )
        ]
        tool_calls = 0

        for _ in range(self._max_tool_rounds):
            response = await self._client.aio.models.generate_content(
                model=self._model,
                contents=contents,
                config=config,
            )
            calls = list(response.function_calls or [])
            if not calls:
                response_text = (response.text or "").strip()
                if not response_text:
                    raise RuntimeError("Gemini reasoning engine returned no response text")
                return ReasoningProposal(
                    response_text=response_text,
                    diagnostic=DiagnosticObservation(
                        component="reasoning_engine",
                        operation="propose_response",
                        implementation={
                            "name": "gemini-generate-content",
                            "model": self._model,
                            "tool_calls": tool_calls,
                            "tools_exposed": [tool.name for tool in tools],
                        },
                    ),
                )

            candidates = response.candidates or []
            if not candidates or candidates[0].content is None:
                raise RuntimeError(
                    "Gemini reasoning engine returned function calls without model content"
                )
            contents.append(candidates[0].content)

            result_parts = []
            for call in calls:
                name = call.name or ""
                tool = tools_by_name.get(name)
                if tool is None:
                    raise RuntimeError(
                        f"Gemini reasoning engine requested unknown tool: {name}"
                    )
                arguments = dict(call.args or {})
                result = await tool.invoke(arguments)
                result_parts.append(
                    genai_types.Part.from_function_response(
                        name=name,
                        response={"result": result},
                    )
                )
                tool_calls += 1

            contents.append(genai_types.Content(role="user", parts=result_parts))

        raise RuntimeError("Gemini reasoning engine exceeded the maximum number of tool rounds")


class OllamaReasoningEngine:
    """Local Ollama reasoning process using Ollama's native tool-calling API."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434/v1",
        model: str = "llama3.2:3b",
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

        async with httpx.AsyncClient(timeout=600.0) as client:
            for _ in range(self._max_tool_rounds):
                api_response = await client.post(
                    self._chat_url,
                    json={
                        "model": self._model,
                        "messages": messages,
                        "tools": api_tools,
                        "options": {"num_ctx": 4096},
                        "stream": False,
                    },
                )
                if api_response.is_error:
                    raise RuntimeError(
                        "Ollama chat request failed: "
                        f"status={api_response.status_code}, body={api_response.text}"
                    )
                response_data = api_response.json()
                message = response_data.get("message", {})
                calls = message.get("tool_calls") or []

                if not calls:
                    response_text = (message.get("content") or "").strip()
                    if not response_text:
                        raise RuntimeError(
                            "Ollama returned neither tool calls nor response text"
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
                    arguments = function.get("arguments") or {}
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    result = await tool.invoke(arguments)
                    messages.append(
                        {
                            "role": "tool",
                            "content": json.dumps(result),
                        }
                    )
                    tool_calls += 1

        raise RuntimeError("Reasoning engine exceeded the maximum number of tool rounds")
