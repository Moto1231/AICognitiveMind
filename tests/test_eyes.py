import base64
import unittest
from pathlib import Path

from aicognitive_mind.api import app
from aicognitive_mind.body import BodyRuntime, BrowserVisionIngress, SensoryModality


def jpeg_data_url(payload: bytes = b"jpeg-bytes") -> str:
    return "data:image/jpeg;base64," + base64.b64encode(payload).decode("ascii")


class EyesV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_browser_frame_becomes_transient_visual_percept(self) -> None:
        eyes = BrowserVisionIngress()

        percept = eyes.accept(
            image_data_url=jpeg_data_url(),
            width=640,
            height=480,
        )

        self.assertEqual(percept.modality, SensoryModality.VISION)
        self.assertEqual(percept.source, "browser-camera")
        self.assertEqual(percept.summary, "Visual frame received from browser camera.")
        self.assertEqual(percept.metadata["width"], 640)
        self.assertEqual(percept.metadata["height"], 480)
        self.assertEqual(percept.metadata["byte_length"], len(b"jpeg-bytes"))
        self.assertTrue(percept.metadata["transient"])
        self.assertEqual(percept.metadata["transport"], "browser")

    async def test_body_see_consumes_browser_frame_once(self) -> None:
        eyes = BrowserVisionIngress()
        runtime = BodyRuntime(vision=eyes)
        eyes.accept(
            image_data_url=jpeg_data_url(),
            width=320,
            height=240,
        )

        ready = await eyes.status()
        self.assertTrue(ready.available)

        seen = await runtime.see()
        self.assertEqual(seen.source, "browser-camera")

        waiting = await eyes.status()
        self.assertFalse(waiting.available)
        with self.assertRaisesRegex(RuntimeError, "No browser camera observation is ready"):
            await runtime.see()

    async def test_invalid_browser_frame_is_rejected(self) -> None:
        eyes = BrowserVisionIngress()

        with self.assertRaisesRegex(ValueError, "JPEG data URLs only"):
            eyes.accept(
                image_data_url="data:image/png;base64,AAAA",
                width=10,
                height=10,
            )

        with self.assertRaisesRegex(ValueError, "invalid base64"):
            eyes.accept(
                image_data_url="data:image/jpeg;base64,not-valid-***",
                width=10,
                height=10,
            )

        with self.assertRaisesRegex(ValueError, "dimensions must be positive"):
            eyes.accept(
                image_data_url=jpeg_data_url(),
                width=0,
                height=10,
            )

    def test_browser_eyes_routes_and_page_exist(self) -> None:
        paths = {route.path for route in app.routes}
        self.assertIn("/body/eyes", paths)
        self.assertIn("/v1/body/eyes/observe", paths)
        self.assertIn("/v1/body/eyes/status", paths)
        self.assertIn("/v1/body/eyes/see", paths)

        page = Path("src/aicognitive_mind/static/eyes.html").read_text(encoding="utf-8")
        self.assertIn("navigator.mediaDevices.getUserMedia", page)
        self.assertIn("/v1/body/eyes/observe", page)
        self.assertIn("/v1/body/eyes/see", page)
        self.assertIn("BODY CAN SEE", page)


if __name__ == "__main__":
    unittest.main()
