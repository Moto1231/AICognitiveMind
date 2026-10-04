"""Runnable Mind-side round-trip demo using a simulated Unity body.

Run from the mind directory:
    python -m examples.roundtrip_demo

This proves the live network path:
AxiomBodyService -> BodySessionManager -> FastAPI WebSocket -> body -> result.
"""

import asyncio
import json

import uvicorn
import websockets
from fastapi import FastAPI

from axiom_body.fastapi_bridge import install_body_websocket
from axiom_body.service import AxiomBodyService
from axiom_body.session import BodySessionManager

PORT = 8765


async def simulated_unity_body():
    uri = f"ws://127.0.0.1:{PORT}/body/ws?body_id=axiom.reference.unity"
    async with websockets.connect(uri) as websocket:
        print("[Unity simulator] connected")
        async for raw in websocket:
            command = json.loads(raw)
            print("[Unity simulator] <-", command["action"], command["payload"])
            await websocket.send(
                json.dumps(
                    {
                        "protocol": "axiom.body/0.1",
                        "message_type": "result",
                        "command_id": command["command_id"],
                        "body_id": "axiom.reference.unity",
                        "success": True,
                        "code": "OK",
                        "payload": {
                            "executed_action": command["action"],
                            "received_payload": command["payload"],
                        },
                    }
                )
            )


async def main():
    session = BodySessionManager(command_timeout=2.0)
    body = AxiomBodyService(session)

    app = FastAPI()
    install_body_websocket(app, session)

    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", lifespan="off")
    )
    server_task = asyncio.create_task(server.serve())

    while not server.started:
        await asyncio.sleep(0.01)

    unity_task = asyncio.create_task(simulated_unity_body())
    while not session.connected:
        await asyncio.sleep(0.01)

    print("[Mind] body connected")
    result = await body.speak("Hello from Axiom Mind", emotion="curious")
    print("[Mind] -> result:", json.dumps(result, indent=2))

    unity_task.cancel()
    try:
        await unity_task
    except asyncio.CancelledError:
        pass

    server.should_exit = True
    await server_task


if __name__ == "__main__":
    asyncio.run(main())
