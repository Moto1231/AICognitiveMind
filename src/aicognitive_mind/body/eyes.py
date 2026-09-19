from __future__ import annotations

import asyncio
import base64
import os
from typing import Any

from aicognitive_mind.body.domain import DeviceStatus, Percept, SensoryModality


def _load_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "Eyes V0.1 requires OpenCV. Install the optional dependency with: "
            "pip install -e '.[eyes]'"
        ) from exc
    return cv2


class OpenCvVisionSensor:
    """One-frame webcam eyes adapter.

    Raw camera frames remain transient. A successful observation returns an
    in-memory JPEG data URI in Percept.content_ref and does not write to disk.
    """

    def __init__(
        self,
        camera_index: int = 0,
        *,
        warmup_frames: int = 3,
        jpeg_quality: int = 90,
    ) -> None:
        if camera_index < 0:
            raise ValueError("camera_index must be zero or greater")
        if warmup_frames < 0:
            raise ValueError("warmup_frames must be zero or greater")
        if not 1 <= jpeg_quality <= 100:
            raise ValueError("jpeg_quality must be between 1 and 100")
        self.camera_index = camera_index
        self.warmup_frames = warmup_frames
        self.jpeg_quality = jpeg_quality

    async def status(self) -> DeviceStatus:
        return await asyncio.to_thread(self._status_sync)

    async def observe(self) -> Percept:
        return await asyncio.to_thread(self._observe_sync)

    def _open_capture(self, cv2: Any) -> Any:
        if os.name == "nt" and hasattr(cv2, "CAP_DSHOW"):
            capture = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if capture.isOpened():
                return capture
            capture.release()
        return cv2.VideoCapture(self.camera_index)

    def _status_sync(self) -> DeviceStatus:
        try:
            cv2 = _load_cv2()
            capture = self._open_capture(cv2)
            try:
                available = bool(capture.isOpened())
            finally:
                capture.release()
            return DeviceStatus(
                device="eyes",
                available=available,
                detail=(
                    f"camera:{self.camera_index} ready"
                    if available
                    else f"camera:{self.camera_index} could not be opened"
                ),
            )
        except Exception as exc:
            return DeviceStatus(
                device="eyes",
                available=False,
                detail=str(exc),
            )

    def _observe_sync(self) -> Percept:
        cv2 = _load_cv2()
        capture = self._open_capture(cv2)
        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"Eyes V0.1 cannot open camera:{self.camera_index}. "
                "Check that a webcam is connected and Windows camera access is enabled."
            )

        try:
            frame = None
            successful = False
            attempts = max(1, self.warmup_frames + 1)
            for _ in range(attempts):
                successful, candidate = capture.read()
                if successful:
                    frame = candidate
            if not successful or frame is None:
                raise RuntimeError(
                    f"Eyes V0.1 opened camera:{self.camera_index} but could not capture a frame."
                )

            encode_args: list[int] = []
            if hasattr(cv2, "IMWRITE_JPEG_QUALITY"):
                encode_args = [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
            encoded_ok, encoded = cv2.imencode(".jpg", frame, encode_args)
            if not encoded_ok:
                raise RuntimeError("Eyes V0.1 captured a frame but JPEG encoding failed.")

            jpeg_bytes = encoded.tobytes()
            content_ref = (
                "data:image/jpeg;base64,"
                + base64.b64encode(jpeg_bytes).decode("ascii")
            )
            height = int(frame.shape[0])
            width = int(frame.shape[1])
            channels = int(frame.shape[2]) if len(frame.shape) > 2 else 1

            return Percept(
                modality=SensoryModality.VISION,
                source=f"camera:{self.camera_index}",
                summary="Visual frame captured.",
                content_ref=content_ref,
                metadata={
                    "media_type": "image/jpeg",
                    "encoding": "base64-data-uri",
                    "width": width,
                    "height": height,
                    "channels": channels,
                    "jpeg_quality": self.jpeg_quality,
                    "transient": True,
                },
            )
        finally:
            capture.release()
