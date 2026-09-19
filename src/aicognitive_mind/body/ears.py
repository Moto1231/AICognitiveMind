from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field

from aicognitive_mind.body.domain import DeviceStatus, Percept, SensoryModality


MAX_AUDIO_BYTES = 8 * 1024 * 1024
MAX_DURATION_MS = 30_000
ALLOWED_AUDIO_MEDIA_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mp4",
    "audio/mpeg",
}


@dataclass(slots=True)
class BrowserAudioIngress:
    """Transient audio ingress fed by a browser-owned microphone."""

    _latest: Percept | None = field(default=None, init=False, repr=False)

    async def status(self) -> DeviceStatus:
        return DeviceStatus(
            device="ears",
            available=self._latest is not None,
            detail=(
                "browser microphone observation ready"
                if self._latest is not None
                else "waiting for browser microphone observation"
            ),
        )

    async def listen(self) -> Percept:
        if self._latest is None:
            raise RuntimeError("No browser microphone observation is ready")
        percept = self._latest
        self._latest = None
        return percept

    def accept(
        self,
        *,
        audio_data_url: str,
        duration_ms: int,
        source: str = "browser-microphone",
    ) -> Percept:
        if duration_ms <= 0:
            raise ValueError("Audio observation duration must be positive")
        if duration_ms > MAX_DURATION_MS:
            raise ValueError("Audio observation exceeds the 30 second transient limit")

        media_type, encoded = self._parse_audio_data_url(audio_data_url)
        try:
            audio_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Audio observation contains invalid base64 data") from exc

        if not audio_bytes:
            raise ValueError("Audio observation is empty")
        if len(audio_bytes) > MAX_AUDIO_BYTES:
            raise ValueError("Audio observation exceeds the 8 MB transient audio limit")

        percept = Percept(
            modality=SensoryModality.AUDIO,
            source=source,
            summary="Audio clip received from browser microphone.",
            content_ref=audio_data_url,
            metadata={
                "media_type": media_type,
                "encoding": "base64-data-uri",
                "duration_ms": duration_ms,
                "byte_length": len(audio_bytes),
                "transient": True,
                "transport": "browser",
            },
        )
        self._latest = percept
        return percept

    @staticmethod
    def _parse_audio_data_url(value: str) -> tuple[str, str]:
        if not value.startswith("data:") or "," not in value:
            raise ValueError("Ears V0.1 accepts base64 audio data URLs only")

        header, encoded = value.split(",", 1)
        if not header.endswith(";base64"):
            raise ValueError("Ears V0.1 accepts base64 audio data URLs only")

        descriptor = header.removeprefix("data:").removesuffix(";base64")
        media_type = descriptor.split(";", 1)[0].lower()
        if media_type not in ALLOWED_AUDIO_MEDIA_TYPES:
            raise ValueError(f"Ears V0.1 does not accept media type {media_type or 'unknown'}")
        return media_type, encoded
