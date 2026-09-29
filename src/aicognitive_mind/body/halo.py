from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aicognitive_mind.body.domain import DeviceStatus, Percept, SensoryModality


@dataclass(slots=True)
class HaloIngress:
    """Transient ingress for Brilliant Labs Halo sensory messages.

    Transport is intentionally outside this adapter. During development the
    source can be halo-emulator; on Android it can be the Brilliant Flutter
    SDK over BLE. The Mind sees the same Body contract in either case.
    """

    _vision: Percept | None = field(default=None, init=False, repr=False)
    _audio: Percept | None = field(default=None, init=False, repr=False)

    async def vision_status(self) -> DeviceStatus:
        return DeviceStatus(
            device="eyes",
            available=self._vision is not None,
            detail="Halo visual observation ready" if self._vision else "waiting for Halo photo",
        )

    async def audio_status(self) -> DeviceStatus:
        return DeviceStatus(
            device="ears",
            available=self._audio is not None,
            detail="Halo audio observation ready" if self._audio else "waiting for Halo audio",
        )

    def accept_photo(self, *, content_ref: str, metadata: dict[str, Any] | None = None) -> Percept:
        if not content_ref:
            raise ValueError("Halo photo requires a content reference")
        percept = Percept(
            modality=SensoryModality.VISION,
            source="brilliant-halo-camera",
            summary="Visual observation received from Brilliant Labs Halo.",
            content_ref=content_ref,
            metadata={"transient": True, "transport": "halo", **(metadata or {})},
        )
        self._vision = percept
        return percept

    def accept_audio(self, *, content_ref: str, metadata: dict[str, Any] | None = None) -> Percept:
        if not content_ref:
            raise ValueError("Halo audio requires a content reference")
        percept = Percept(
            modality=SensoryModality.AUDIO,
            source="brilliant-halo-microphone",
            summary="Audio observation received from Brilliant Labs Halo.",
            content_ref=content_ref,
            metadata={"transient": True, "transport": "halo", **(metadata or {})},
        )
        self._audio = percept
        return percept

    async def observe(self) -> Percept:
        if self._vision is None:
            raise RuntimeError("No Halo visual observation is ready")
        percept, self._vision = self._vision, None
        return percept

    async def listen(self) -> Percept:
        if self._audio is None:
            raise RuntimeError("No Halo audio observation is ready")
        percept, self._audio = self._audio, None
        return percept
