"""MCP draft Events: durable message subscriptions and signed webhook delivery."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import logging
import secrets
import socket
import time
from contextlib import asynccontextmanager, suppress
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.shared.exceptions import MCPError
from mcp.types import PaginatedRequestParams, RequestParams
from pydantic import BaseModel, ConfigDict, Field

EVENT_NAME = "message.created"
SENSORY_EVENT_NAME = "sensory.ready"
STATE_KEY = "mcp_message_events_v1"
MAX_ATTEMPTS = 6
logger = logging.getLogger(__name__)
_wakeups: set[asyncio.Event] = set()

EVENT_DEFINITION = {
    "name": EVENT_NAME,
    "description": (
        "A new human text message was durably received by this Axiom mind. "
        "The request_id identifies the message to read, claim, and answer."
    ),
    "delivery": ["webhook"],
    "inputSchema": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Optional Body session filter; omit to receive all human messages.",
                "pattern": "^[A-Za-z0-9_-]{1,128}$",
            },
        },
        "additionalProperties": False,
    },
    "payloadSchema": {
        "type": "object",
        "properties": {
            "mind_id": {"type": "string"},
            "request_id": {"type": "string"},
            "session_id": {"type": "string"},
            "text": {"type": "string", "description": "Preview; read the message for full text."},
        },
        "required": ["mind_id", "request_id", "session_id", "text"],
        "additionalProperties": False,
    },
}

SENSORY_EVENT_DEFINITION = {
    "name": SENSORY_EVENT_NAME,
    "description": (
        "Preserved camera or audio evidence is ready for passive interpretation. "
        "Claim the request with claim_incoming_sensory; this is not a human message."
    ),
    "delivery": ["webhook"],
    "inputSchema": deepcopy(EVENT_DEFINITION["inputSchema"]),
    "payloadSchema": {
        "type": "object",
        "properties": {
            "mind_id": {"type": "string"}, "request_id": {"type": "string"},
            "session_id": {"type": "string"}, "modality": {"enum": ["vision", "audio"]},
            "source": {"type": "string"}, "evidence": {"type": "object"},
        },
        "required": ["mind_id", "request_id", "session_id", "modality", "source", "evidence"],
        "additionalProperties": False,
    },
}
SENSORY_EVENT_DEFINITION["inputSchema"]["properties"]["session_id"]["description"] = (
    "Optional Body session filter; omit to receive this Mind's sensory-ready events."
)


class MessageFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,128}$")


class WebhookDestination(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["webhook"]
    url: str = Field(min_length=1, max_length=8192)


class SignedDestination(WebhookDestination):
    secret: str


class SubscribeParams(RequestParams):
    name: Literal["message.created", "sensory.ready"]
    arguments: MessageFilter = Field(default_factory=MessageFilter)
    delivery: SignedDestination
    cursor: None = None
    ttlMs: int | None = Field(default=None, ge=1)


class UnsubscribeParams(RequestParams):
    name: Literal["message.created", "sensory.ready"]
    arguments: MessageFilter = Field(default_factory=MessageFilter)
    delivery: WebhookDestination


def _secret_key(secret: str) -> bytes:
    try:
        if not secret.startswith("whsec_"):
            raise ValueError
        key = base64.b64decode(secret[6:], validate=True)
        if not 24 <= len(key) <= 64:
            raise ValueError
        return key
    except (ValueError, binascii.Error) as exc:
        raise ValueError("A whsec_ signing key containing 24-64 bytes is required") from exc


def signed_headers(secret: str, event_id: str, body: bytes, timestamp: int) -> dict[str, str]:
    message = event_id.encode() + b"." + str(timestamp).encode() + b"." + body
    signature = base64.b64encode(hmac.digest(_secret_key(secret), message, "sha256")).decode()
    return {
        "Content-Type": "application/json",
        "webhook-id": event_id,
        "webhook-timestamp": str(timestamp),
        "webhook-signature": "v1," + signature,
    }


async def _callback_target(url: str) -> tuple[str, str, str]:
    """Resolve once and pin the connection to a validated public address."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").encode("idna").decode("ascii")
        if (
            parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443)
        ):
            raise ValueError
        answers = await asyncio.wait_for(
            asyncio.get_running_loop().getaddrinfo(
                host, 443, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
            ),
            timeout=5,
        )
        addresses = [str(answer[4][0]) for answer in answers]
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError
        address = addresses[0]
        authority = "[" + address + "]" if ":" in address else address
        target = urlunsplit(("https", authority, parsed.path or "/", parsed.query, ""))
        return target, host, host
    except (ValueError, UnicodeError, OSError) as exc:
        raise ValueError("Callback must resolve to public HTTPS on port 443") from exc


async def post_webhook(
    url: str, secret: str, event_id: str, payload: dict, subscription_id: str,
    previous_secret: str | None = None,
) -> tuple[int, bytes]:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    if len(body) > 256 * 1024:
        raise ValueError("Event exceeds 256 KiB")
    target, host, server_name = await _callback_target(url)
    timestamp = int(time.time())
    headers = signed_headers(secret, event_id, body, timestamp)
    if previous_secret:
        headers["webhook-signature"] += (
            " " + signed_headers(previous_secret, event_id, body, timestamp)["webhook-signature"]
        )
    headers.update({"Host": host, "X-MCP-Subscription-Id": subscription_id})
    # The URL uses the validated address; SNI/certificate validation use the original host.
    # Disabling environment proxies prevents proxy-side DNS from bypassing address pinning.
    async with httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client:
        async with client.stream(
            "POST", target, headers=headers, content=body,
            extensions={"sni_hostname": server_name},
        ) as response:
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 64 * 1024:
                    raise ValueError("Callback response is too large")
            return response.status_code, bytes(chunks)


def event_owner(provider: Any, mind_id: str) -> dict[str, str]:
    token = get_access_token()
    # The caller first selects its verified account stores. The subject must
    # still own that selected Mind; an arbitrary target ID is never authority.
    if token is None or token.subject not in {provider.username, mind_id, "__legacy__"}:
        raise MCPError(code=-32001, message="This account cannot access this mind's events")
    if provider.required_scope not in token.scopes or token.resource != provider.resource_url:
        raise MCPError(code=-32001, message="The Axiom mind scope and resource are required")
    identity = {
        "client_id": token.client_id,
        "subject": token.subject,
        "issuer": str((token.claims or {}).get("iss", "")),
    }
    return {**identity, "id": hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()}


class MessageEvents:
    """One CAS-protected registry/outbox per mind; secrets stay in operational storage."""

    def __init__(self, records: Any, *, post: Any = None, authorized: Any = None) -> None:
        self.records = records
        self.post = post or post_webhook
        self.authorized = authorized

    async def _change(self, change: Any, *, create: bool = False) -> Any:
        for _ in range(12):
            before = await self.records.get(STATE_KEY)
            if before is None and not create:
                return None
            after = deepcopy(before) if before is not None else {
                "subscriptions": {}, "deliveries": {},
            }
            result = change(after)
            if before is None:
                try:
                    await self.records.create(STATE_KEY, after)
                    return result
                except Exception:
                    if await self.records.get(STATE_KEY) is None:
                        raise
            elif after == before or await self.records.replace(STATE_KEY, before, after):
                return result
        raise RuntimeError("Message event state is busy; retry")

    @staticmethod
    def _matches(sub: dict, session_id: str, now: float, name: str = EVENT_NAME) -> bool:
        return sub["name"] == name and sub["expires_at"] > now and (
            not sub["arguments"].get("session_id")
            or sub["arguments"]["session_id"] == session_id
        )

    async def enabled(self, session_id: str = "legacy", name: str = EVENT_NAME) -> bool:
        state = await self.records.get(STATE_KEY)
        return bool(state and any(
            self._matches(sub, session_id, time.time(), name)
            for sub in state["subscriptions"].values()
        ))

    async def subscribe(self, owner: dict, params: SubscribeParams) -> dict:
        _secret_key(params.delivery.secret)
        arguments = params.arguments.model_dump(exclude_none=True)
        identity = [owner["id"], params.delivery.url, params.name, arguments]
        sub_id = "sub_" + hashlib.sha256(
            json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:40]
        now = time.time()
        state = await self.records.get(STATE_KEY) or {"subscriptions": {}}
        previous = state["subscriptions"].get(sub_id)
        # Reuse a recent verification only with the same principal, URL and key.
        verified = bool(
            previous and previous["secret"] == params.delivery.secret
            and previous.get("verified_at", 0) > now - 600
        )
        if not verified:
            challenge = secrets.token_urlsafe(32)
            try:
                status, body = await self.post(
                    params.delivery.url, params.delivery.secret,
                    "msg_verification_" + secrets.token_hex(16),
                    {"type": "verification", "challenge": challenge}, sub_id,
                )
                echoed = json.loads(body).get("challenge")
                if not 200 <= status < 300 or not isinstance(echoed, str):
                    raise ValueError("challenge_failed")
                if not hmac.compare_digest(challenge, echoed):
                    raise ValueError("challenge_failed")
            except (ValueError, httpx.HTTPError, OSError, TimeoutError) as exc:
                reason = "timeout" if isinstance(exc, (TimeoutError, httpx.TimeoutException)) else "challenge_failed"
                raise MCPError(
                    code=-32015, message="Callback verification failed", data={"reason": reason}
                ) from exc
        lifetime = min(max((params.ttlMs or 86_400_000) / 1000, 60), 7 * 86_400)
        expires = now + lifetime

        def save(state: dict) -> None:
            old = state["subscriptions"].get(sub_id)
            sub = {
                "id": sub_id, "owner": owner, "name": params.name, "arguments": arguments,
                "url": params.delivery.url, "secret": params.delivery.secret,
                "expires_at": expires, "created_at": old["created_at"] if old else now,
                "verified_at": now,
            }
            if old and old["secret"] != sub["secret"]:
                sub.update({"previous_secret": old["secret"], "rotate_until": now + 300})
            elif old and old.get("rotate_until", 0) > now:
                sub.update({key: old[key] for key in ("previous_secret", "rotate_until")})
            state["subscriptions"][sub_id] = sub

        await self._change(save, create=True)
        for wake in tuple(_wakeups):
            wake.set()
        return {
            "id": sub_id, "refreshBefore": datetime.fromtimestamp(expires, UTC).isoformat(),
            "cursor": None, "truncated": False,
        }

    async def unsubscribe(self, owner: dict, params: UnsubscribeParams) -> dict:
        arguments = params.arguments.model_dump(exclude_none=True)

        def remove(state: dict) -> None:
            matching = {
                key for key, sub in state["subscriptions"].items()
                if sub["owner"]["id"] == owner["id"] and sub["name"] == params.name
                and sub["url"] == params.delivery.url and sub["arguments"] == arguments
            }
            for key in matching:
                state["subscriptions"].pop(key)
            state["deliveries"] = {
                key: value for key, value in state["deliveries"].items()
                if value["subscription_id"] not in matching
            }

        await self._change(remove)
        return {}

    async def enqueue(self, request: dict) -> None:
        sensory = request.get("task") == "sensory_interpretation"
        if not sensory and request.get("priority", 0) != 0:
            return
        now = time.time()
        if request.get("state") != "pending" or (
            request.get("deadline") is not None and request["deadline"] <= now
        ):
            return
        session = request.get("body_session", "legacy")
        name = SENSORY_EVENT_NAME if sensory else EVENT_NAME
        if sensory:
            context = request.get("input_context", {})
            if context.get("modality") not in {"vision", "audio"}:
                raise ValueError("Sensory event requires a supported modality")
            evidence = context.get("evidence")
            if not isinstance(evidence, dict) or not evidence.get("sha256") or not evidence.get("captured_at"):
                raise ValueError("Sensory event requires preserved evidence")
            data = {
                "mind_id": self.records.mind_id, "request_id": request["request_id"],
                "session_id": session, "modality": context["modality"],
                "source": str(context.get("source", "")), "evidence": deepcopy(evidence),
            }
        else:
            data = {
                "mind_id": self.records.mind_id, "request_id": request["request_id"],
                "session_id": session, "text": request["message"][:4000],
            }
        event = {
            "eventId": "evt_" + request["request_id"],
            "name": name,
            "timestamp": datetime.fromtimestamp(request["created"], UTC).isoformat(),
            "data": data,
            "cursor": None,
        }

        def append(state: dict) -> None:
            for sub_id, sub in state["subscriptions"].items():
                if not self._matches(sub, session, now, name) or sub["created_at"] > request["created"]:
                    continue
                key = sub_id + ":" + request["request_id"]
                state["deliveries"].setdefault(key, {
                    "subscription_id": sub_id, "event": event,
                    "attempts": 0, "next_attempt": now, "claim": "", "claim_until": 0,
                    "state": "pending",
                })

        await self._change(append)
        # The queue record is the recovery marker for a crash between these writes.
        current = await self.records.get(request["request_id"])
        if current and not current.get("message_event_enqueued"):
            await self.records.replace(
                request["request_id"], current, {**current, "message_event_enqueued": True},
            )
        for wake in tuple(_wakeups):
            wake.set()

    async def flush(self) -> None:
        # Repair an interrupted enqueue before attempting any deliveries.
        for request in await self.records.pending():
            if request.get("notify_message_event") and not request.get("message_event_enqueued"):
                await self.enqueue(request)

        now = time.time()
        claim = secrets.token_hex(16)

        def take(state: dict) -> list[tuple[str, dict, dict]]:
            expired = {
                key for key, sub in state["subscriptions"].items() if sub["expires_at"] <= now
            }
            for key in expired:
                state["subscriptions"].pop(key)
            for key in list(state["deliveries"]):
                if state["deliveries"][key]["subscription_id"] not in state["subscriptions"]:
                    state["deliveries"].pop(key)
            selected = []
            for key, delivery in state["deliveries"].items():
                if (
                    delivery["state"] != "pending" or delivery["next_attempt"] > now
                    or delivery.get("claim_until", 0) > now
                ):
                    continue
                delivery.update({"claim": claim, "claim_until": now + 60})
                selected.append((key, deepcopy(delivery),
                                 deepcopy(state["subscriptions"][delivery["subscription_id"]])))
                if len(selected) == 4:
                    break
            return selected

        for key, delivery, sub in await self._change(take) or []:
            if delivery["event"]["name"] == SENSORY_EVENT_NAME:
                request = await self.records.get(delivery["event"]["data"]["request_id"])
                if not request or request.get("state") != "pending" or (
                    request.get("deadline") is not None and request["deadline"] <= time.time()
                ):
                    def remove_stale(state: dict) -> None:
                        current = state["deliveries"].get(key)
                        if current and current.get("claim") == claim:
                            state["deliveries"].pop(key)

                    await self._change(remove_stale)
                    continue
            status = None
            allowed = True
            try:
                if self.authorized:
                    allowed = await self.authorized(sub)
                if allowed:
                    previous = sub.get("previous_secret") if sub.get("rotate_until", 0) > time.time() else None
                    status, _ = await self.post(
                        sub["url"], sub["secret"], delivery["event"]["eventId"],
                        delivery["event"], sub["id"], previous,
                    )
            except (ValueError, httpx.HTTPError, OSError, TimeoutError):
                pass

            def finish(state: dict) -> None:
                current = state["deliveries"].get(key)
                if not current or current.get("claim") != claim:
                    return
                if not allowed or status == 410:
                    state["subscriptions"].pop(sub["id"], None)
                    state["deliveries"] = {
                        k: v for k, v in state["deliveries"].items()
                        if v["subscription_id"] != sub["id"]
                    }
                elif status is not None and 200 <= status < 300:
                    state["deliveries"].pop(key)
                else:
                    attempts = current["attempts"] + 1
                    current.update({
                        "attempts": attempts, "claim": "", "claim_until": 0,
                        "next_attempt": time.time() + min(2 ** attempts, 300),
                        "state": "failed" if status == 413 or attempts >= MAX_ATTEMPTS else "pending",
                        "last_status": status,
                    })
                    # Retain a bounded diagnostic history without retrying terminal failures.
                    failed = [k for k, v in state["deliveries"].items() if v["state"] == "failed"]
                    for old in failed[:-64]:
                        state["deliveries"].pop(old)

            await self._change(finish)

    @asynccontextmanager
    async def running(self):
        wake = asyncio.Event()
        _wakeups.add(wake)

        async def worker() -> None:
            while True:
                wake.clear()
                try:
                    await self.flush()
                    state = await self.records.get(STATE_KEY) or {"deliveries": {}}
                except Exception:
                    # Callback URLs, signing secrets and message text must never enter logs.
                    logger.warning("Message event delivery deferred; durable outbox retained")
                    state = {"deliveries": {}}
                now = time.time()
                waits = [
                    max(0.1, max(item["next_attempt"], item.get("claim_until", 0)) - now)
                    for item in state["deliveries"].values() if item["state"] == "pending"
                ]
                try:
                    await asyncio.wait_for(wake.wait(), timeout=min([30.0, *waits]))
                except TimeoutError:
                    pass

        task = asyncio.create_task(worker(), name="axiom-message-events")
        try:
            yield self
        finally:
            _wakeups.discard(wake)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class EventDeliveryWorker:
    """Deliver only existing registries, keeping every outbox in its own Mind scope."""

    def __init__(self, storage: Any, provider: Any) -> None:
        from aicognitive_mind.host_runtime import RuntimeRecords

        self.storage, self.provider = storage, provider
        self.root = RuntimeRecords(storage.mind)
        self.after = ""

    async def authorized(self, mind_id: str, sub: dict) -> bool:
        from aicognitive_mind.commit import CommitConflict

        owner = sub.get("owner", {})
        if owner.get("issuer") != self.provider.base_url:
            return False
        client = await self.provider.get_client(owner.get("client_id", ""))
        if not client or (client.scope and self.provider.required_scope not in client.scope.split()):
            return False
        accounts = getattr(self.provider, "accounts", None)
        try:
            account = await accounts.resolve_subject(owner.get("subject", "")) if accounts else None
        except (CommitConflict, ValueError):
            return False
        if owner.get("subject") == self.provider.username:
            return account is None and mind_id == self.root.mind_id
        if account is None:
            return False
        target = self.root.mind_id if account.mind_id == "__legacy__" else account.mind_id
        return target == mind_id

    async def flush(self) -> None:
        from aicognitive_mind.host_runtime import RuntimeRecords
        from aicognitive_mind.persistence import scope_storage

        minds = await self.root.event_registry_mind_ids(self.after)
        self.after = minds[-1] if len(minds) == 128 else ""
        semaphore = asyncio.Semaphore(8)

        async def deliver(mind_id: str) -> None:
            async with semaphore:
                storage = self.storage if mind_id == self.root.mind_id else scope_storage(self.storage, mind_id)
                records = RuntimeRecords(storage.mind)

                async def allowed(sub: dict) -> bool:
                    return await self.authorized(mind_id, sub)

                await MessageEvents(records, authorized=allowed).flush()

        # A bad tenant callback must not stop other registered receivers.
        results = await asyncio.gather(
            *(deliver(mind_id) for mind_id in {self.root.mind_id, *minds}),
            return_exceptions=True,
        )
        if any(isinstance(result, BaseException) for result in results):
            logger.warning("Scoped event delivery deferred; durable outboxes retained")

    @asynccontextmanager
    async def running(self):
        wake = asyncio.Event()
        _wakeups.add(wake)

        async def run() -> None:
            while True:
                wake.clear()
                try:
                    await self.flush()
                except Exception:
                    logger.warning("Event registry delivery deferred")
                try:
                    await asyncio.wait_for(wake.wait(), timeout=0.1 if self.after else 2.0)
                except TimeoutError:
                    pass

        task = asyncio.create_task(run(), name="axiom-scoped-message-events")
        try:
            yield self
        finally:
            _wakeups.discard(wake)
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


def register_message_events(server: Any, provider: Any) -> None:
    from aicognitive_mind.account_mcp import authorized_state

    async def scoped(ctx: Any) -> tuple[Any, dict[str, str]]:
        state = await authorized_state(ctx.lifespan_context, provider)
        return state, event_owner(provider, state.hosts.records.mind_id)

    async def advertise(ctx: Any, call_next: Any) -> Any:
        result = await call_next(ctx)
        if ctx.method == "server/discover":
            try:
                await scoped(ctx)
            except MCPError:
                return result
            result = result.model_dump(by_alias=True, exclude_none=True) if isinstance(result, BaseModel) else dict(result)
            result["capabilities"] = {**result.get("capabilities", {}), "events": {}}
        return result

    server.middleware.append(advertise)

    async def list_events(ctx: Any, params: PaginatedRequestParams) -> dict:
        try:
            await scoped(ctx)
        except MCPError:
            return {"events": []}
        return {"events": [deepcopy(EVENT_DEFINITION), deepcopy(SENSORY_EVENT_DEFINITION)]}

    async def subscribe(ctx: Any, params: SubscribeParams) -> dict:
        state, owner = await scoped(ctx)
        records = state.hosts.records
        try:
            return await MessageEvents(records).subscribe(owner, params)
        except ValueError as exc:
            raise MCPError(code=-32602, message=str(exc)) from exc

    async def unsubscribe(ctx: Any, params: UnsubscribeParams) -> dict:
        state, owner = await scoped(ctx)
        records = state.hosts.records
        return await MessageEvents(records).unsubscribe(owner, params)

    # The draft Events methods are additive custom MCP methods in the 2.x SDK.
    server._lowlevel_server.add_request_handler("events/list", PaginatedRequestParams, list_events)
    server._lowlevel_server.add_request_handler("events/subscribe", SubscribeParams, subscribe)
    server._lowlevel_server.add_request_handler("events/unsubscribe", UnsubscribeParams, unsubscribe)
