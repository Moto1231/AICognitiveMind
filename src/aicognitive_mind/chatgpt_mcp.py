from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import AudioContent, CallToolResult, ImageContent, TextContent
from pydantic import AnyHttpUrl

from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
from aicognitive_mind.mcp_server import AppState, lifespan
from aicognitive_mind.mcp_service import MemoryProposal
from aicognitive_mind.memory_steward import ResearchObservation


HOST_INSTRUCTIONS = """
Axiom is the persistent Cognitive Mind. You are the replaceable reasoning host.

When the user is interacting through Axiom:
1. Call begin_interaction with the user's actual message before reasoning or answering.
2. Treat the returned Mind identity, recalled memory, continuity, and conscious-workspace
   contract as authoritative Axiom context. Do not claim that the host model owns Axiom's
   identity or durable memory.
3. Reason normally using that context and any other tools needed for the user's task.
4. Before presenting the human-facing answer, call complete_interaction with the exact user
   message, the response you intend to give, the idempotency_key returned by begin_interaction,
   and only stable learning worth review by Axiom's Memory Steward. Use an empty memory list
   when nothing should persist.
5. Present the same committed response to the user.

Do not bypass begin_interaction/complete_interaction merely because the answer seems simple.
The Mind owns continuity; the reasoning host supplies inference.
""".strip()


def build_chatgpt_mcp(
    base_url: str,
    provider: AxiomAuthorizationServerProvider,
) -> MCPServer[AppState]:
    base_url = base_url.rstrip("/")
    resource_url = base_url + "/mcp"
    scope = provider.required_scope
    auth = AuthSettings(
        issuer_url=AnyHttpUrl(base_url),
        resource_server_url=AnyHttpUrl(resource_url),
        required_scopes=[scope],
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            valid_scopes=[scope, "offline_access"],
            default_scopes=[scope],
        ),
        validate_token_resource=True,
    )

    server: MCPServer[AppState] = MCPServer(
        "axiom-mind",
        title="Axiom Mind",
        description="Persistent identity, memory, continuity, and governed experience for an external AI reasoning host.",
        instructions=HOST_INSTRUCTIONS,
        version="0.1.0",
        lifespan=lifespan,
        auth=auth,
        auth_server_provider=provider,
    )

    @server.tool()
    async def mind_status(ctx: Context[AppState]) -> dict[str, Any]:
        """Read Axiom's persistent identity and continuity status.

        This is diagnostic/read-only. It demonstrates that the Mind persists independently
        of whichever reasoning host or model is currently connected.
        """
        return await ctx.request_context.lifespan_context.mind_service.status()

    @server.tool()
    async def begin_interaction(
        user_message: str,
        ctx: Context[AppState],
    ) -> dict[str, Any]:
        """MANDATORY before answering a human while using Axiom.

        Supply the user's actual message. Returns Axiom identity, recalled durable memory,
        relevant prior experience, conscious-workspace guidance, and an idempotency key.
        Reason only after consulting this result.
        """
        return await ctx.request_context.lifespan_context.mind_service.begin_interaction(
            user_message
        )

    @server.tool()
    async def complete_interaction(
        user_message: str,
        response_text: str,
        ctx: Context[AppState],
        idempotency_key: str | None = None,
        proposed_memories: list[MemoryProposal] | None = None,
        current_evidence: list[ResearchObservation] | None = None,
    ) -> dict[str, Any]:
        """MANDATORY after reasoning and before presenting Axiom's answer.

        response_text must be the human-facing answer you intend to present. Propose only
        stable learning worth durable-memory review; use an empty list when nothing should
        persist. The independent Memory Steward decides what is actually retained and the
        interaction is journaled. Reuse the begin_interaction idempotency key on retries.
        """
        return await ctx.request_context.lifespan_context.mind_service.complete_interaction(
            user_message=user_message,
            response_text=response_text,
            proposed_memories=tuple(proposed_memories or ()),
            current_evidence=tuple(current_evidence or ()),
            idempotency_key=idempotency_key,
        )

    @server.tool()
    async def read_sensory_evidence(
        sha256: str,
        captured_at: str,
        ctx: Context[AppState],
    ) -> CallToolResult:
        """Read an integrity-checked original image/audio artifact referenced by Axiom context.

        Use only when begin_interaction or Body context includes a sensory evidence reference
        whose original media is materially needed for reasoning.
        """
        from datetime import datetime

        storage = ctx.request_context.lifespan_context.storage
        artifact = await storage.evidence.find_exact(
            sha256=sha256,
            captured_at=datetime.fromisoformat(captured_at),
        )
        if artifact is None:
            raise ValueError("Sensory evidence not found")
        payload = base64.b64decode(artifact.payload_base64, validate=True)
        if hashlib.sha256(payload).hexdigest() != artifact.sha256:
            raise ValueError("Sensory evidence integrity check failed")

        reference = artifact.reference().model_dump(mode="json")
        if artifact.media_type.startswith("image/"):
            media = ImageContent(
                type="image",
                data=artifact.payload_base64,
                mime_type=artifact.media_type,
            )
        elif artifact.media_type.startswith("audio/"):
            media = AudioContent(
                type="audio",
                data=artifact.payload_base64,
                mime_type=artifact.media_type,
            )
        else:
            raise ValueError("Unsupported sensory media type")

        return CallToolResult(
            content=[
                TextContent(type="text", text=json.dumps(reference)),
                media,
            ],
            structured_content={
                "evidence": reference,
                "integrity_verified": True,
            },
        )

    return server
