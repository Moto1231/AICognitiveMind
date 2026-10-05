from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Any, Protocol

from mcp import Client, StdioServerParameters
from openai import AsyncOpenAI

from aicognitive_mind.host_context import HostWorkingContext
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
    working_context: "HostWorkingContext" = field(default_factory=lambda: HostWorkingContext())


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
    """OpenAI reasoning process integrated into Axiom's host-maintained session."""

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
        working_context = HostWorkingContext.model_validate(
            begin_context.get("host_working_context", {})
        )

        instructions = (
            f"{contract}\n\n"
            "HOST BOUNDARY:\n"
            "The MCP host already completed begin_interaction for this turn. "
            "Reason using the supplied Mind identity and recalled context. "
            "You are Axiom's active reasoning faculty. Maintain the supplied working_context "
            "as your volatile, session-local short-term context and update it on every turn. "
            "Track participants, the current speaker and addressee, topic, and unresolved references. "
            "Keep identity_status unresolved or candidate unless current evidence or explicit "
            "confirmation grounds a known identity; do not turn a person mentioned in history into "
            "the person currently present. Preserve evidence and uncertainty in grounding. "
            "When the answer is ready, call finalize_turn with the human-facing response, the updated "
            "working_context, and only stable learning that deserves durable-memory review. "
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
                    "working_context": {
                        "type": "object",
                        "properties": {
                            "summary": {"type": "string", "maxLength": 2000},
                            "participants": {
                                "type": "array",
                                "maxItems": 32,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "participant_id": {"type": "string", "maxLength": 80},
                                        "name": {"type": ["string", "null"], "maxLength": 120},
                                        "identity_status": {
                                            "type": "string",
                                            "enum": ["unresolved", "candidate", "confirmed"],
                                        },
                                        "presence_status": {
                                            "type": "string",
                                            "enum": ["observed", "reported", "referenced", "unknown"],
                                        },
                                        "relationship": {"type": ["string", "null"], "maxLength": 200},
                                        "grounding": {
                                            "type": "array",
                                            "maxItems": 8,
                                            "items": {"type": "string"},
                                        },
                                    },
                                    "required": [
                                        "participant_id", "name", "identity_status",
                                        "presence_status", "relationship", "grounding",
                                    ],
                                    "additionalProperties": False,
                                },
                            },
                            "active_speaker": {"type": ["string", "null"], "maxLength": 80},
                            "addressee": {"type": ["string", "null"], "maxLength": 80},
                            "unresolved_references": {
                                "type": "array",
                                "maxItems": 24,
                                "items": {"type": "string"},
                            },
                        },
                        "required": [
                            "summary", "participants", "active_speaker", "addressee",
                            "unresolved_references",
                        ],
                        "additionalProperties": False,
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
                "required": ["response_text", "working_context", "proposed_memories"],
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
                    "working_context": working_context.model_dump(mode="json"),
                },
                default=str,
            ),
            tools=[finalize_tool],
            tool_choice={"type": "function", "name": "finalize_turn"},
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
                context = HostWorkingContext.model_validate(arguments["working_context"])
                return HostReasoningResult(
                    response_text=response_text,
                    proposed_memories=memories,
                    working_context=context,
                )

        response_text = response.output_text.strip()
        if not response_text:
            raise RuntimeError(
                "Reasoning host returned neither finalize_turn nor response text"
            )
        raise RuntimeError("Reasoning host did not return the required finalize_turn context")


class CognitiveMindHost:
    """One conversation host; its volatile working context is private to this instance."""

    def __init__(self, client: Any, reasoner: HostReasoner) -> None:
        self._client = client
        self._reasoner = reasoner
        self._working_context = HostWorkingContext()

    async def interact(self, user_message: str) -> HostTurn:
        begun = _structured(
            await self._client.call_tool(
                "begin_interaction",
                {
                    "user_message": user_message,
                    "host_working_context": self._working_context.model_dump(mode="json"),
                },
            ),
            "begin_interaction",
        )
        if begun.get("status") != "ready_to_reason":
            raise RuntimeError(f"Mind is not ready to reason: {begun}")

        returned_context = HostWorkingContext.model_validate(
            begun.get("host_working_context", {})
        )
        if returned_context != self._working_context:
            raise RuntimeError("Mind returned different host working context than submitted")
        reasoning_context = dict(begun)
        reasoning = await self._reasoner.reason(user_message, reasoning_context)

        completed = _structured(
            await self._client.call_tool(
                "complete_interaction",
                {
                    "user_message": user_message,
                    "response_text": reasoning.response_text,
                    "idempotency_key": begun.get("idempotency_key"),
                    "host_working_context": reasoning.working_context.model_dump(mode="json"),
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

        self._working_context = HostWorkingContext.model_validate(
            completed.get("host_working_context", {})
        )

        return HostTurn(
            response_text=reasoning.response_text,
            memory_decisions=tuple(completed.get("memory_decisions", [])),
        )


def _server_environment(args: argparse.Namespace) -> dict[str, str]:
    env = os.environ.copy()
    env["STORAGE_PROVIDER"] = "mongo"
    env["MONGODB_URI"] = args.mongodb_uri
    env["MONGODB_DATABASE"] = args.mongodb_database
    env["APP_NAME"] = "Axiom"
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
