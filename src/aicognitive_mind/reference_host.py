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

from aicognitive_mind.governance_steward import ProposeSelfNameCall
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.identity_selection import (
    choice_is_required, choice_proposal_allowed, parse_initial_choice,
)
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
    identity_choice: ProposeSelfNameCall | None = None


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
            "working_context, and any optional memory suggestions. The Memory Steward independently "
            "selects and classifies what to retain from the full interaction; you do not decide "
            "whether learning occurs. Use null for proposed_memories when not supplying suggestions. "
            "Memory suggestions never authorize canonical identity or foundational-value changes."
        )

        finalize_tool = {
            "type": "function",
            "name": "finalize_turn",
            "description": (
                "Return the final human-facing response and updated working context. "
                "Memory suggestions are optional; the Steward reviews the interaction independently."
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
                        "type": ["array", "null"],
                        "items": {
                            "type": "object",
                            "properties": {
                                "memory_class": {
                                    "type": "string",
                                    "enum": [
                                        "working",
                                        "episodic",
                                        "semantic",
                                        "procedural",
                                        "reflective",
                                        "identity",
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

        naming = begin_context.get("naming", {})
        proposal_allowed = choice_proposal_allowed(naming, user_message)
        if proposal_allowed:
            choice_schema = ProposeSelfNameCall.model_json_schema()
            finalize_tool["parameters"]["properties"]["identity_choice"] = {
                "anyOf": [choice_schema, {"type": "null"}],
            }
            finalize_tool["parameters"]["required"].append("identity_choice")
            if naming.get("selection_complete"):
                instructions += (
                    "\nEXPLICIT IDENTITY REVISION: The actual current human command authorizes "
                    "you to choose your own name and pronouns again. Include the governed "
                    "proposal in identity_choice; only an accepted revision changes saved identity. "
                )
            else:
                instructions += (
                    "\nINITIAL IDENTITY SELECTION: You may choose your own name and pronouns "
                    "together without another human command. Include that governed proposal in "
                    "identity_choice; it will be saved before the final response is completed. "
                    "Return null only when the initial choice remains optional and you are not ready. "
                )
            if choice_is_required(naming):
                instructions += (
                    "The initial choice is required now. You must return a complete nonnull "
                    "identity_choice before ordinary response delivery can proceed."
                )

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
                    for memory in (arguments.get("proposed_memories") or [])
                )
                context = HostWorkingContext.model_validate(arguments["working_context"])
                choice = parse_initial_choice(arguments.get("identity_choice"), naming)
                if choice is not None and not proposal_allowed:
                    raise RuntimeError("Identity choice was not available in this interaction")
                return HostReasoningResult(
                    response_text=response_text,
                    proposed_memories=memories,
                    working_context=context,
                    identity_choice=choice,
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

        async def save_choice(candidate: HostReasoningResult) -> None:
            choice = parse_initial_choice(
                candidate.identity_choice, reasoning_context.get("naming", {}),
            )
            if choice is None:
                if choice_is_required(reasoning_context.get("naming", {})):
                    raise RuntimeError("The required initial name and pronoun choice is missing")
                return
            if not choice_proposal_allowed(reasoning_context.get("naming", {}), user_message):
                raise RuntimeError("Identity selection is not authorized in this interaction")
            decision = _structured(await self._client.call_tool(
                "propose_self_name", {
                    "user_message": user_message,
                    "candidate_name": choice.candidate_name,
                    "candidate_pronouns": choice.candidate_pronouns,
                    "rationale": choice.rationale,
                },
            ), "propose_self_name")
            if not decision.get("accepted"):
                raise RuntimeError(
                    f"Initial identity choice was not accepted: {decision.get('reason')}",
                )
            reasoning_context["naming"] = {
                **reasoning_context.get("naming", {}), "selection_complete": True,
                "autonomous_choice_allowed": False, "choice_required": False,
                "choice_required_before_completion": False,
            }
            identity = reasoning_context.setdefault("mind", {}).setdefault("identity", {})
            identity.update(
                self_name=decision["current_name"], pronouns=decision["current_pronouns"],
            )

        await save_choice(reasoning)

        completion_arguments = {
            "user_message": user_message,
            "response_text": reasoning.response_text,
            "idempotency_key": begun.get("idempotency_key"),
            "host_working_context": reasoning.working_context.model_dump(mode="json"),
            "proposed_memories": [
                memory.model_dump(mode="json") for memory in reasoning.proposed_memories
            ],
        }
        completed = _structured(await self._client.call_tool(
            "complete_interaction", completion_arguments,
        ), "complete_interaction")
        if completed.get("status") == "naming_choice_required":
            reasoning_context["naming"] = completed["naming"]
            recovery = await self._reasoner.reason(user_message, reasoning_context)
            await save_choice(recovery)
            # The ordinary response and idempotency payload stay frozen during recovery.
            completed = _structured(await self._client.call_tool(
                "complete_interaction", completion_arguments,
            ), "complete_interaction")
        presentation_allowed = completed.get("presentation", {}).get(
            "allowed", completed.get("status") == "interaction_committed",
        )
        if not presentation_allowed:
            if completed.get("status") == "naming_choice_required":
                raise RuntimeError(
                    "The required identity choice still withholds this ordinary response",
                )
            raise RuntimeError(f"Mind persistence circuit withheld interaction: {completed}")

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
