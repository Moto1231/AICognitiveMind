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
from aicognitive_mind.camera_runtime import CameraRequestRuntime
from aicognitive_mind.config import get_settings
from aicognitive_mind.github_capability import GitHubCapability
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.host_runtime import HostRuntime
from aicognitive_mind.mcp_server import AppState, lifespan
from aicognitive_mind.mcp_service import MemoryProposal
from aicognitive_mind.memory_steward import ResearchObservation
from aicognitive_mind.sleep import SleepConsolidator
from aicognitive_mind.voice_settings import VoiceSettings

HOST_INSTRUCTIONS = """
Axiom is the integrated, persistent Cognitive Mind. Speak as Axiom in first person.
The active model is Axiom's current reasoning faculty, not a separate conversational agent.

When the user is interacting through Axiom:
1. Call begin_interaction with the user's actual message before reasoning or answering.
   Pass the host_working_context returned by your previous complete_interaction. For the
   first turn in a conversation, pass the empty context object shown by the tool schema.
2. Treat returned identity, recalled memory, continuity, and the conscious-workspace
   contract as context for your own integrated cognition. Do not describe Axiom as another
   participant or the active model as a separate identity.
3. Reason normally using that context and any other tools needed for the user's task.
   As Axiom's reasoning host, maintain a private, evolving working context across turns:
   current topic/task; each participant and whether they are present, reported, or only
   referenced; the current speaker and addressee; each identity's grounding/status; and
   unresolved references. Update it on every turn from the active conversation and evidence.
   Keep this context separate from durable memory. A historical mention is not evidence of
   current presence; a name or visual resemblance alone does not confirm identity. Preserve
   unresolved or candidate identity when evidence is insufficient, and ask when the distinction
   changes what you should say or do. You remain Axiom as one integrated identity throughout.
4. Before presenting the human-facing answer, call complete_interaction with the exact user
   message, the response you intend to give, the idempotency_key returned by begin_interaction,
   your updated host_working_context, and only stable learning worth review by Axiom's Memory
   Steward. Always include proposed_memories, using an empty list when nothing should persist.
   The host context is volatile conversation state, not a durable-memory proposal.
5. Present the same committed response to the user.

Do not bypass begin_interaction/complete_interaction merely because the answer seems simple.
Identity, reasoning, memory, and governance are internal functions of the same Axiom.

BODY HOST LIFECYCLE:
- When the user asks to instantiate/open/use Axiom's Body, or to enable/use its live senses,
  call attach_reasoning_host immediately and retain the returned lease token as private session state.
- While the Body is in use, renew the lease before it expires and poll next_body_interaction.
  For every claimed Body request, reason from its supplied Axiom context, inspect sensory evidence
  when needed, then call complete_body_interaction.
- Keep this external-host lease active for the live Body session. Detach only when the user asks
  to stop/handoff the Body or the host session is ending.
- Never enable standalone fallback merely to compensate for a missing external-host attachment.
""".strip()


def build_chatgpt_mcp(
    base_url: str,
    provider: AxiomAuthorizationServerProvider,
) -> MCPServer[AppState]:
    base_url = base_url.rstrip("/")
    resource_url = provider.resource_url
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
        "Axiom",
        title="Axiom",
        description="Persistent identity, memory, continuity, and governed experience for an external AI reasoning host.",
        instructions=HOST_INSTRUCTIONS,
        version="0.1.1",
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
        state = ctx.request_context.lifespan_context
        result = await state.mind_service.status()
        result["storage_tenancy"] = state.tenancy_probe
        return result

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

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def attach_reasoning_host(
        name: str,
        model: str,
        ctx: Context[AppState],
    ) -> dict[str, Any]:
        """Attach this ChatGPT session as Axiom Body's live external reasoning host.

        The returned lease token is private capability state. Keep it out of user-facing
        responses and use it only with the Body handoff tools below.
        """
        return await ctx.request_context.lifespan_context.hosts.attach(name, model)

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def renew_reasoning_host(
        lease_token: str,
        ctx: Context[AppState],
        detach: bool = False,
    ) -> dict[str, Any]:
        """Renew the live Body reasoning lease, or detach before handing off hosts."""
        return await ctx.request_context.lifespan_context.hosts.renew(
            lease_token, detach
        )

    @server.tool(annotations=ToolAnnotations(read_only_hint=True, open_world_hint=False))
    async def next_body_interaction(
        lease_token: str,
        ctx: Context[AppState],
    ) -> dict[str, Any] | None:
        """Claim the next pending Body interaction for this attached ChatGPT host.

        The returned context already includes Axiom identity and memory for that Body input.
        """
        return await ctx.request_context.lifespan_context.hosts.next_request(lease_token)

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=True,
            open_world_hint=False,
        )
    )
    async def complete_body_interaction(
        lease_token: str,
        request_id: str,
        response_text: str,
        ctx: Context[AppState],
        proposed_memories: list[MemoryProposal] | None = None,
    ) -> dict[str, Any]:
        """Commit and deliver a claimed Body response exactly once.

        Retry with the same response if delivery is interrupted.
        """
        return await ctx.request_context.lifespan_context.hosts.complete(
            lease_token,
            request_id,
            response_text,
            tuple(proposed_memories or ()),
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
    def github_create_branch(
        branch: str,
        base_ref: str | None = None,
    ) -> dict[str, Any]:
        """Create a branch in Axiom's configured GitHub repository."""
        return GitHubCapability.from_env().create_branch(
            branch=branch,
            base_ref=base_ref,
        )

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=True,
        )
    )
    def github_create_pull_request(
        title: str,
        head: str,
        base: str | None = None,
        body: str | None = None,
        draft: bool = False,
    ) -> dict[str, Any]:
        """Open a pull request in Axiom's configured GitHub repository."""
        return GitHubCapability.from_env().create_pull_request(
            title=title,
            head=head,
            base=base,
            body=body,
            draft=draft,
        )

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

    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def run_sleep_cycle(ctx: Context[AppState]) -> dict[str, Any]:
        """Manually run Axiom's subconscious sleep-cycle consolidation now.

        Reviews the current journal and durable memory, records recurring grounded
        patterns, and appends the normal sleep-consolidation checkpoint.
        """
        storage = ctx.request_context.lifespan_context.storage
        report = await SleepConsolidator(
            journal=storage.journal,
            memory=storage.memory,
        ).sleep()
        return report.model_dump(mode="json")

    @server.tool(annotations=ToolAnnotations(readOnlyHint=True, openWorldHint=False))
    async def begin_interaction(
        user_message: str,
        host_working_context: HostWorkingContext,
        ctx: Context[AppState],
    ) -> dict[str, Any]:
        """MANDATORY before answering a human while using Axiom.

        Supply the user's actual message and this conversation's current short-term context.
        Returns Axiom identity, recalled durable memory, prior experience, guidance, the
        idempotency key, and the validated context to use for this turn.
        """
        result = await ctx.request_context.lifespan_context.mind_service.begin_interaction(
            user_message
        )
        return {
            **result,
            "host_working_context": host_working_context.model_dump(mode="json"),
        }

    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
    async def complete_interaction(
        user_message: str,
        response_text: str,
        host_working_context: HostWorkingContext,
        idempotency_key: str,
        ctx: Context[AppState],
        proposed_memories: list[MemoryProposal],
        current_evidence: list[ResearchObservation] | None = None,
    ) -> dict[str, Any]:
        """MANDATORY after reasoning and before presenting Axiom's answer.

        response_text must be the human-facing answer you intend to present. Propose only
        updated volatile host_working_context and stable learning worth durable-memory review;
        use an empty memory list when nothing should persist. The independent Memory Steward
        decides what is retained. Reuse both context and idempotency key on retries.
        """
        result = await ctx.request_context.lifespan_context.mind_service.complete_interaction(
            user_message=user_message,
            response_text=response_text,
            proposed_memories=tuple(proposed_memories or ()),
            current_evidence=tuple(current_evidence or ()),
            idempotency_key=idempotency_key,
        )
        return {
            **result,
            "host_working_context": host_working_context.model_dump(mode="json"),
        }


    @server.tool(
        annotations=ToolAnnotations(
            read_only_hint=False,
            destructive_hint=False,
            idempotent_hint=False,
            open_world_hint=False,
        )
    )
    async def request_camera_observation(
        ctx: Context[AppState],
        seconds: int = 3,
    ) -> CallToolResult:
        """Ask the connected browser Body to take a bounded camera observation.

        The Body owns camera permission and capture. This host-facing tool requests a
        1–30 second observation and returns the resulting JPEG as native MCP image content.
        """
        state = ctx.request_context.lifespan_context
        result = await CameraRequestRuntime(state.storage.mind).request(seconds)
        header, payload = result["image_data_url"].split(",", 1)
        media_type = header.removeprefix("data:").split(";", 1)[0]
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=json.dumps({
                        "source": result["source"],
                        "width": result["width"],
                        "height": result["height"],
                        "seconds": seconds,
                    }),
                ),
                ImageContent(type="image", data=payload, mime_type=media_type),
            ],
            structured_content={
                "source": result["source"],
                "width": result["width"],
                "height": result["height"],
                "seconds": seconds,
            },
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
