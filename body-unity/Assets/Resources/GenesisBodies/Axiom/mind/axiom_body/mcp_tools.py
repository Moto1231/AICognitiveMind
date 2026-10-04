from __future__ import annotations

from typing import Any, Dict, Optional

from .service import AxiomBodyService


def register_body_tools(mcp: Any, body: AxiomBodyService) -> None:
    """Register the stable Body tools on an MCP/FastMCP server.

    The function only assumes the server exposes a `.tool()` decorator, which
    keeps this module decoupled from a specific MCP SDK version.
    """

    @mcp.tool()
    async def body_status() -> Dict[str, Any]:
        """Return the connected body's semantic state. Use before body actions when readiness is uncertain."""
        return await body.status()

    @mcp.tool()
    async def body_capabilities() -> Dict[str, Any]:
        """Return what the current body can do. Do not assume every embodiment supports every action."""
        return await body.capabilities()

    @mcp.tool()
    async def body_look_at(
        target_type: str,
        target_id: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        z: Optional[float] = None,
        intensity: float = 1.0,
    ) -> Dict[str, Any]:
        """Direct gaze/visual attention toward a semantic target or world position."""
        return await body.look_at(
            target_type,
            target_id,
            x=x,
            y=y,
            z=z,
            intensity=intensity,
        )

    @mcp.tool()
    async def body_expression(
        expression: str,
        intensity: float = 1.0,
        duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """Ask the current body to express a semantic facial/emotional expression."""
        return await body.expression(expression, intensity, duration_ms)

    @mcp.tool()
    async def body_gesture(
        gesture: str,
        intensity: float = 1.0,
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Ask the current body to perform a semantic gesture such as wave, nod, point, or acknowledge."""
        return await body.gesture(gesture, intensity, target)

    @mcp.tool()
    async def body_speak(
        text: str,
        emotion: str = "neutral",
        attention_target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Speak through the current body. The body owns TTS playback, lip sync, and animation."""
        return await body.speak(text, emotion, attention_target)

    @mcp.tool()
    async def body_listen(mode: str = "conversation") -> Dict[str, Any]:
        """Set hearing mode: conversation, ambient, command, or off."""
        return await body.listen(mode)

    @mcp.tool()
    async def body_observe(
        mode: str = "current_view",
        target: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Request visual observation. Sensor output should produce evidence artifacts, not just transient summaries."""
        return await body.observe(mode, target)

    @mcp.tool()
    async def body_posture(posture: str) -> Dict[str, Any]:
        """Set semantic posture such as stand, sit, rest, or sleep."""
        return await body.posture(posture)

    @mcp.tool()
    async def body_stop() -> Dict[str, Any]:
        """Stop voluntary body actions such as speaking or movement."""
        return await body.stop()
