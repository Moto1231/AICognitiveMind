import unittest
from pathlib import Path

from aicognitive_mind.api import app
from aicognitive_mind.body import (
    BodyRuntime,
    BrowserAvatarOutput,
    ExpressionIntent,
    ExpressionModality,
)


class FaceV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_avatar_output_normalizes_expression_intent(self) -> None:
        face = BrowserAvatarOutput()

        await face.render(
            ExpressionIntent(
                modality=ExpressionModality.AVATAR,
                text="Smile.",
                metadata={"expression": "happy", "weight": 0.75},
            )
        )

        intent = face.consume()
        self.assertIsNotNone(intent)
        assert intent is not None
        self.assertEqual(intent.modality, ExpressionModality.AVATAR)
        self.assertEqual(intent.text, "Smile.")
        self.assertEqual(intent.metadata["expression"], "happy")
        self.assertEqual(intent.metadata["weight"], 0.75)
        self.assertIsNone(face.consume())

    async def test_body_runtime_preserves_face_expression_metadata(self) -> None:
        face = BrowserAvatarOutput()
        runtime = BodyRuntime(avatar=face)
        original = ExpressionIntent(
            modality=ExpressionModality.AVATAR,
            metadata={"expression": "happy", "weight": 1.0},
        )

        await runtime.present_intent(original)

        delivered = face.consume()
        self.assertIsNotNone(delivered)
        assert delivered is not None
        self.assertEqual(delivered.metadata["expression"], "happy")
        self.assertEqual(delivered.metadata["weight"], 1.0)

    async def test_face_rejects_non_avatar_intent(self) -> None:
        face = BrowserAvatarOutput()
        runtime = BodyRuntime(avatar=face)

        with self.assertRaisesRegex(ValueError, "avatar ExpressionIntent"):
            await runtime.present_intent(
                ExpressionIntent(
                    modality=ExpressionModality.VOICE,
                    text="Not a face command.",
                )
            )

    async def test_face_rejects_invalid_expression_weight(self) -> None:
        face = BrowserAvatarOutput()

        with self.assertRaisesRegex(ValueError, "between 0 and 1"):
            await face.render(
                ExpressionIntent(
                    modality=ExpressionModality.AVATAR,
                    metadata={"expression": "happy", "weight": 1.5},
                )
            )

    async def test_face_status_reports_browser_vrm_adapter(self) -> None:
        face = BrowserAvatarOutput()

        status = await face.status()

        self.assertEqual(status.device, "face")
        self.assertTrue(status.available)
        self.assertIn("VRM", status.detail or "")

    def test_face_routes_and_vrm_runtime_exist(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/body/face", paths)
        self.assertIn("/v1/body/face/expression", paths)
        self.assertIn("/v1/body/face/status", paths)
        self.assertIn("/v1/body/face/next", paths)

        markup = Path("src/aicognitive_mind/static/face.html").read_text(encoding="utf-8")
        self.assertIn("@pixiv/three-vrm@3.5.5", markup)
        self.assertIn("three@0.180.0", markup)
        self.assertIn("VRMLoaderPlugin", markup)
        self.assertIn("expressionManager", markup)
        self.assertIn('sendExpression("neutral")', markup)
        self.assertIn('sendExpression("happy")', markup)
        self.assertIn("/v1/body/face/expression", markup)
        self.assertIn("/v1/body/face/next", markup)
        self.assertIn("FACE RECEIVED EXPRESSION INTENT", markup)


if __name__ == "__main__":
    unittest.main()
