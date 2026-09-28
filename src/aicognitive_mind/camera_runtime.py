"""Storage-backed Body camera requests shared by MCP and the browser Body."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import uuid4

from aicognitive_mind.host_runtime import RuntimeRecords


class CameraRequestRuntime:
    def __init__(self, mind: Any, timeout: float = 45) -> None:
        self.records = RuntimeRecords(mind)
        self.timeout = timeout

    async def request(self, seconds: int = 3) -> dict[str, Any]:
        if not 1 <= seconds <= 30:
            raise ValueError("Camera duration must be between 1 and 30 seconds")
        before = await self.records.get("camera_request")
        if before and before.get("state") == "pending" and before.get("deadline", 0) > time.time():
            raise RuntimeError("A camera request is already pending")
        request = {
            "kind": "camera_request",
            "request_id": uuid4().hex,
            "state": "pending",
            "seconds": seconds,
            "created": time.time(),
            "deadline": time.time() + self.timeout,
            "result": {},
        }
        if before:
            if not await self.records.replace("camera_request", before, request):
                raise RuntimeError("Camera request changed concurrently")
        else:
            await self.records.create("camera_request", request)

        while time.time() < request["deadline"]:
            current = await self.records.get("camera_request")
            if current and current.get("request_id") == request["request_id"] and current.get("state") == "complete":
                return current["result"]
            await asyncio.sleep(0.2)
        raise TimeoutError("The Body did not complete the camera request before its deadline")

    async def next(self) -> dict[str, Any] | None:
        current = await self.records.get("camera_request")
        if not current or current.get("state") != "pending":
            return None
        if current.get("deadline", 0) <= time.time():
            return None
        return {
            "request_id": current["request_id"],
            "seconds": current["seconds"],
            "deadline": current["deadline"],
        }

    async def complete(
        self, request_id: str, image_data_url: str, width: int, height: int
    ) -> dict[str, Any]:
        current = await self.records.get("camera_request")
        if not current or current.get("request_id") != request_id or current.get("state") != "pending":
            raise RuntimeError("Camera request is absent, expired, or already completed")
        if not image_data_url.startswith("data:image/jpeg;base64,"):
            raise ValueError("Camera result must be a JPEG data URL")
        if width <= 0 or height <= 0:
            raise ValueError("Camera dimensions must be positive")
        result = {
            "image_data_url": image_data_url,
            "width": width,
            "height": height,
            "source": "browser-camera-mcp",
        }
        if not await self.records.replace(
            "camera_request", current, {**current, "state": "complete", "result": result}
        ):
            raise RuntimeError("Camera request changed concurrently")
        return {"completed": True, "request_id": request_id}
