from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Dict, Optional

from .models import BodyCommand, BodyEvent, BodyResult

SendJson = Callable[[Dict[str, Any]], Awaitable[None]]
EventHandler = Callable[[BodyEvent], Awaitable[None]]


class BodyUnavailableError(RuntimeError):
    pass


class BodySessionManager:
    """Tracks the currently connected embodiment and correlates commands/results.

    The transport itself is intentionally external. A FastAPI WebSocket bridge,
    local IPC bridge, or future robot adapter can all attach a send_json callable.
    """

    def __init__(self, *, command_timeout: float = 10.0) -> None:
        self._send_json: Optional[SendJson] = None
        self._connected_body_id: Optional[str] = None
        self._pending: Dict[str, asyncio.Future[BodyResult]] = {}
        self._event_handlers: list[EventHandler] = []
        self.command_timeout = command_timeout
        self._connection_generation = 0

    @property
    def connected(self) -> bool:
        return self._send_json is not None

    @property
    def connected_body_id(self) -> Optional[str]:
        return self._connected_body_id

    def attach(self, body_id: str, send_json: SendJson) -> int:
        self._connection_generation += 1
        self._connected_body_id = body_id
        self._send_json = send_json
        return self._connection_generation

    def detach(self, connection_generation: int | None = None) -> None:
        # If a previous socket finishes after a replacement connection has already
        # attached, it must not tear down the new body session.
        if (
            connection_generation is not None
            and connection_generation != self._connection_generation
        ):
            return

        self._send_json = None
        self._connected_body_id = None
        for future in self._pending.values():
            if not future.done():
                future.set_exception(BodyUnavailableError("Body disconnected."))
        self._pending.clear()

    def on_event(self, handler: EventHandler) -> None:
        self._event_handlers.append(handler)

    async def send(self, command: BodyCommand) -> BodyResult:
        if self._send_json is None:
            raise BodyUnavailableError("No body is connected.")

        if self._connected_body_id:
            command.body_id = self._connected_body_id

        loop = asyncio.get_running_loop()
        future: asyncio.Future[BodyResult] = loop.create_future()
        self._pending[command.command_id] = future

        try:
            await self._send_json(command.to_wire())
            return await asyncio.wait_for(future, timeout=self.command_timeout)
        except asyncio.TimeoutError as exc:
            raise BodyUnavailableError(
                f"Body did not respond to {command.action!r} within {self.command_timeout:g}s."
            ) from exc
        finally:
            self._pending.pop(command.command_id, None)

    async def receive(self, message: Dict[str, Any]) -> None:
        message_type = str(message.get("message_type", ""))

        if message_type == "result":
            result = BodyResult.from_wire(message)
            future = self._pending.get(result.command_id)
            if future is not None and not future.done():
                future.set_result(result)
            return

        if message_type == "event":
            event = BodyEvent.from_wire(message)
            for handler in list(self._event_handlers):
                await handler(event)
            return

        # Unknown wire messages are intentionally ignored at this layer.
