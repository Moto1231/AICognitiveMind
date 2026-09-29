import unittest

from aicognitive_mind.body.domain import SensoryModality
from aicognitive_mind.body.halo import HaloIngress


class HaloIngressTests(unittest.IsolatedAsyncioTestCase):
    async def test_photo_is_transient_vision_percept(self) -> None:
        halo = HaloIngress()
        halo.accept_photo(content_ref="artifact://halo/photo/1", metadata={"width": 640})

        status = await halo.vision_status()
        seen = await halo.observe()

        self.assertTrue(status.available)
        self.assertEqual(seen.modality, SensoryModality.VISION)
        self.assertEqual(seen.source, "brilliant-halo-camera")
        self.assertTrue(seen.metadata["transient"])
        self.assertEqual(seen.metadata["width"], 640)

        with self.assertRaisesRegex(RuntimeError, "No Halo visual observation"):
            await halo.observe()

    async def test_audio_is_transient_audio_percept(self) -> None:
        halo = HaloIngress()
        halo.accept_audio(content_ref="artifact://halo/audio/1", metadata={"codec": "pcm"})

        heard = await halo.listen()

        self.assertEqual(heard.modality, SensoryModality.AUDIO)
        self.assertEqual(heard.source, "brilliant-halo-microphone")
        self.assertEqual(heard.metadata["codec"], "pcm")
        self.assertTrue(heard.metadata["transient"])


if __name__ == "__main__":
    unittest.main()
