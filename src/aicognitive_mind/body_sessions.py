"""Durable per-Body FIFO queues shared across API workers."""

import hashlib
from contextvars import ContextVar
from typing import Any
from uuid import uuid4

from aicognitive_mind.body import DeviceStatus, ExpressionIntent, Percept
from aicognitive_mind.host_runtime import RuntimeRecords

body_session: ContextVar[str] = ContextVar("body_session", default="legacy")


class BodyQueue:
    def __init__(self, records: RuntimeRecords, modality: str, adapter: Any) -> None:
        self.records, self.modality, self.adapter = records, modality, adapter

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
