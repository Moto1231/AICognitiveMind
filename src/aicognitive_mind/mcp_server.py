from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from mcp.server.mcpserver import Context, MCPServer

from aicognitive_mind.config import get_settings
from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.mongo_storage import (
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
    MongoRuntime,
)


@dataclass
class AppState:
    runtime: MongoRuntime
    mind_service: CognitiveMcpService


@asynccontextmanager
async def lifespan(_server: MCPServer[AppState]) -> AsyncIterator[AppState]:
    settings = get_settings()
    runtime = MongoRuntime(settings.mongodb_uri, settings.mongodb_database)
    await runtime.initialize()
    try:
        yield AppState(
            runtime=runtime,
            mind_service=CognitiveMcpService(
                mind=MongoMindStore(runtime.database),
                journal=MongoJournalStore(runtime.database),
                memory=MongoMemoryStore(runtime.database),
            ),
        )
    finally:
        await runtime.close()


mcp = MCPServer("Digital Genesis Cognitive Mind", lifespan=lifespan)


@mcp.tool()
async def initialize_mind(
    self_name: str,
    foundational_values: list[str],
    ctx: Context[AppState],
) -> dict:
    """Initialize the one persistent Mind for this deployment.

    Call this only when the Mind has never been initialized. A second initialization is rejected.
    Identity belongs to the Mind and remains independent of whichever MCP host/model is connected.
    """
    return await ctx.lifespan.mind_service.initialize(
        self_name=self_name,
        foundational_values=tuple(foundational_values),
    )


@mcp.tool()
async def mind_status(ctx: Context[AppState]) -> dict:
    """Read the persistent Mind identity and continuity counters.

    Use this for administration, diagnostics, and demonstrations that identity/memory remain
    present when the connected reasoning model or MCP host changes.
    """
    return await ctx.lifespan.mind_service.status()


@mcp.tool()
async def begin_interaction(
    user_message: str,
    ctx: Context[AppState],
) -> dict:
    """Mandatory first step before answering a human as this Cognitive Mind.

    Returns identity plus related durable memory and prior experience. The connected MCP host
    supplies reasoning; the Mind supplies continuity. Do not answer the human as the Mind before
    consulting this tool.
    """
    return await ctx.lifespan.mind_service.begin_interaction(user_message)


@mcp.tool()
async def complete_interaction(
    user_message: str,
    response_text: str,
    proposed_memories: list[MemoryProposal],
    ctx: Context[AppState],
) -> dict:
    """Mandatory final step after reasoning and before presenting the final answer.

    The connected model proposes only stable learning worth preserving. The Memory Steward
    independently accepts/rejects those proposals, commits accepted durable memory, and journals
    the complete user/response experience. Pass an empty list when nothing deserves retention.
    """
    return await ctx.lifespan.mind_service.complete_interaction(
        user_message=user_message,
        response_text=response_text,
        proposed_memories=tuple(proposed_memories),
    )


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
        json_response=True,
        stateless_http=True,
    )
