from __future__ import annotations

from typing import Any, Dict, Optional

from .models import BodyCommand
from .session import BodySessionManager, BodyUnavailableError


class AxiomBodyService:
    """Semantic Mind-side facade for a connected body."""

    def __init__(self, session: BodySessionManager) -> None:
        self.session = session

    async def _call(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            result = await self.session.send(BodyCommand(action=action, payload=payload or {}))
        except BodyUnavailableError as exc:
            return {
                "success": False,
                "code": "BODY_NOT_READY",
                "message": str(exc),
                "payload": {},
            }
        return result.to_dict()

    async def status(self) -> Dict[str, Any]:
        if not self.session.connected:
            return {
                "success": False,
                "code": "BODY_NOT_READY",
                "message": "No body is connected.",
                "payload": {"connected": False},
            }
        return await self._call("status")

    async def capabilities(self) -> Dict[str, Any]:
        return await self._call("capabilities")

    async def presence(self, presence: str, intensity: float = 1.0) -> Dict[str, Any]:
        return await self._call("presence", {"presence": presence, "intensity": intensity})

    async def look_at(
        self,
        target_type: str,
        target_id: Optional[str] = None,
        *,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        intensity: float = 1.0,
    ) -> Dict[str, Any]:
        target: Dict[str, Any] = {"type": target_type}
        if target_id is not None:
            target["id"] = target_id
        if target_type == "world_position":
            target["world_position"] = {"x": x or 0.0, "y": y or 0.0, "z": z or 0.0}
        return await self._call("look_at", {"target": target, "intensity": intensity})

    async def expression(
        self,
        expression: str,
        intensity: float = 1.0,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        return await self._call(
            "expression",
            {
                "expression": expression,
                "intensity": intensity,
                "duration_ms": duration_ms,
            },
        )

    async def gesture(
        self,
        gesture: str,
        intensity: float = 1.0,
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"gesture": gesture, "intensity": intensity}
        if target is not None:
            payload["target"] = target
        return await self._call("gesture", payload)

    async def speak(
        self,
        text: str,
        emotion: str = "neutral",
        attention_target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"text": text, "emotion": emotion}
        if attention_target is not None:
            payload["attention_target"] = attention_target
        return await self._call("speak", payload)

    async def listen(self, mode: str = "conversation") -> Dict[str, Any]:
        return await self._call("listen", {"mode": mode})

    async def observe(
        self,
        mode: str = "current_view",
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"mode": mode}
        if target is not None:
            payload["target"] = target
        return await self._call("observe", payload)

    async def posture(self, posture: str) -> Dict[str, Any]:
        return await self._call("posture", {"posture": posture})

    async def stop(self) -> Dict[str, Any]:
        return await self._call("stop")
