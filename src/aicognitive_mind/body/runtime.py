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


def configured_voice_intent(
    text: str,
    settings: dict[str, object] | None = None,
    *,
    rate: float | None = None,
    pitch: float | None = None,
    volume: float | None = None,
    voice_name: str | None = None,
) -> ExpressionIntent:
    """Build the canonical voice intent using shared settings plus explicit overrides."""
    speech_text = text.strip()
    if not speech_text:
        raise ValueError("Speech text cannot be empty")
    if len(speech_text) > 4000:
        raise ValueError("Speech text cannot exceed 4000 characters")
    configured = settings or {}
    metadata = {
        "rate": configured.get("rate", 1.0) if rate is None else rate,
        "pitch": configured.get("pitch", 1.0) if pitch is None else pitch,
        "volume": configured.get("volume", 1.0) if volume is None else volume,
        "voice_name": (
            (configured.get("voiceName") or None)
            if voice_name is None
            else voice_name
        ),
        # Queue acceptance is not proof that browser playback completed.
        "delivery_status": "queued",
    }
    return ExpressionIntent(
        modality=ExpressionModality.VOICE,
        text=speech_text,
        metadata=metadata,
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

    async def speak_intent(self, intent: ExpressionIntent) -> None:
        if self.voice is None:
            raise RuntimeError("No mouth is attached")
        if intent.modality != ExpressionModality.VOICE:
            raise ValueError("Mouth requires a voice ExpressionIntent")
        await self.voice.speak(intent)

    async def speak(self, text: str) -> None:
        await self.speak_intent(
            ExpressionIntent(
                modality=ExpressionModality.VOICE,
                text=text,
            )
        )

    async def present_intent(self, intent: ExpressionIntent) -> None:
        if self.avatar is None:
            raise RuntimeError("No face is attached")
        if intent.modality != ExpressionModality.AVATAR:
            raise ValueError("Face requires an avatar ExpressionIntent")
        await self.avatar.render(intent)

    async def present(self, text: str) -> None:
        await self.present_intent(
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
