"""Gemini's native speech protocol and browser-playable, typed audio bytes."""

from __future__ import annotations

import base64
import binascii
import io
import re
import wave
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx


class GeminiAudioError(RuntimeError):
    """The configured Gemini endpoint could not produce valid speech audio."""


class SynthesizedAudio(bytes):
    """Keep the existing bytes contract while retaining the actual media type."""

    media_type: str

    def __new__(cls, payload: bytes, *, media_type: str):
        result = super().__new__(cls, payload)
        result.media_type = media_type
        return result


def uses_gemini_speech(*, base_url: str, provider_name: str, model: str) -> bool:
    provider = provider_name.casefold()
    return (
        urlsplit(base_url).hostname == "generativelanguage.googleapis.com"
        or "gemini" in provider
        or model.removeprefix("models/").casefold().startswith("gemini-")
    )


def gemini_interactions_url(base_url: str) -> str:
    """Convert the saved Gemini/OpenAI base without replacing custom origins."""
    address = urlsplit(base_url)
    path = address.path.rstrip("/")
    for suffix in ("/chat/completions", "/audio/speech"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    if path.endswith("/openai"):
        path = path[:-len("/openai")]
    if path.endswith("/models"):
        path = path[:-len("/models")]
    if not path and address.hostname == "generativelanguage.googleapis.com":
        path = "/v1beta"
    if not path.endswith("/interactions"):
        path += "/interactions"
    return urlunsplit(address._replace(path=path, fragment=""))


def _playable_audio(block: dict[str, Any]) -> SynthesizedAudio:
    try:
        encoded = block["data"]
        if not isinstance(encoded, str):
            raise ValueError("Audio data is not base64 text")
        audio = base64.b64decode(encoded, validate=True)
        if not audio:
            raise ValueError("Empty audio")
        mime = block.get("mime_type", "audio/wav")
        if not isinstance(mime, str):
            raise ValueError("Invalid media type")
        kind = mime.split(";", 1)[0].strip().casefold()
        if kind in {"audio/l16", "audio/pcm"}:
            # Gemini documents L16 as signed little-endian, 16-bit, mono PCM.
            match = re.search(r"(?:^|;)\s*rate=(\d+)", mime)
            rate = block.get("sample_rate", int(match.group(1)) if match else 24_000)
            if type(rate) is not int or not 8_000 <= rate <= 192_000 or len(audio) % 2:
                raise ValueError("Invalid PCM format")
            output = io.BytesIO()
            with wave.open(output, "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(rate)
                stream.writeframes(audio)
            audio = output.getvalue()
        elif kind not in {"audio/wav", "audio/x-wav", "audio/wave"}:
            raise ValueError("Unexpected speech audio format")
        with wave.open(io.BytesIO(audio), "rb") as stream:
            if stream.getnframes() < 1 or not stream.readframes(stream.getnframes()):
                raise ValueError("Empty WAV audio")
        return SynthesizedAudio(audio, media_type="audio/wav")
    except (KeyError, TypeError, ValueError, binascii.Error, wave.Error, EOFError) as exc:
        raise GeminiAudioError("Gemini returned invalid or unsupported speech audio.") from exc


@dataclass(frozen=True)
class GeminiAudioRenderer:
    api_key: str = field(repr=False)
    model: str
    endpoint_url: str
    voice: str = "Kore"
    timeout: float = 90.0
    client: Any = field(default=None, repr=False)

    async def synthesize(self, text: str, *, speed: float = 1.0, volume: float = 0.0) -> SynthesizedAudio:
        part: dict[str, Any] = {"type": "text", "text": text}
        if speed != 1.0 or volume != 0.0:
            part["annotations"] = [{
                "type": "speech_metadata",
                "style": f"Speaking rate: {speed:g} times normal. Volume: {volume:g} dB relative to normal.",
            }]
        payload = {
            "model": self.model.removeprefix("models/"),
            "input": [{"type": "user_input", "content": [part]}],
            "response_format": {"type": "audio", "mime_type": "audio/wav", "sample_rate": 24_000},
            "generation_config": {"speech_config": [{"voice": self.voice}]},
        }
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json", "Accept": "application/json"}
        try:
            if self.client is not None:
                response = await self.client.request(
                    "POST", gemini_interactions_url(self.endpoint_url),
                    headers=headers, json=payload, timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(gemini_interactions_url(self.endpoint_url), headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise GeminiAudioError("Gemini speech endpoint could not be reached.") from exc
        if response.status_code >= 400:
            raise GeminiAudioError(f"Gemini rejected the speech request (HTTP {response.status_code}).")
        try:
            result = response.json()
            blocks = [
                block for step in result.get("steps", []) if step.get("type") == "model_output"
                for block in step.get("content", []) if block.get("type") == "audio"
            ]
            if not blocks:
                raise ValueError("No generated speech")
            return _playable_audio(blocks[-1])
        except (TypeError, ValueError, AttributeError) as exc:
            raise GeminiAudioError("Gemini returned no valid speech audio.") from exc
