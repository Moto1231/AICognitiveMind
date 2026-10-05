import unittest
from pathlib import Path


class VoicePackV01Tests(unittest.TestCase):
    def test_voice_pack_runtime_exports_persistence_and_application(self) -> None:
        source = Path("src/aicognitive_mind/static/voice_pack.js").read_text(
            encoding="utf-8"
        )

        self.assertIn("DEFAULT_VOICE_PACK", source)
        self.assertIn("loadSavedVoicePack", source)
        self.assertIn("saveVoicePack", source)
        self.assertIn("clearSavedVoicePack", source)
        self.assertIn("resolveVoice", source)
        self.assertIn("applyVoicePack", source)
        self.assertIn("aicognitive_mind.voice_pack.v1", source)

    def test_avatar_editor_surface_is_removed(self) -> None:
        self.assertFalse(Path("src/aicognitive_mind/static/avatar_editor.html").exists())

    def test_live_body_uses_saved_or_shared_voice_pack_for_mouth_output(self) -> None:
        markup = Path("src/aicognitive_mind/static/live_body.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('from "/static/voice_pack.js"', markup)
        self.assertIn("loadSavedVoicePack()", markup)
        self.assertIn("sharedVoicePack = loadSavedVoicePack()", markup)
        self.assertIn("applyVoicePack(utterance, sharedVoicePack, voices)", markup)
        self.assertIn("/v1/body/voice/settings", markup)
        self.assertIn("SpeechSynthesisUtterance", markup)


if __name__ == "__main__":
    unittest.main()
