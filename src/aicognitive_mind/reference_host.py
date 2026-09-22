from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Protocol

from mcp import Client, StdioServerParameters
from openai import AsyncOpenAI

from aicognitive_mind.mcp_service import MemoryProposal


def _structured(result: Any, tool_name: str) -> dict[str, Any]:
    if result.is_error:
        text = " | ".join(
            item.text for item in result.content if hasattr(item, "text")
        )
        raise RuntimeError(f"{tool_name} failed: {text}")
    if result.structured_content is None:
        raise RuntimeError(f"{tool_name} returned no structured content")
    return result.structured_content


@dataclass(frozen=True)
class HostReasoningResult:
    response_text: str
    proposed_memories: tuple[MemoryProposal, ...] = ()


@dataclass(frozen=True)
class HostTurn:
    response_text: str
    memory_decisions: tuple[dict[str, Any], ...]


class HostReasoner(Protocol):
    async def reason(
        self,
        user_message: str,
        begin_context: dict[str, Any],
    ) -> HostReasoningResult: ...


class OpenAIHostReasoner:
    """Replaceable OpenAI reasoning host that does not own Mind state."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-5.6-terra",
        client: Any | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._model = model

    async def reason(
        self,
        user_message: str,
        begin_context: dict[str, Any],
    ) -> HostReasoningResult:
        contract = str(begin_context.get("conscious_workspace_contract", "")).strip()
        recalled_context = begin_context.get("recalled_context", {})
        mind = begin_context.get("mind", {})

        instructions = (
            f"{contract}\n\n"
            "HOST BOUNDARY:\n"
            "The MCP host already completed begin_interaction for this turn. "
            "Reason using the supplied Mind identity and recalled context. "
            "Do not claim that the reasoning model owns identity or durable memory. "
            "When the answer is ready, call finalize_turn with the human-facing response "
            "and only stable learning that deserves durable-memory review. "
            "Do not propose identity changes. If nothing should persist, use an empty "
            "proposed_memories array."
        )

        finalize_tool = {
            "type": "function",
            "name": "finalize_turn",
            "description": (
                "Return the final human-facing response and stable memory proposals. "
                "The host will submit these proposals to the independent Memory Steward."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "response_text": {
                        "type": "string",
                        "minLength": 1,
                    },
                    "proposed_memories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "memory_class": {
                                    "type": "string",
                                    "enum": [
                                        "episodic",
                                        "semantic",
                                        "procedural",
                                        "reflective",
                                    ],
                                },
                                "content": {
                                    "type": "string",
                                    "minLength": 1,
                                },
                                "associations": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "grounding": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "memory_class",
                                "content",
                                "associations",
                                "grounding",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["response_text", "proposed_memories"],
                "additionalProperties": False,
            },
            "strict": True,
        }

        response = await self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=json.dumps(
                {
                    "human_message": user_message,
                    "mind": mind,
                    "recalled_context": recalled_context,
                },
                default=str,
            ),
            tools=[finalize_tool],
        )

        for item in response.output:
            if (
                getattr(item, "type", None) == "function_call"
                and getattr(item, "name", None) == "finalize_turn"
            ):
                arguments = json.loads(item.arguments)
                response_text = str(arguments.get("response_text", "")).strip()
                if not response_text:
                    raise RuntimeError("finalize_turn returned no response text")
                memories = tuple(
                    MemoryProposal.model_validate(memory)
                    for memory in arguments.get("proposed_memories", [])
                )
                return HostReasoningResult(
                    response_text=response_text,
                    proposed_memories=memories,
                )

        response_text = response.output_text.strip()
        if not response_text:
            raise RuntimeError(
                "Reasoning host returned neither finalize_turn nor response text"
            )
        return HostReasoningResult(response_text=response_text)


class CognitiveMindHost:
    """Host orchestration: begin through MCP, reason externally, complete through MCP."""

    def __init__(self, client: Any, reasoner: HostReasoner) -> None:
        self._client = client
        self._reasoner = reasoner

    async def interact(self, user_message: str) -> HostTurn:
        begun = _structured(
            await self._client.call_tool(
                "begin_interaction",
                {"user_message": user_message},
            ),
            "begin_interaction",
        )
        if begun.get("status") != "ready_to_reason":
            raise RuntimeError(f"Mind is not ready to reason: {begun}")

        reasoning = await self._reasoner.reason(user_message, begun)

        completed = _structured(
            await self._client.call_tool(
                "complete_interaction",
                {
                    "user_message": user_message,
                    "response_text": reasoning.response_text,
                    "idempotency_key": begun.get("idempotency_key"),
                    "proposed_memories": [
                        memory.model_dump(mode="json")
                        for memory in reasoning.proposed_memories
                    ],
                },
            ),
            "complete_interaction",
        )
        if completed.get("status") != "interaction_committed":
            raise RuntimeError(f"Mind did not commit interaction: {completed}")

        return HostTurn(
            response_text=reasoning.response_text,
            memory_decisions=tuple(completed.get("memory_decisions", [])),
        )


def _server_environment(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["STORAGE_PROVIDER"] = "mongo"
    env["MONGODB_URI"] = args.mongodb_uri
    env["MONGODB_DATABASE"] = args.mongodb_database
    env["APP_NAME"] = "AI Cognitive Mind"
    return env


async def _run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for the reference reasoning host")

    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "aicognitive_mind.mcp_server", "--transport", "stdio"],
        env=_server_environment(args),
    )

    async with Client(params) as client:
        status = await client.call_tool("mind_status", {})
        if status.is_error:
            raise RuntimeError(
                "The canonical Mind is not initialized at this MongoDB target. "
                "Point MONGODB_URI/MONGODB_DATABASE at the existing Mind before chatting."
            )

        reasoner = OpenAIHostReasoner(api_key=api_key, model=args.model)
        host = CognitiveMindHost(client=client, reasoner=reasoner)

        if args.message:
            turn = await host.interact(args.message)
            print(turn.response_text)
            return

        print("Connected to the persistent Cognitive Mind. Type /exit to leave.")
        while True:
            try:
                message = input("\nYou> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not message:
                continue
            if message.lower() in {"/exit", "/quit"}:
                break
            turn = await host.interact(message)
            print(f"\nMind> {turn.response_text}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reference MCP reasoning host for the persistent Cognitive Mind"
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("OPENAI_MODEL", "gpt-5.6-terra"),
        help="Replaceable OpenAI reasoning model used by this host process.",
    )
    parser.add_argument(
        "--mongodb-uri",
        default=os.environ.get("MONGODB_URI", "mongodb://127.0.0.1:27017"),
        help="MongoDB URI containing the canonical persistent Mind.",
    )
    parser.add_argument(
        "--mongodb-database",
        default=os.environ.get("MONGODB_DATABASE", "ai_cognitive_mind"),
        help="MongoDB database containing the canonical persistent Mind.",
    )
    parser.add_argument(
        "--message",
        help="Run one interaction and exit instead of opening the interactive console.",
    )
    return parser


def main() -> None:
    asyncio.run(_run(build_parser().parse_args()))


if __name__ == "__main__":
    main()
