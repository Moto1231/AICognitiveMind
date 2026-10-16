from __future__ import annotations

from dataclasses import dataclass

import httpx


FISH_TTS_URL = "https://api.fish.audio/v1/tts"


class FishAudioError(RuntimeError):
    """Raised when Fish Audio cannot synthesize speech."""


@dataclass(frozen=True)
class FishAudioRenderer:
    api_key: str
    model: str = "s2.1-pro-free"
    reference_id: str | None = None
    endpoint_url: str = FISH_TTS_URL

    async def synthesize(
        self,
        text: str,
        *,
        speed: float = 1.0,
        volume: float = 0.0,
    ) -> bytes:
        payload: dict[str, object] = {
            "text": text,
            "format": "mp3",
            "prosody": {
                "speed": max(0.5, min(2.0, speed)),
                "volume": max(-20.0, min(20.0, volume)),
            },
        }
        if self.reference_id:
            payload["reference_id"] = self.reference_id

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "model": self.model,
        }

        try:
            endpoint_url = self.endpoint_url.rstrip("/")
            if not endpoint_url.endswith("/tts"):
                endpoint_url += "/tts"
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(endpoint_url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise FishAudioError("Fish Audio could not be reached.") from exc

        if response.status_code >= 400:
            detail = response.text[:500].strip()
            raise FishAudioError(
                f"Fish Audio rejected the speech request ({response.status_code})."
                + (f" {detail}" if detail else "")
            )

        if not response.content:
            raise FishAudioError("Fish Audio returned an empty audio response.")

        return response.content
