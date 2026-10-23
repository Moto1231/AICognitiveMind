import base64
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from aicognitive_mind.remote_media import (
    CodexTaskClient,
    MediaError,
    camera_frame,
    describe,
    microphone_audio,
    speak,
    stop_hook,
    transcribe,
)


class RemoteMediaTests(unittest.TestCase):
    def test_configured_voice_uses_existing_task_and_saves_returned_audio(self):
        client = Mock()
        client.execute.return_value = {
            "status": "completed",
            "result": {
                "audio_base64": base64.b64encode(b"mp3 data").decode(),
                "media_type": "audio/mpeg",
            },
        }
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("aicognitive_mind.remote_media.windows_voice") as windows,
        ):
            path = Path(folder) / "reply.mp3"
            result = speak(client, "Hello", path, play=False)
            self.assertEqual(path.read_bytes(), b"mp3 data")
            self.assertEqual(result["route"], "configured_audio_voice")
            windows.assert_not_called()
        client.execute.assert_called_once_with("audio_voice", "synthesize_voice", text="Hello")

    def test_explicit_unconfigured_result_uses_windows_and_correct_file_type(self):
        client = Mock()
        client.execute.return_value = {"status": "not_configured", "result": {"rate": 1.2}}
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("aicognitive_mind.remote_media.windows_voice") as windows,
        ):
            result = speak(client, "Hello", Path(folder) / "reply.mp3", play=False)
        self.assertEqual(Path(result["path"]).suffix, ".wav")
        self.assertEqual(result["route"], "windows_default")
        self.assertEqual(windows.call_args.args[2], {"rate": 1.2})

    def test_auth_or_provider_error_does_not_use_windows(self):
        client = Mock()
        client.execute.side_effect = MediaError("Provider request rejected")
        with patch("aicognitive_mind.remote_media.windows_voice") as windows:
            with self.assertRaisesRegex(MediaError, "rejected"):
                speak(client, "Hello", Path("unused.mp3"), play=False)
            windows.assert_not_called()

    def test_transcription_is_audio_in_and_vision_is_image_in(self):
        client = Mock()
        with tempfile.TemporaryDirectory() as folder:
            audio = Path(folder) / "input.wav"
            audio.write_bytes(b"wav input")
            transcribe(client, audio)
            client.execute.assert_called_with(
                "audio",
                "transcribe",
                filename="input.wav",
                media_type="audio/wav",
                audio_base64=base64.b64encode(b"wav input").decode(),
            )
            image = Path(folder) / "camera.jpg"
            image.write_bytes(b"jpeg input")
            describe(client, image, "What is visible?")
        args, kwargs = client.execute.call_args
        self.assertEqual(args, ("vision", "chat"))
        self.assertTrue(
            kwargs["messages"][0]["content"][1]["image_url"]["url"].startswith(
                "data:image/jpeg;base64,"
            )
        )

    def test_camera_device_is_released_even_if_capture_fails(self):
        capture = Mock()
        capture.isOpened.return_value = False
        cv = SimpleNamespace(VideoCapture=Mock(return_value=capture), CAP_DSHOW=1, CAP_ANY=0)
        with (
            patch.dict("sys.modules", {"cv2": cv}),
            self.assertRaisesRegex(MediaError, "Camera could not open"),
        ):
            camera_frame(Path("unused.jpg"))
        capture.release.assert_called_once()

    def test_microphone_records_bounded_pcm_and_releases_device(self):
        import wave

        sd = Mock()
        sd.rec.return_value.tobytes.return_value = b"\x00\x00" * 160
        with (
            tempfile.TemporaryDirectory() as folder,
            patch.dict("sys.modules", {"sounddevice": sd}),
        ):
            path = Path(folder) / "mic.wav"
            microphone_audio(path, 0.01)
            with wave.open(str(path)) as audio:
                self.assertEqual(audio.getframerate(), 16000)
                self.assertEqual(audio.getnchannels(), 1)
                self.assertEqual(audio.getsampwidth(), 2)
            with self.assertRaises(MediaError):
                microphone_audio(path, 31)
        sd.stop.assert_called_once()

    def test_transport_uses_ephemeral_context_and_never_starts_reasoning(self):
        response_lines = [
            {"id": 1, "result": {}},
            {"id": 2, "result": {"thread": {"id": "transport-only", "ephemeral": True}}},
            {
                "id": 3,
                "result": {
                    "content": [],
                    "structuredContent": {
                        "status": "completed",
                        "result": "transcript",
                    },
                },
            },
        ]
        process = Mock()
        process.stdin = io.StringIO()
        process.stdout = io.StringIO("\n".join(json.dumps(row) for row in response_lines))
        process.poll.return_value = None
        with (
            patch("aicognitive_mind.remote_media.subprocess.Popen", return_value=process),
            CodexTaskClient("codex-test") as client,
        ):
            result = client.execute("audio", "transcribe", filename="test.wav")
        self.assertEqual(result["result"], "transcript")
        sent = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
        self.assertEqual(
            [row["method"] for row in sent],
            [
                "initialize",
                "initialized",
                "thread/start",
                "mcpServer/tool/call",
            ],
        )
        self.assertTrue(sent[2]["params"]["ephemeral"])
        self.assertEqual(sent[3]["params"]["server"], "axiom")
        self.assertEqual(sent[3]["params"]["tool"], "execute_task")
        process.terminate.assert_called_once()

    def test_reply_hook_is_scoped_deduplicated_and_returns_json(self):
        payload = {
            "hook_event_name": "Stop",
            "session_id": "selected-chat",
            "turn_id": "turn-1",
            "last_assistant_message": "**Hello**",
        }
        with (
            tempfile.TemporaryDirectory() as folder,
            patch("aicognitive_mind.remote_media.CodexTaskClient") as client,
            patch("aicognitive_mind.remote_media.speak") as speech,
        ):
            speech.return_value = {"status": "playback_returned"}
            args = SimpleNamespace(
                session_id="selected-chat", state_dir=Path(folder), codex=None, server="axiom"
            )
            for session in ["other-chat", "selected-chat", "selected-chat"]:
                payload["session_id"] = session
                output = io.StringIO()
                with (
                    patch("sys.stdin", io.StringIO(json.dumps(payload))),
                    contextlib.redirect_stdout(output),
                ):
                    stop_hook(args)
                self.assertEqual(json.loads(output.getvalue()), {})
            client.assert_called_once()
            speech.assert_called_once()
            self.assertEqual(speech.call_args.args[1], "Hello")


if __name__ == "__main__":
    unittest.main()
