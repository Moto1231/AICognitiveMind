"""Durable per-Body FIFO queues shared across API workers."""

import asyncio
import hashlib
import math
import time
from contextvars import ContextVar
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from aicognitive_mind.body import DeviceStatus, ExpressionIntent, Percept
from aicognitive_mind.host_runtime import RuntimeRecords

body_session: ContextVar[str] = ContextVar("body_session", default="legacy")

ACTIVE_BODY_FRESH_SECONDS = 120


class BodyClientState(BaseModel):
    """Bounded browser-reported operational state, never media or identity."""

    model_config = ConfigDict(extra="forbid", strict=True)

    client_revision: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._:-]+$")
    hearing: bool | None = None
    voice: bool | None = None
    page_visible: bool | None = None
    page_focused: bool | None = None
    microphone_live: bool | None = None
    microphone_enabled: bool | None = None
    voice_mode: Literal["off", "connected_host", "realtime"] | None = None
    last_playback: Literal["idle", "started", "completed", "failed", "cancelled"] | None = None


class BodySessionHeartbeat(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    client_state: BodyClientState | None = None
    takeover: bool = False
    release: bool = False

    @model_validator(mode="after")
    def validate_ownership_action(self) -> "BodySessionHeartbeat":
        if self.takeover and self.release:
            raise ValueError("A Body session cannot take over and release ownership together")
        return self


async def active_body_status(records: RuntimeRecords, *, now: float | None = None) -> dict[str, Any] | None:
    """Expose only fresh client state from this Mind's active named Body."""
    active = await records.get("active_body_session")
    if not isinstance(active, dict):
        return None
    session = active.get("session_id")
    updated_at = active.get("updated_at")
    if (
        not isinstance(session, str) or not session or session == "legacy" or len(session) > 128
        or isinstance(updated_at, bool) or not isinstance(updated_at, (int, float))
        or not math.isfinite(updated_at)
    ):
        return None
    age = max(0.0, (time.time() if now is None else now) - updated_at)
    fresh = age <= ACTIVE_BODY_FRESH_SECONDS
    state = None
    if fresh and isinstance(active.get("client_state"), dict):
        try:
            state = BodyClientState.model_validate(active["client_state"]).model_dump(exclude_none=True)
        except ValidationError:
            # Older or corrupt records must not expose arbitrary stored fields.
            pass
    return {
        "fresh": fresh,
        "last_heartbeat_age_seconds": round(age, 3),
        "client_state": state,
        "client_state_source": "client_reported" if state is not None else None,
    }

_body_output_subscribers: dict[tuple[str, str, str], set[asyncio.Queue[None]]] = {}


def subscribe_body_output(
    session_id: str, modality: str, *, mind_scope: str = "legacy"
) -> asyncio.Queue[None]:
    subscriber: asyncio.Queue[None] = asyncio.Queue()
    _body_output_subscribers.setdefault((mind_scope, session_id, modality), set()).add(subscriber)
    return subscriber


def unsubscribe_body_output(
    session_id: str, modality: str, subscriber: asyncio.Queue[None], *, mind_scope: str = "legacy"
) -> None:
    subscribers = _body_output_subscribers.get((mind_scope, session_id, modality))
    if subscribers is None:
        return
    subscribers.discard(subscriber)
    if not subscribers:
        _body_output_subscribers.pop((mind_scope, session_id, modality), None)


def notify_body_output(session_id: str, modality: str, *, mind_scope: str = "legacy") -> None:
    for subscriber in tuple(_body_output_subscribers.get((mind_scope, session_id, modality), ())):
        subscriber.put_nowait(None)


class BodyQueue:
    def __init__(self, records: RuntimeRecords, modality: str, adapter: Any) -> None:
        self.records, self.modality, self.adapter = records, modality, adapter

    @property
    def output_scope(self) -> str:
        return str(getattr(self.records, "mind_id", "legacy"))

    def key(self) -> str:
        return (
            "body_" + hashlib.sha256(f"{body_session.get()}:{self.modality}".encode()).hexdigest()
        )

    async def change(self, append: dict | None = None) -> dict | None:
        key = self.key()
        for _ in range(10):
            before = await self.records.get(key)
            if before is None:
                try:
                    await self.records.create(key, {"items": [], "revision": 0})
                except Exception:
                    if await self.records.get(key) is None:
                        raise
                continue
            items = list(before["items"])
            result = None
            if append is not None:
                if len(items) >= 32:
                    raise RuntimeError(
                        "Body queue is full; consume pending items before submitting more"
                    )
                items.append(append)
            elif items:
                result = items.pop(0)
            else:
                return None
            if await self.records.replace(
                key, before, {"items": items, "revision": before["revision"] + 1}
            ):
                return result
        raise RuntimeError("Body queue is busy; retry the request")

    async def accept(self, **kwargs: Any) -> Percept:
        # Validation happens in an isolated adapter, never a shared transient slot.
        percept = type(self.adapter)().accept(**kwargs)
        await self.change(percept.model_dump(mode="json"))
        return percept

    async def observe(self) -> Percept:
        item = await self.change()
        if item is None:
            raise RuntimeError("No Body observation is ready for this session")
        return Percept.model_validate(item)

    async def listen(self) -> Percept:
        return await self.observe()

    async def speak(self, intent: ExpressionIntent) -> None:
        adapter = type(self.adapter)()
        await adapter.speak(intent)
        await self.change({**adapter.consume().model_dump(mode="json"), "delivery_id": uuid4().hex})
        notify_body_output(body_session.get(), self.modality, mind_scope=self.output_scope)

    async def render(self, intent: ExpressionIntent) -> None:
        adapter = type(self.adapter)()
        await adapter.render(intent)
        await self.change({**adapter.consume().model_dump(mode="json"), "delivery_id": uuid4().hex})

    async def deliver(self) -> tuple[ExpressionIntent | None, str | None]:
        queue = await self.records.get(self.key())
        if not queue or not queue["items"]:
            return None, None
        item = queue["items"][0]
        return ExpressionIntent.model_validate(item), item["delivery_id"]

    async def acknowledge(self, delivery_id: str) -> None:
        for _ in range(10):
            before = await self.records.get(self.key())
            if (
                not before
                or not before["items"]
                or before["items"][0].get("delivery_id") != delivery_id
            ):
                return  # Retry of an already acknowledged receipt is harmless.
            if await self.records.replace(
                self.key(),
                before,
                {"items": before["items"][1:], "revision": before["revision"] + 1},
            ):
                return
        raise RuntimeError("Body acknowledgment conflicted; retry it")

    async def consume(self) -> ExpressionIntent | None:
        item = await self.change()
        return ExpressionIntent.model_validate(item) if item else None

    async def status(self) -> DeviceStatus:
        return DeviceStatus(device=self.modality, available=True, detail="Session queue ready")
