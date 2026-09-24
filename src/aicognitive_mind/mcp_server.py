from __future__ import annotations

import argparse
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, ImageContent, AudioContent, TextContent

from aicognitive_mind.config import get_settings
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.host_runtime import HostRuntime
from aicognitive_mind.github_capability import GitHubCapability
from aicognitive_mind.mcp_service import (
    BeliefReframeProposal,
    BeliefTransitionProposal,
    CognitiveMcpService,
    MemoryProposal,
)
from aicognitive_mind.memory_steward import ResearchObservation
from aicognitive_mind.persistence import StorageRuntime, create_storage


@dataclass
class AppState:
    runtime: StorageRuntime
    mind_service: CognitiveMcpService
    storage: Any = None
    hosts: Any = None


@asynccontextmanager
async def lifespan(_server: MCPServer[AppState]) -> AsyncIterator[AppState]:
    storage = await create_storage(get_settings())
    try:
        service = CognitiveMcpService(mind=storage.mind, journal=storage.journal, memory=storage.memory)
        yield AppState(runtime=storage.runtime, mind_service=service, storage=storage,
                       hosts=HostRuntime(storage.mind, service))

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
    belief_transitions: list[BeliefTransitionProposal] | None = None,
    belief_reframes: list[BeliefReframeProposal] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Mandatory final step after reasoning and before presenting the final answer.

    The connected model proposes only stable learning worth preserving. The Memory Steward
    independently accepts/rejects those proposals, commits accepted durable memory, and journals
    the complete user/response experience. Pass an empty list when nothing deserves retention.
    When current external evidence materially informed reasoning, include it with its separate
    provenance / confidence / weight appraisal. When evidence bears on a recalled semantic tension,
    also include its semantic interpretation (subject / attribute / value) so the Memory Steward
    can re-deliberate that tension. If research establishes whether the competing values are
    independent and apply to the same time/context, include a tension_finding as well. These
    dimensions are not collapsed into one score. When recall or re-deliberation reports
    candidate_ready, the host may explicitly include that exact subject / attribute / candidate
    value in belief_transitions. The Steward revalidates readiness before changing current belief.
    When readiness is reframe_required and the tension finding contains explicit scopes for both
    values, the host may submit that exact pair in belief_reframes. The Steward revalidates the
    finding and preserves both values as scoped beliefs rather than selecting a winner.
    """
    return await ctx.request_context.lifespan_context.mind_service.complete_interaction(
        user_message=user_message,
        response_text=response_text,
        proposed_memories=tuple(proposed_memories),
        current_evidence=tuple(current_evidence or ()),
        belief_transitions=tuple(belief_transitions or ()),
        belief_reframes=tuple(belief_reframes or ()),
        idempotency_key=idempotency_key,
    )


@mcp.tool()
async def attach_reasoning_host(name: str, model: str, ctx: Context[AppState]) -> dict[str, Any]:
    """Acquire the exclusive 120-second Body reasoning lease; keep the returned token private."""
    return await ctx.request_context.lifespan_context.hosts.attach(name, model)


@mcp.tool()
async def renew_reasoning_host(lease_token: str, ctx: Context[AppState], detach: bool = False) -> dict[str, Any]:
    """Renew the lease while reasoning, or detach before handing off to another host."""
    return await ctx.request_context.lifespan_context.hosts.renew(lease_token, detach)


@mcp.tool()
async def next_body_interaction(lease_token: str, ctx: Context[AppState]) -> dict[str, Any] | None:
    """Claim a Body request and receive its identity/memory context; poll while attached."""
    return await ctx.request_context.lifespan_context.hosts.next_request(lease_token)


@mcp.tool()
async def complete_body_interaction(lease_token: str, request_id: str, response_text: str,
    proposed_memories: list[MemoryProposal], ctx: Context[AppState]) -> dict[str, Any]:
    """Commit and deliver a claimed Body response exactly once; retry with unchanged input."""
    return await ctx.request_context.lifespan_context.hosts.complete(
        lease_token, request_id, response_text, tuple(proposed_memories))


@mcp.tool()
async def propose_self_name(user_message: str, candidate_name: str, rationale: str,
    ctx: Context[AppState]) -> dict[str, Any]:
    """Submit an explicit human self-name command to the same Governance Steward as fallback reasoning."""
    storage = ctx.request_context.lifespan_context.storage
    tool = GovernanceStewardTool(mind=storage.mind, journal=storage.journal, input_text=user_message)
    return await tool.invoke({"action": "propose_self_name", "candidate_name": candidate_name, "rationale": rationale})


@mcp.tool()
async def read_sensory_evidence(sha256: str, captured_at: str, ctx: Context[AppState]) -> CallToolResult:
    """Read integrity-checked original media for host-side interpretation without invoking fallback inference."""
    import base64
    import hashlib
    from datetime import datetime
    storage = ctx.request_context.lifespan_context.storage
    artifact = await storage.evidence.find_exact(sha256=sha256, captured_at=datetime.fromisoformat(captured_at))
    if artifact is None:
        raise ValueError("Sensory evidence not found")
    payload = base64.b64decode(artifact.payload_base64, validate=True)
    if hashlib.sha256(payload).hexdigest() != artifact.sha256:
        raise ValueError("Sensory evidence integrity check failed")
    import json
    reference = artifact.reference().model_dump(mode="json")
    if artifact.media_type.startswith("image/"):
        media = ImageContent(type="image", data=artifact.payload_base64, mime_type=artifact.media_type)
    elif artifact.media_type.startswith("audio/"):
        media = AudioContent(type="audio", data=artifact.payload_base64, mime_type=artifact.media_type)
    else:
        raise ValueError("Unsupported sensory media type")
    return CallToolResult(content=[TextContent(type="text", text=json.dumps(reference)), media],
                          structured_content={"evidence": reference, "integrity_verified": True})


class McpTokenAuth:
    """Authenticate HTTP before MCP tools or request bodies are processed."""
    def __init__(self, app: Any, token: str | None) -> None:
        self.app, self.token = app, token

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        import hmac
        if scope["type"] == "http" and self.token:
            headers = dict(scope.get("headers", []))
            supplied = headers.get(b"authorization", b"")
            expected = ("Bearer " + self.token).encode()
            if not hmac.compare_digest(supplied, expected):
                from starlette.responses import Response
                await Response(status_code=401, headers={"WWW-Authenticate": "Bearer"})(scope, receive, send)
                return
        await self.app(scope, receive, send)


def main() -> None:
    parser = argparse.ArgumentParser(description="Digital Genesis Cognitive Mind MCP server")
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
        help="MCP transport. Use stdio for local hosts such as VS Code.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    transport = args.transport
    if transport == "stdio":
        mcp.run(transport="stdio")
        return

    import uvicorn
    token = get_settings().mcp_access_token
    if args.host not in {"127.0.0.1", "::1", "localhost"} and not token:
        parser.error("MCP_ACCESS_TOKEN is required for non-loopback HTTP binding")
    http_app = mcp.streamable_http_app(host=args.host, json_response=True, stateless_http=True)
    uvicorn.run(McpTokenAuth(http_app, token), host=args.host, port=args.port)



# --- Axiom GitHub capability -------------------------------------------------

@mcp.tool()
def github_status() -> dict:
    """Check the GitHub repository currently connected to Axiom."""
    return GitHubCapability.from_env().status()


@mcp.tool()
def github_list_path(path: str = "", ref: str | None = None) -> dict:
    """List files/directories in Axiom's configured GitHub repository."""
    return GitHubCapability.from_env().list_path(path=path, ref=ref)


@mcp.tool()
def github_read_file(path: str, ref: str | None = None) -> dict:
    """Read a UTF-8 text file from Axiom's configured GitHub repository."""
    return GitHubCapability.from_env().read_file(path=path, ref=ref)


@mcp.tool()
def github_write_file(
    path: str,
    content: str,
    message: str,
    branch: str | None = None,
) -> dict:
    """Create or replace a UTF-8 text file and commit it to Axiom's GitHub repository."""
    return GitHubCapability.from_env().write_file(
        path=path,
        content=content,
        message=message,
        branch=branch,
    )

# --- End Axiom GitHub capability --------------------------------------------


if __name__ == "__main__":
    main()
