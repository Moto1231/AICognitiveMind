import asyncio
import unittest

from axiom_body.models import BodyCommand
from axiom_body.service import AxiomBodyService
from axiom_body.session import BodySessionManager


class BodyAdapterTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.session = BodySessionManager(command_timeout=0.5)
        self.service = AxiomBodyService(self.session)
        self.sent = []

        async def send_json(message):
            self.sent.append(message)
            await self.session.receive(
                {
                    "protocol": "axiom.body/0.1",
                    "message_type": "result",
                    "command_id": message["command_id"],
                    "body_id": "axiom.reference.unity",
                    "success": True,
                    "code": "OK",
                    "payload": {"echo_action": message["action"]},
                }
            )

        self.session.attach("axiom.reference.unity", send_json)

    async def test_speak_maps_to_semantic_command(self):
        result = await self.service.speak("Hello", emotion="happy")
        self.assertTrue(result["success"])
        self.assertEqual(self.sent[-1]["action"], "speak")
        self.assertEqual(self.sent[-1]["payload"]["text"], "Hello")
        self.assertEqual(self.sent[-1]["payload"]["emotion"], "happy")

    async def test_expression_maps_to_semantic_command(self):
        result = await self.service.expression("curious", 0.65, 2500)
        self.assertTrue(result["success"])
        self.assertEqual(self.sent[-1]["action"], "expression")
        self.assertEqual(self.sent[-1]["payload"]["duration_ms"], 2500)

    async def test_not_connected_is_semantic_error(self):
        session = BodySessionManager(command_timeout=0.01)
        service = AxiomBodyService(session)
        result = await service.status()
        self.assertFalse(result["success"])
        self.assertEqual(result["code"], "BODY_NOT_READY")

    async def test_old_disconnect_cannot_detach_replacement_connection(self):
        session = BodySessionManager(command_timeout=0.01)

        async def first_send(message):
            pass

        async def second_send(message):
            pass

        first_generation = session.attach("axiom.reference.unity", first_send)
        second_generation = session.attach("axiom.reference.unity", second_send)

        session.detach(first_generation)
        self.assertTrue(session.connected)

        session.detach(second_generation)
        self.assertFalse(session.connected)


if __name__ == "__main__":
    unittest.main()
