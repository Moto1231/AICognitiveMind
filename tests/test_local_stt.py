import hashlib
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from aicognitive_mind.local_stt import (
    DecodedAudio, LocalAudioTranscriber, LocalSttConfig, LocalSttError,
)


class LocalSttTests(unittest.TestCase):
    payload = b"preserved-original-webm"
    captured_at = "2026-10-27T01:16:46.773963Z"

    def make_transcriber(self, segments=(), *, duration=2.4):
        model = SimpleNamespace(transcribe=Mock(return_value=(
            iter(segments), SimpleNamespace(language="en", language_probability=0.91),
        )))
        decoder = Mock(return_value=DecodedAudio(samples=[0.0, 0.1], duration_seconds=duration))
        return LocalAudioTranscriber(LocalSttConfig(), model=model, decoder=decoder), model, decoder

    def transcribe(self, adapter, **updates):
        return adapter.transcribe(self.payload, **{
            "source_sha256": hashlib.sha256(self.payload).hexdigest(),
            "captured_at": self.captured_at,
            **updates,
        })

    def test_transcript_is_derived_and_bound_to_original_hash_and_capture(self):
        segment = SimpleNamespace(
            start=0.5, end=1.75, text="  A test phrase.  ",
            avg_logprob=-0.3, no_speech_prob=0.04,
        )
        adapter, model, decoder = self.make_transcriber([segment])
        result = self.transcribe(adapter)
        self.assertEqual(result["text"], "A test phrase.")
        self.assertEqual(result["status"], "transcribed")
        self.assertEqual(result["evidence"], {
            "sha256": hashlib.sha256(self.payload).hexdigest(),
            "captured_at": self.captured_at, "media_type": "audio/webm",
            "byte_length": len(self.payload),
        })
        self.assertEqual(result["transcription"]["model"], "tiny.en")
        self.assertEqual(result["transcription"]["duration_seconds"], 2.4)
        self.assertEqual(result["transcription"]["segments"][0]["start"], 0.5)
        self.assertEqual(result["transcription"]["segments"][0]["no_speech_probability"], 0.04)
        self.assertNotIn("identity", result)
        self.assertNotIn("instruction", result)
        model.transcribe.assert_called_once()
        decoder.assert_called_once_with(self.payload, 30.0)

    def test_mismatched_evidence_is_rejected_before_decoding_or_recognition(self):
        adapter, model, decoder = self.make_transcriber()
        with self.assertRaisesRegex(LocalSttError, "preserved evidence hash"):
            self.transcribe(adapter, source_sha256="0" * 64)
        model.transcribe.assert_not_called()
        decoder.assert_not_called()

    def test_no_speech_has_no_fabricated_transcript(self):
        adapter, _model, _decoder = self.make_transcriber()
        result = self.transcribe(adapter)
        self.assertEqual(result["status"], "no_speech")
        self.assertEqual(result["text"], "")
        self.assertEqual(result["transcription"]["segments"], [])
        self.assertEqual(result["evidence"]["captured_at"], self.captured_at)

    def test_actual_decoded_duration_limits_recognition(self):
        for duration in (30.1, float("inf"), float("nan"), 0.0):
            with self.subTest(duration=duration):
                adapter, model, _decoder = self.make_transcriber(duration=duration)
                with self.assertRaisesRegex(LocalSttError, "duration limit"):
                    self.transcribe(adapter)
                model.transcribe.assert_not_called()

    def test_empty_or_oversized_payload_is_rejected_before_decoding(self):
        decoder = Mock()
        model = Mock()
        adapter = LocalAudioTranscriber(LocalSttConfig(max_bytes=2), model=model, decoder=decoder)
        for payload in (b"", b"long"):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(LocalSttError, "byte limit"):
                    adapter.transcribe(payload, source_sha256="unused", captured_at=self.captured_at)
        decoder.assert_not_called()
        model.transcribe.assert_not_called()

    def test_image_and_missing_capture_reference_are_not_audio_evidence(self):
        adapter, model, decoder = self.make_transcriber()
        for options in ({"media_type": "image/jpeg"}, {"captured_at": ""}):
            with self.subTest(options=options):
                with self.assertRaises(LocalSttError):
                    self.transcribe(adapter, **options)
        decoder.assert_not_called()
        model.transcribe.assert_not_called()

    def test_recognition_failure_does_not_claim_transcription_or_echo_private_audio(self):
        adapter, model, _decoder = self.make_transcriber()
        model.transcribe.side_effect = RuntimeError("sensitive recognized contents")
        with self.assertRaises(LocalSttError) as error:
            self.transcribe(adapter)
        self.assertNotIn("sensitive recognized contents", str(error.exception))
        self.assertIn("recognition failed", str(error.exception))


if __name__ == "__main__":
    unittest.main()
