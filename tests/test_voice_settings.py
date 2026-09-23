import unittest

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.storage import InMemoryMindStore
from aicognitive_mind.voice_settings import VoiceSettings


class VoiceSettingsTests(unittest.IsolatedAsyncioTestCase):
    async def test_settings_survive_new_store_instance_and_reject_stale_edit(self):
        mind = InMemoryMindStore()
        first = VoiceSettings(mind)
        second = VoiceSettings(mind)

        self.assertEqual((await first.read())["revision"], 0)
        updated = await first.update(expected_revision=0, rate=1.2, volume=0.7)
        self.assertEqual(updated["revision"], 1)
        self.assertEqual((await second.read())["rate"], 1.2)
        with self.assertRaises(CommitConflict):
            await second.update(expected_revision=0, pitch=1.1)

    async def test_rejects_out_of_range_values(self):
        store = VoiceSettings(InMemoryMindStore())
        with self.assertRaises(ValueError):
            await store.update(expected_revision=0, rate=float("nan"))
        with self.assertRaises(ValueError):
            await store.update(expected_revision=0, volume=2)


if __name__ == "__main__":
    unittest.main()
