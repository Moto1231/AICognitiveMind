from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field

from aicognitive_mind.body.domain import DeviceStatus, Percept, SensoryModality


JPEG_DATA_PREFIX = "data:image/jpeg;base64,"
MAX_JPEG_BYTES = 5 * 1024 * 1024


@dataclass(slots=True)
class BrowserVisionIngress:
    """Transient visual ingress fed by a browser-owned camera.

    The physical webcam remains attached to the user's device. A browser page,
    served by the remote Body runtime, uses getUserMedia() and sends one JPEG
    frame to this ingress. No local Python process or native camera dependency
    is required.
    """

    _latest: Percept | None = field(default=None, init=False, repr=False)

    async def status(self) -> DeviceStatus:
        return DeviceStatus(
            device="eyes",
            available=self._latest is not None,
            detail=(
                "browser camera observation ready"
                if self._latest is not None
                else "waiting for browser camera observation"
            ),
        )

    async def observe(self) -> Percept:
        if self._latest is None:
            raise RuntimeError("No browser camera observation is ready")
        percept = self._latest
        self._latest = None
        return percept

    def accept(
        self,
        *,
        image_data_url: str,
        width: int,
        height: int,
        source: str = "browser-camera",
    ) -> Percept:
        if width <= 0 or height <= 0:
            raise ValueError("Visual observation dimensions must be positive")
        if not image_data_url.startswith(JPEG_DATA_PREFIX):
            raise ValueError("Eyes V0.1 accepts JPEG data URLs only")

        encoded = image_data_url.removeprefix(JPEG_DATA_PREFIX)
        try:
            jpeg_bytes = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Visual observation contains invalid base64 JPEG data") from exc

        if not jpeg_bytes:
            raise ValueError("Visual observation contains an empty JPEG")
        if len(jpeg_bytes) > MAX_JPEG_BYTES:
            raise ValueError("Visual observation exceeds the 5 MB transient frame limit")

        percept = Percept(
            modality=SensoryModality.VISION,
            source=source,
            summary="Visual frame received from browser camera.",
            content_ref=image_data_url,
            metadata={
                "media_type": "image/jpeg",
                "encoding": "base64-data-uri",
                "width": width,
                "height": height,
                "byte_length": len(jpeg_bytes),
                "transient": True,
                "transport": "browser",
            },
        )
        self._latest = percept
        return percept
