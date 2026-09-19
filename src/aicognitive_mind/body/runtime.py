from __future__ import annotations

from dataclasses import dataclass

from aicognitive_mind.body.contracts import (
    AudioSensor,
    AvatarOutput,
    VisionSensor,
    VoiceOutput,
)
from aicognitive_mind.body.domain import (
    DeviceStatus,
    ExpressionIntent,
    ExpressionModality,
    Percept,
)


@dataclass(slots=True)
class BodyRuntime:
    """Coordinates replaceable Body faculties without owning Mind state."""

    vision: VisionSensor | None = None
    audio: AudioSensor | None = None
    voice: VoiceOutput | None = None
    avatar: AvatarOutput | None = None

    async def status(self) -> tuple[DeviceStatus, ...]:
        devices = [
            device
            for device in (self.vision, self.audio, self.voice, self.avatar)
            if device is not None
        ]
        return tuple([await device.status() for device in devices])

    async def see(self) -> Percept:
        if self.vision is None:
            raise RuntimeError("No eyes are attached")
        return await self.vision.observe()

    async def hear(self) -> Percept:
        if self.audio is None:
            raise RuntimeError("No ears are attached")
        return await self.audio.listen()

    async def speak(self, text: str) -> None:
        if self.voice is None:
            raise RuntimeError("No mouth is attached")
        await self.voice.speak(
            ExpressionIntent(
                modality=ExpressionModality.VOICE,
                text=text,
            )
        )

    async def present(self, text: str) -> None:
        if self.avatar is None:
            raise RuntimeError("No face is attached")
        await self.avatar.render(
            ExpressionIntent(
                modality=ExpressionModality.AVATAR,
                text=text,
            )
        )

    async def express(self, text: str) -> None:
        if self.voice is not None:
            await self.speak(text)
        if self.avatar is not None:
            await self.present(text)
