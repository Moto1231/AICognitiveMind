"""Body-independent device media, using the existing authenticated Axiom tasks.

The Codex adapter opens an ephemeral, non-reasoning MCP transport context. It
never starts a model turn, resumes the user's chat, or reads chat transcripts.
"""

from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path
from typing import Any


class MediaError(RuntimeError):
    """A device, transport, or configured task failed."""


def codex_executable() -> str:
    executable = shutil.which("codex")
    if executable:
        return executable
    root = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
    candidates = list(root.glob("*/codex.exe"))
    if candidates:
        return str(max(candidates, key=lambda path: path.stat().st_mtime))
    raise MediaError("Codex executable not found; supply --codex explicitly.")


class CodexTaskClient:
    """Reuse Codex's MCP OAuth storage without copying credentials to this client."""

    def __init__(self, executable: str | None = None, server: str = "axiom") -> None:
        self.server = server
        self.messages: queue.Queue[Any] = queue.Queue()
        self.request_id = 0
        self.process = subprocess.Popen(
            [executable or codex_executable(), "app-server", "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        threading.Thread(target=self._read, daemon=True).start()
        try:
            self.call(
                "initialize",
                {
                    "clientInfo": {"name": "axiom_remote_media", "version": "0.1"},
                    "capabilities": {"experimentalApi": True},
                },
            )
            self._send({"method": "initialized"})
            context = self.call("thread/start", {"ephemeral": True})
            if context["thread"].get("ephemeral") is not True:
                raise MediaError("The media transport must be ephemeral.")
            self.context_id = context["thread"]["id"]
        except Exception:
            self.close()
            raise

    def _read(self) -> None:
        assert self.process.stdout is not None
        try:
            for line in self.process.stdout:
                try:
                    self.messages.put(json.loads(line))
                except ValueError:
                    continue
        finally:
            self.messages.put(None)

    def _send(self, message: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def call(self, method: str, params: dict[str, Any], timeout: float = 120) -> Any:
        self.request_id += 1
        request_id = self.request_id
        self._send({"id": request_id, "method": method, "params": params})
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise MediaError(f"Timed out waiting for {method}.")
            try:
                message = self.messages.get(timeout=remaining)
            except queue.Empty as exc:
                raise MediaError(f"Timed out waiting for {method}.") from exc
            if message is None:
                raise MediaError("The authenticated media transport closed.")
            if "method" in message and "id" in message:
                self._send(
                    {
                        "id": message["id"],
                        "error": {
                            "code": -32601,
                            "message": "Interaction requires the user's host client.",
                        },
                    }
                )
                raise MediaError("Sign-in or approval is required in the host client.")
            if message.get("id") != request_id:
                continue
            if "error" in message:
                raise MediaError(message["error"].get("message", "Host request failed."))
            return message["result"]

    def execute(self, task: str, operation: str, **arguments: Any) -> dict[str, Any]:
        response = self.call(
            "mcpServer/tool/call",
            {
                "threadId": self.context_id,
                "server": self.server,
                "tool": "execute_task",
                "arguments": {"task": task, "operation": operation, **arguments},
            },
        )
        if response.get("isError"):
            detail = next(
                (
                    item.get("text", "")
                    for item in response.get("content", [])
                    if item.get("type") == "text"
                ),
                "Axiom task failed.",
            )
            raise MediaError(detail)
        result = response.get("structuredContent")
        if not isinstance(result, dict):
            for item in response.get("content", []):
                if item.get("type") == "text":
                    try:
                        result = json.loads(item["text"])
                        break
                    except ValueError:
                        continue
        if not isinstance(result, dict):
            raise MediaError("Axiom returned no structured task result.")
        if result.get("status") not in {"completed", "not_configured"}:
            raise MediaError(result.get("error", "The configured task failed."))
        return result

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def __enter__(self) -> CodexTaskClient:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def camera_frame(path: Path, device: int = 0) -> dict[str, Any]:
    import cv2

    capture = cv2.VideoCapture(device, cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY)
    try:
        if not capture.isOpened():
            raise MediaError("Camera could not open; check device selection, use, and permission.")
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        frame = None
        for _ in range(5):
            ok, frame = capture.read()
            if not ok:
                raise MediaError("Camera opened but did not return a frame.")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(path), frame):
            raise MediaError("Camera image could not be saved.")
        return {"status": "captured", "path": str(path.resolve()), "device": device}
    finally:
        capture.release()


def microphone_audio(path: Path, seconds: float = 5, device: int | None = None) -> None:
    import sounddevice as sd

    if not 0 < seconds <= 30:
        raise MediaError("Microphone capture must be between 0 and 30 seconds.")
    try:
        samples = sd.rec(
            int(seconds * 16000), samplerate=16000, channels=1, dtype="int16", device=device
        )
        sd.wait()
    finally:
        sd.stop()
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(16000)
        audio.writeframes(samples.tobytes())


def windows_voice(text: str, path: Path, preferences: dict[str, Any]) -> None:
    if os.name != "nt":
        raise MediaError("No Axiom voice configured; Windows fallback requires Windows.")
    script = r"""
$ErrorActionPreference = 'Stop'
$mediaPayload = [Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$mediaSynth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $available = @($mediaSynth.GetInstalledVoices() | ForEach-Object { $_.VoiceInfo.Name })
    if ($available -contains $mediaPayload.voice_name) {
        $mediaSynth.SelectVoice($mediaPayload.voice_name)
    }
    $speechRate = [int](10 * [Math]::Log($mediaPayload.rate, 2))
    $mediaSynth.Rate = [Math]::Max(-10, [Math]::Min(10, $speechRate))
    $mediaSynth.Volume = [int]($mediaPayload.volume * 100)
    $mediaSynth.SetOutputToWaveFile($mediaPayload.path)
    $mediaSynth.Speak([string]$mediaPayload.text)
} finally { $mediaSynth.Dispose() }
"""
    subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        input=json.dumps(
            {
                "text": text,
                "path": str(path.resolve()),
                "voice_name": preferences.get("voice_name", ""),
                "rate": preferences.get("rate", 1),
                "volume": preferences.get("volume", 1),
            }
        ),
        text=True,
        capture_output=True,
        check=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


def play_audio(path: Path) -> None:
    if os.name != "nt":
        raise MediaError("Use --no-play and your client's audio player on this platform.")
    send = ctypes.windll.winmm.mciSendStringW
    alias = "axiomMedia" + str(os.getpid())
    kind = "waveaudio" if path.suffix == ".wav" else "mpegvideo"
    if send(f'open "{path.resolve()}" type {kind} alias {alias}', None, 0, None):
        raise MediaError("Windows could not open the generated audio.")
    try:
        if send(f"play {alias} wait", None, 0, None):
            raise MediaError("Windows could not play the generated audio.")
    finally:
        send(f"close {alias}", None, 0, None)


def speak(client: Any, text: str, path: Path, play: bool = True) -> dict[str, Any]:
    response = client.execute("audio_voice", "synthesize_voice", text=text)
    path.parent.mkdir(parents=True, exist_ok=True)
    if response["status"] == "not_configured":
        path = path.with_suffix(".wav")
        windows_voice(text, path, response.get("result", {}))
        route = "windows_default"
    else:
        result = response.get("result", {})
        media_type = result.get("media_type")
        if media_type not in {"audio/mpeg", "audio/wav", "audio/x-wav"}:
            raise MediaError("The voice task returned an unsupported audio type.")
        audio = base64.b64decode(result.get("audio_base64", ""), validate=True)
        if not audio or len(audio) > 20_000_000:
            raise MediaError("The voice task returned empty or oversized audio.")
        path = path.with_suffix(".wav" if media_type in {"audio/wav", "audio/x-wav"} else ".mp3")
        path.write_bytes(audio)
        route = "configured_audio_voice"
    if play:
        play_audio(path)
    return {
        "status": "playback_returned" if play else "saved",
        "route": route,
        "path": str(path.resolve()),
    }


def transcribe(client: Any, path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) > 10_000_000:
        raise MediaError("Audio input exceeds the 10 MB client limit.")
    return client.execute(
        "audio",
        "transcribe",
        filename=path.name,
        media_type="audio/wav",
        audio_base64=base64.b64encode(data).decode("ascii"),
    )


def describe(client: Any, path: Path, prompt: str) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) > 10_000_000:
        raise MediaError("Image input exceeds the 10 MB client limit.")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    url = f"data:{mime};base64," + base64.b64encode(data).decode("ascii")
    return client.execute(
        "vision",
        "chat",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": url}},
                ],
            }
        ],
    )


def reply_for_speech(text: str) -> str:
    text = re.sub(r"<oai-mem-citation>.*?</oai-mem-citation>", "", text, flags=re.S)
    text = re.sub(r"```.*?```", " Code is included in the written reply. ", text, flags=re.S)
    text = re.sub(r"\[([^\]]+)\]\([^\n]*?\)", r"\1", text)
    text = re.sub(r"(?m)^\s*[#>*-]+\s*", "", text)
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def stop_hook(args: argparse.Namespace) -> None:
    """At most one attempt per completed turn; never continue the agent turn."""
    try:
        payload = json.load(sys.stdin)
        if payload.get("session_id") != args.session_id:
            return
        if payload.get("hook_event_name") != "Stop":
            return
        text = reply_for_speech(payload.get("last_assistant_message") or "")
        turn_id = payload.get("turn_id")
        if not text or not isinstance(turn_id, str) or not turn_id:
            return
        key = hashlib.sha256((args.session_id + "\0" + turn_id).encode()).hexdigest()
        args.state_dir.mkdir(parents=True, exist_ok=True)
        marker = args.state_dir / (key + ".json")
        try:
            with marker.open("x", encoding="utf-8") as stream:
                json.dump({"status": "started"}, stream)
        except FileExistsError:
            return
        try:
            with CodexTaskClient(args.codex, args.server) as client:
                result = speak(client, text, args.state_dir / (key + ".mp3"))
        except Exception as exc:
            result = {"status": "failed", "error_type": type(exc).__name__}
            print("Axiom voice failed; inspect the remote media connection.", file=sys.stderr)
        marker.write_text(json.dumps(result), encoding="utf-8")
    except Exception:
        print("Axiom voice hook could not process its input.", file=sys.stderr)
    finally:
        print("{}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", help="Codex executable; uses its existing MCP OAuth connection")
    parser.add_argument("--server", default="axiom", help="Configured MCP server name")
    commands = parser.add_subparsers(dest="command", required=True)
    camera = commands.add_parser("camera", help="Capture one frame without Body")
    camera.add_argument("path", type=Path)
    camera.add_argument("--device", type=int, default=0)
    record = commands.add_parser("record", help="Record a bounded microphone WAV")
    record.add_argument("path", type=Path)
    record.add_argument("--seconds", type=float, default=5)
    record.add_argument("--device", type=int)
    voice = commands.add_parser("speak", help="Existing Audio/Voice task -> local playback")
    voice.add_argument("text")
    voice.add_argument("path", type=Path)
    voice.add_argument("--no-play", action="store_true")
    hearing = commands.add_parser("transcribe", help="Existing Audio/Transcription task")
    hearing.add_argument("path", type=Path)
    vision = commands.add_parser("describe", help="Existing Vision task")
    vision.add_argument("path", type=Path)
    vision.add_argument("--prompt", default="Describe what is visible in this image.")
    commands.add_parser("devices", help="List microphone and speaker devices")
    hook = commands.add_parser("hook", help="Speak completed replies in one selected chat")
    hook.add_argument("--session-id", required=True)
    hook.add_argument("--state-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "hook":
        stop_hook(args)
        return
    try:
        if args.command == "camera":
            result = camera_frame(args.path, args.device)
        elif args.command == "record":
            microphone_audio(args.path, args.seconds, args.device)
            result = {"status": "recorded", "path": str(args.path.resolve())}
        elif args.command == "devices":
            import sounddevice as sd

            result = {"devices": list(sd.query_devices()), "defaults": list(sd.default.device)}
        else:
            with CodexTaskClient(args.codex, args.server) as client:
                if args.command == "speak":
                    result = speak(client, args.text, args.path, not args.no_play)
                elif args.command == "transcribe":
                    result = transcribe(client, args.path)
                else:
                    result = describe(client, args.path, args.prompt)
        print(json.dumps(result))
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}), file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
