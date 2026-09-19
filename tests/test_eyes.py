import base64
import unittest
from unittest.mock import patch

from aicognitive_mind.body.domain import SensoryModality
from aicognitive_mind.body.eyes import OpenCvVisionSensor


class FakeEncoded:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def tobytes(self) -> bytes:
        return self._payload


class FakeFrame:
    shape = (480, 640, 3)


class FakeCapture:
    def __init__(self, *, opened: bool = True, reads_ok: bool = True) -> None:
        self.opened = opened
        self.reads_ok = reads_ok
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        if self.reads_ok:
            return True, FakeFrame()
        return False, None

    def release(self) -> None:
        self.released = True


class FakeCv2:
    CAP_DSHOW = 700
    IMWRITE_JPEG_QUALITY = 1

    def __init__(self, capture: FakeCapture) -> None:
        self.capture = capture
        self.video_capture_calls = []

    def VideoCapture(self, *args):
        self.video_capture_calls.append(args)
        return self.capture

    def imencode(self, extension, frame, args):
        self.last_encode = (extension, frame, args)
        return True, FakeEncoded(b"jpeg-bytes")


class EyesV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_status_reports_available_camera(self) -> None:
        capture = FakeCapture()
        cv2 = FakeCv2(capture)
        eyes = OpenCvVisionSensor(camera_index=0)

        with patch("aicognitive_mind.body.eyes._load_cv2", return_value=cv2):
            status = await eyes.status()

        self.assertTrue(status.available)
        self.assertEqual(status.device, "eyes")
        self.assertIn("camera:0", status.detail or "")
        self.assertTrue(capture.released)

    async def test_observe_returns_transient_in_memory_jpeg(self) -> None:
        capture = FakeCapture()
        cv2 = FakeCv2(capture)
        eyes = OpenCvVisionSensor(
            camera_index=0,
            warmup_frames=2,
            jpeg_quality=87,
        )

        with patch("aicognitive_mind.body.eyes._load_cv2", return_value=cv2):
            percept = await eyes.observe()

        self.assertEqual(percept.modality, SensoryModality.VISION)
        self.assertEqual(percept.source, "camera:0")
        self.assertEqual(percept.summary, "Visual frame captured.")
        self.assertTrue(
            (percept.content_ref or "").startswith("data:image/jpeg;base64,")
        )
        encoded = (percept.content_ref or "").split(",", 1)[1]
        self.assertEqual(base64.b64decode(encoded), b"jpeg-bytes")
        self.assertEqual(percept.metadata["width"], 640)
        self.assertEqual(percept.metadata["height"], 480)
        self.assertEqual(percept.metadata["channels"], 3)
        self.assertEqual(percept.metadata["jpeg_quality"], 87)
        self.assertTrue(percept.metadata["transient"])
        self.assertTrue(capture.released)

    async def test_unavailable_camera_is_reported_without_raising(self) -> None:
        capture = FakeCapture(opened=False)
        cv2 = FakeCv2(capture)
        eyes = OpenCvVisionSensor(camera_index=0)

        with patch("aicognitive_mind.body.eyes._load_cv2", return_value=cv2):
            status = await eyes.status()

        self.assertFalse(status.available)
        self.assertIn("could not be opened", status.detail or "")

    async def test_observe_fails_explicitly_when_frame_cannot_be_read(self) -> None:
        capture = FakeCapture(reads_ok=False)
        cv2 = FakeCv2(capture)
        eyes = OpenCvVisionSensor(camera_index=0, warmup_frames=0)

        with (
            patch("aicognitive_mind.body.eyes._load_cv2", return_value=cv2),
            self.assertRaisesRegex(RuntimeError, "could not capture a frame"),
        ):
            await eyes.observe()

        self.assertTrue(capture.released)

    def test_invalid_configuration_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OpenCvVisionSensor(camera_index=-1)
        with self.assertRaises(ValueError):
            OpenCvVisionSensor(warmup_frames=-1)
        with self.assertRaises(ValueError):
            OpenCvVisionSensor(jpeg_quality=0)
        with self.assertRaises(ValueError):
            OpenCvVisionSensor(jpeg_quality=101)


if __name__ == "__main__":
    unittest.main()
