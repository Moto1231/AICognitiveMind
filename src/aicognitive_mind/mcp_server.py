from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import Context, MCPServer

from aicognitive_mind.config import get_settings
from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.memory_steward import ResearchObservation
from aicognitive_mind.persistence import StorageRuntime, create_storage


@dataclass
class AppState:
    runtime: StorageRuntime
    mind_service: CognitiveMcpService


@asynccontextmanager
async def lifespan(_server: MCPServer[AppState]) -> AsyncIterator[AppState]:
    storage = await create_storage(get_settings())
    try:
        yield AppState(
            runtime=storage.runtime,
            mind_service=CognitiveMcpService(
                mind=storage.mind,
                journal=storage.journal,
                memory=storage.memory,
            ),
        )
    finally:
        await storage.runtime.close()


mcp = MCPServer("Digital Genesis Cognitive Mind", lifespan=lifespan)


@mcp.tool()
async def initialize_mind(
    self_name: str,
    foundational_values: list[str],
    ctx: Context[AppState],
) -> dict[str, Any]:
    """Initialize the one persistent Mind for this deployment.

    Call this only when the Mind has never been initialized. A second initialization is rejected.
    Identity belongs to the Mind and remains independent of whichever MCP host/model is connected.
    """
    return await ctx.request_context.lifespan_context.mind_service.initialize(
        self_name=self_name,
        foundational_values=tuple(foundational_values),
    )


@mcp.tool()
async def mind_status(ctx: Context[AppState]) -> dict[str, Any]:
    """Read the persistent Mind identity and continuity counters.

    Use this for administration, diagnostics, and demonstrations that identity/memory remain
    present when the connected reasoning model or MCP host changes.
    """
    return await ctx.request_context.lifespan_context.mind_service.status()


@mcp.tool()
async def begin_interaction(
    user_message: str,
    ctx: Context[AppState],
) -> dict[str, Any]:
    """Mandatory first step before answering a human as this Cognitive Mind.

    Returns identity plus related durable memory and prior experience. The connected MCP host
    supplies reasoning; the Mind supplies continuity. Do not answer the human as the Mind before
    consulting this tool.
    """
    return await ctx.request_context.lifespan_context.mind_service.begin_interaction(user_message)


@mcp.tool()
async def complete_interaction(
    user_message: str,
    response_text: str,
    proposed_memories: list[MemoryProposal],
    ctx: Context[AppState],
    current_evidence: list[ResearchObservation] | None = None,
) -> dict[str, Any]:
    """Mandatory final step after reasoning and before presenting the final answer.

    The connected model proposes only stable learning worth preserving. The Memory Steward
    independently accepts/rejects those proposals, commits accepted durable memory, and journals
    the complete user/response experience. Pass an empty list when nothing deserves retention.
    When current external evidence materially informed reasoning, include it with its separate
    provenance / confidence / weight appraisal. These dimensions are not collapsed into one score.
    """
    return await ctx.request_context.lifespan_context.mind_service.complete_interaction(
        user_message=user_message,
        response_text=response_text,
        proposed_memories=tuple(proposed_memories),
        current_evidence=tuple(current_evidence or ()),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Digital Genesis Cognitive Mind MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
        help="MCP transport. Use stdio for local hosts such as VS Code.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    transport = args.transport
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    mcp.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        json_response=True,
        stateless_http=True,
    )


if __name__ == "__main__":
    main()
