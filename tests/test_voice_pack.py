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

    def test_avatar_editor_exposes_voice_pack_controls(self) -> None:
        markup = Path("src/aicognitive_mind/static/avatar_editor.html").read_text(
            encoding="utf-8"
        )

        self.assertIn("Voice Pack", markup)
        self.assertIn('id="voiceSelect"', markup)
        self.assertIn('id="voiceRate"', markup)
        self.assertIn('id="voicePitch"', markup)
        self.assertIn('id="voiceVolume"', markup)
        self.assertIn('id="previewVoicePack"', markup)
        self.assertIn('id="saveVoicePack"', markup)
        self.assertIn('id="resetVoicePack"', markup)
        self.assertIn('from "/static/voice_pack.js"', markup)
        self.assertIn("speechSynthesis.getVoices()", markup)

    def test_live_body_uses_saved_voice_pack_for_mouth_output(self) -> None:
        markup = Path("src/aicognitive_mind/static/live_body.html").read_text(
            encoding="utf-8"
        )

        self.assertIn('from "/static/voice_pack.js"', markup)
        self.assertIn("loadSavedVoicePack()", markup)
        self.assertIn(
            "applyVoicePack(utterance, loadSavedVoicePack(), voices)",
            markup,
        )
        self.assertIn("SpeechSynthesisUtterance", markup)


if __name__ == "__main__":
    unittest.main()
