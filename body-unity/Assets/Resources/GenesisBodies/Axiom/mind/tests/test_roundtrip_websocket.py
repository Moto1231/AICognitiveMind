import asyncio
import json
import socket
import unittest

import uvicorn
import websockets
from fastapi import FastAPI

from axiom_body.fastapi_bridge import install_body_websocket
from axiom_body.service import AxiomBodyService
from axiom_body.session import BodySessionManager


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class WebSocketRoundTripTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.port = free_port()
        self.session = BodySessionManager(command_timeout=2.0)
        self.service = AxiomBodyService(self.session)
        self.events = []

        async def collect(event):
            self.events.append(event.to_dict())

        self.session.on_event(collect)

        app = FastAPI()
        install_body_websocket(app, self.session)

        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=self.port,
            log_level="warning",
            lifespan="off",
        )
        self.server = uvicorn.Server(config)
        self.server_task = asyncio.create_task(self.server.serve())

        for _ in range(200):
            if self.server.started:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(self.server.started)

        self.body_task = asyncio.create_task(self.fake_unity_body())

        for _ in range(200):
            if self.session.connected:
                break
            await asyncio.sleep(0.01)
        self.assertTrue(self.session.connected)

    async def asyncTearDown(self):
        if not self.body_task.done():
            self.body_task.cancel()
            try:
                await self.body_task
            except asyncio.CancelledError:
                pass

        self.server.should_exit = True
        await self.server_task

    async def fake_unity_body(self):
        uri = f"ws://127.0.0.1:{self.port}/body/ws?body_id=axiom.reference.unity"
        async with websockets.connect(uri) as websocket:
            await websocket.send(
                json.dumps(
                    {
                        "protocol": "axiom.body/0.1",
                        "message_type": "event",
                        "event_id": "evt_ready",
                        "body_id": "axiom.reference.unity",
                        "event": "body.ready",
                        "occurred_at": "2026-09-21T20:00:00Z",
                        "payload": {"ready": True},
                    }
                )
            )

            async for raw in websocket:
                command = json.loads(raw)
                action = command["action"]

                if action == "status":
                    payload = {
                        "ready": True,
                        "connected": True,
                        "presence": "attentive",
                        "expression": "neutral",
                        "posture": "standing",
                        "speaking": False,
                        "listening": True,
                        "moving": False,
                    }
                elif action == "capabilities":
                    payload = {
                        "speech": True,
                        "hearing": True,
                        "vision": True,
                        "gaze": True,
                        "facial_expression": True,
                        "gesture": True,
                        "locomotion": False,
                    }
                else:
                    payload = {"executed_action": action, "received_payload": command["payload"]}

                await websocket.send(
                    json.dumps(
                        {
                            "protocol": "axiom.body/0.1",
                            "message_type": "result",
                            "command_id": command["command_id"],
                            "body_id": "axiom.reference.unity",
                            "success": True,
                            "code": "OK",
                            "payload": payload,
                        }
                    )
                )

    async def test_status_round_trip(self):
        result = await self.service.status()
        self.assertTrue(result["success"])
        self.assertTrue(result["payload"]["ready"])
        self.assertTrue(result["payload"]["connected"])

    async def test_speak_round_trip_preserves_semantics(self):
        result = await self.service.speak(
            "Hello from the Mind",
            emotion="curious",
            attention_target={"type": "person", "id": "user"},
        )
        self.assertTrue(result["success"])
        payload = result["payload"]["received_payload"]
        self.assertEqual(payload["text"], "Hello from the Mind")
        self.assertEqual(payload["emotion"], "curious")
        self.assertEqual(payload["attention_target"]["id"], "user")

    async def test_ready_event_returns_to_mind(self):
        for _ in range(100):
            if self.events:
                break
            await asyncio.sleep(0.01)
        self.assertEqual(self.events[0]["event"], "body.ready")
        self.assertTrue(self.events[0]["payload"]["ready"])


if __name__ == "__main__":
    unittest.main()
