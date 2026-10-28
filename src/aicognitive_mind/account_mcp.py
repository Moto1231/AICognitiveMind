"""Bind authenticated MCP calls to existing account stores, per request."""

from __future__ import annotations

from contextvars import ContextVar
from functools import wraps
import inspect
from typing import Any

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.shared.exceptions import MCPError

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.host_runtime import HostRuntime, RuntimeRecords
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.persistence import scope_storage
from aicognitive_mind.task_dispatcher import TaskModelDispatcher


_request_state: ContextVar[Any | None] = ContextVar("axiom_account_state", default=None)


def request_state(ctx: Any) -> Any:
    """Use the verified call scope; ordinary local/stdio tools retain their state."""
    scoped = _request_state.get()
    return scoped if scoped is not None else ctx.request_context.lifespan_context


async def authorized_account(provider: Any, token: Any) -> Any:
    """Validate the server-verified subject against live account identity."""
    if (
        token is None
        or not isinstance(token.subject, str)
        or not token.subject
        or provider.required_scope not in token.scopes
        or token.resource != provider.resource_url
    ):
        raise MCPError(code=-32001, message="An authenticated Axiom account is required")

    # A persistent MCP transport can retain the verified token between calls.
    # Recheck its originating portal session before every Realtime tool call,
    # including calls whose access token is still valid in the OAuth cache.
    if token.client_id == "axiom-realtime" and not await provider.access_token_session_active(token):
        raise MCPError(code=-32001, message="The Realtime portal session has ended")

    account = None
    accounts = getattr(provider, "accounts", None)
    if accounts is not None:
        try:
            account = await accounts.resolve_subject(token.subject)
        except (CommitConflict, ValueError) as exc:
            raise MCPError(code=-32001, message="The authenticated account is ambiguous") from exc

    if token.subject == provider.username:
        # The configured operator is an explicit legacy root principal. A
        # colliding account selector must never silently gain root access.
        if account is not None:
            raise MCPError(code=-32001, message="The authenticated account is ambiguous")
        return None
    if account is None:
        raise MCPError(code=-32001, message="The authenticated account is unavailable")
    return account


async def authorized_state(root: Any, provider: Any) -> Any:
    """Select the same verified tenant for tools and raw MCP protocol methods."""
    account = await authorized_account(provider, get_access_token())
    if account is None or account.mind_id == "__legacy__":
        return root

    # Import lazily: the local MCP server also uses request_state for shared
    # task execution, without depending on authenticated HTTP construction.
    from aicognitive_mind.mcp_server import AppState

    storage = scope_storage(root.storage, account.mind_id)
    service = CognitiveMcpService(
        mind=storage.mind, journal=storage.journal, memory=storage.memory,
    )
    startup_probe = getattr(root, "tenancy_probe", None)
    verification = None
    if isinstance(startup_probe, dict):
        # Startup verified the shared backend, not this account's initialization.
        # Do not expose the root or synthetic probe selectors to another account.
        verification = {
            key: startup_probe[key]
            for key in ("status", "provider", "verified_collections")
            if key in startup_probe
        }
        verification["verification_scope"] = "deployment_startup"
    return AppState(
        runtime=storage.runtime,
        mind_service=service,
        storage=storage,
        hosts=HostRuntime(storage.mind, service),
        task_dispatcher=TaskModelDispatcher(RuntimeRecords(storage.mind)),
        tenancy_probe=verification,
    )


async def _authorized_state(ctx: Any, provider: Any) -> Any:
    return await authorized_state(ctx.request_context.lifespan_context, provider)


def account_tools(server: Any, provider: Any) -> Any:
    """Preserve tool schemas while guarding every tool that accesses mind state."""
    def tool(**options: Any) -> Any:
        def register(fn: Any) -> Any:
            signature = inspect.signature(fn)
            if "ctx" not in signature.parameters:
                # Static URLs and existing synchronous external capabilities do
                # not select a mind; preserve SDK authentication/execution.
                return server.tool(**options)(fn)

            @wraps(fn)
            async def scoped(*args: Any, **kwargs: Any) -> Any:
                ctx = signature.bind(*args, **kwargs).arguments["ctx"]
                state = await _authorized_state(ctx, provider)
                selected = _request_state.set(state)
                try:
                    return await fn(*args, **kwargs)
                finally:
                    _request_state.reset(selected)

            return server.tool(**options)(scoped)
        return register
    return tool
