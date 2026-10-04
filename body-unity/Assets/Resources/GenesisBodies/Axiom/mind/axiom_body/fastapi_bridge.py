from __future__ import annotations

from typing import Any

from .session import BodySessionManager


def install_body_websocket(app: Any, session: BodySessionManager, path: str = "/body/ws") -> None:
    """Install the Unity-to-Mind WebSocket bridge on an existing FastAPI app.

    FastAPI is imported lazily so the core Body package remains framework-independent.
    Unity connects outward to this endpoint; the Mind does not need an inbound port on
    the user's desktop body runtime.

    Note: because this module uses postponed annotations, the WebSocket annotation is
    attached explicitly before route registration. Otherwise a locally imported
    ``WebSocket`` can remain an unresolved string and FastAPI may reject the upgrade.
    """
    try:
        from fastapi import WebSocket, WebSocketDisconnect
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("FastAPI is required for install_body_websocket().") from exc

    async def axiom_body_socket(websocket) -> None:
        await websocket.accept()
        body_id = websocket.query_params.get("body_id", "axiom.reference.unity")

        async def send_json(message: dict[str, Any]) -> None:
            await websocket.send_json(message)

        connection_generation = session.attach(body_id, send_json)

        try:
            while True:
                message = await websocket.receive_json()
                await session.receive(message)
        except WebSocketDisconnect:
            pass
        finally:
            session.detach(connection_generation)

    axiom_body_socket.__annotations__["websocket"] = WebSocket
    axiom_body_socket.__annotations__["return"] = None
    app.websocket(path)(axiom_body_socket)
