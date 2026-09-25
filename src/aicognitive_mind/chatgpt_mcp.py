from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import Context, MCPServer
from mcp.types import AudioContent, CallToolResult, ImageContent, TextContent, ToolAnnotations
from pydantic import AnyHttpUrl

from aicognitive_mind.chatgpt_oauth import AxiomAuthorizationServerProvider
from aicognitive_mind.config import get_settings
from aicognitive_mind.github_capability import GitHubCapability
from aicognitive_mind.host_runtime import HostRuntime
from aicognitive_mind.mcp_server import AppState, lifespan
from aicognitive_mind.mcp_service import MemoryProposal
from aicognitive_mind.memory_steward import ResearchObservation
from aicognitive_mind.voice_settings import VoiceSettings

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
        title="Axiom",
        description="Persistent identity, memory, continuity, and governed experience for an external AI reasoning host.",
        instructions=HOST_INSTRUCTIONS,
        version="0.1.0",
        lifespan=lifespan,
        auth=auth,
        auth_server_provider=provider,
    )

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    async def mind_status(ctx: Context[AppState]) -> dict[str, Any]:
        """Read Axiom's persistent identity and continuity status.

        This is diagnostic/read-only. It demonstrates that the Mind persists independently
        of whichever reasoning host or model is currently connected.
        """
        return await ctx.request_context.lifespan_context.mind_service.status()

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    async def get_body_voice_settings(ctx: Context[AppState]) -> dict[str, Any]:
        """Read the phone Body's shared voice, speaking rate, pitch, and volume.

        The browser chooses from voices installed on that device. This does not start its mic.
        """
        storage = ctx.request_context.lifespan_context.storage
        return await VoiceSettings(storage.mind).read()

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    async def get_body_reasoning_status(ctx: Context[AppState]) -> dict[str, Any]:
        """Read the phone Body's external host and configured fallback provider/model.

        This reports configuration; it does not guarantee provider quota or availability.
        """
        state = ctx.request_context.lifespan_context
        settings = get_settings()
        provider_name = settings.effective_standalone_reasoning_provider
        requested_model = (
            settings.gemini_model if provider_name == "gemini"
            else settings.openai_model if provider_name == "openai"
            else None
        )
        return {
            "active_external_host": await HostRuntime(
                state.storage.mind, state.mind_service
            ).active(),
            "fallback_provider": provider_name,
            "fallback_requested_model": requested_model,
        }

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def set_body_voice_settings(
        expected_revision: int,
        ctx: Context[AppState],
        voice_name: str | None = None,
        rate: float | None = None,
        pitch: float | None = None,
        volume: float | None = None,
    ) -> dict[str, Any]:
        """Change the phone Body's persisted voice preferences at the user's request.

        First call get_body_voice_settings and pass its revision to prevent lost edits.
        Use voice_name only for a voice known to exist on the user's phone; an unknown
        name falls back to the browser's default voice. This cannot remotely turn on
        a microphone or override the browser's permission requirement.
        """
        storage = ctx.request_context.lifespan_context.storage
        return await VoiceSettings(storage.mind).update(
            expected_revision=expected_revision,
            voice_name=voice_name,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    def github_status() -> dict[str, Any]:
        """Read status for Axiom's configured GitHub repository."""
        return GitHubCapability.from_env().status()

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    def github_list_path(path: str = "", ref: str | None = None) -> dict[str, Any]:
        """List files/directories in Axiom's configured GitHub repository."""
        return GitHubCapability.from_env().list_path(path=path, ref=ref)

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=True))
    def github_read_file(path: str, ref: str | None = None) -> dict[str, Any]:
        """Read a UTF-8 text file from Axiom's configured GitHub repository."""
        return GitHubCapability.from_env().read_file(path=path, ref=ref)

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        )
    )
    def github_write_file(
        path: str,
        content: str,
        message: str,
        branch: str | None = None,
    ) -> dict[str, Any]:
        """Create or replace a UTF-8 text file in Axiom's configured GitHub repository."""
        return GitHubCapability.from_env().write_file(
            path=path,
            content=content,
            message=message,
            branch=branch,
        )

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
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

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
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

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
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
