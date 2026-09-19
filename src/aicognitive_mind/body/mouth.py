from __future__ import annotations

from dataclasses import dataclass, field

from aicognitive_mind.body.domain import (
    DeviceStatus,
    ExpressionIntent,
    ExpressionModality,
)


@dataclass(slots=True)
class BrowserVoiceOutput:
    """Transient browser-facing output adapter for the Body's Mouth."""

    _pending: ExpressionIntent | None = field(default=None, init=False, repr=False)

    async def status(self) -> DeviceStatus:
        return DeviceStatus(
            device="mouth",
            available=True,
            detail="browser speech output ready",
        )

    async def speak(self, intent: ExpressionIntent) -> None:
        if intent.modality != ExpressionModality.VOICE:
            raise ValueError("Browser mouth accepts voice ExpressionIntent only")

        text = (intent.text or "").strip()
        if not text:
            raise ValueError("Voice ExpressionIntent requires text")

        metadata = dict(intent.metadata)

        rate = self._number(metadata.get("rate", 1.0), "rate")
        pitch = self._number(metadata.get("pitch", 1.0), "pitch")
        volume = self._number(metadata.get("volume", 1.0), "volume")

        if not 0.1 <= rate <= 10.0:
            raise ValueError("Voice rate must be between 0.1 and 10")
        if not 0.0 <= pitch <= 2.0:
            raise ValueError("Voice pitch must be between 0 and 2")
        if not 0.0 <= volume <= 1.0:
            raise ValueError("Voice volume must be between 0 and 1")

        voice_name = metadata.get("voice_name")
        if voice_name is not None:
            voice_name = str(voice_name).strip() or None

        metadata.update(
            {
                "rate": rate,
                "pitch": pitch,
                "volume": volume,
                "voice_name": voice_name,
                "transient": True,
                "transport": "browser-speech-synthesis",
            }
        )
        self._pending = intent.model_copy(update={"text": text, "metadata": metadata})

    def consume(self) -> ExpressionIntent | None:
        intent = self._pending
        self._pending = None
        return intent

    @staticmethod
    def _number(value: object, label: str) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Voice {label} must be numeric") from exc
