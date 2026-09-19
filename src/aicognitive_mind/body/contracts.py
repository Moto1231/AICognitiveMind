from __future__ import annotations

from typing import Protocol

from aicognitive_mind.body.domain import DeviceStatus, ExpressionIntent, Percept


class VisionSensor(Protocol):
    async def status(self) -> DeviceStatus: ...

    async def observe(self) -> Percept: ...


class AudioSensor(Protocol):
    async def status(self) -> DeviceStatus: ...

    async def listen(self) -> Percept: ...


class VoiceOutput(Protocol):
    async def status(self) -> DeviceStatus: ...

    async def speak(self, intent: ExpressionIntent) -> None: ...


class AvatarOutput(Protocol):
    async def status(self) -> DeviceStatus: ...

    async def render(self, intent: ExpressionIntent) -> None: ...
