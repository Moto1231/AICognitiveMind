"""Shared, durable voice preferences for Axiom's browser Body and MCP hosts."""

from __future__ import annotations

import math
from typing import Any

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.host_runtime import RuntimeRecords

DEFAULT_VOICE_SETTINGS: dict[str, Any] = {
    "voiceName": "",
    "rate": 1.0,
    "pitch": 1.0,
    "volume": 1.0,
    "revision": 0,
}


class VoiceSettings:
    KEY = "body_voice_settings"

    def __init__(self, mind: Any) -> None:
        self.records = RuntimeRecords(mind)

    async def read(self) -> dict[str, Any]:
        stored = await self.records.get(self.KEY)
        return {**DEFAULT_VOICE_SETTINGS, **(stored or {})}

    async def update(
        self,
        *,
        expected_revision: int,
        voice_name: str | None = None,
        rate: float | None = None,
        pitch: float | None = None,
        volume: float | None = None,
    ) -> dict[str, Any]:
        changes: dict[str, Any] = {}
        if voice_name is not None:
            if len(voice_name) > 120:
                raise ValueError("Voice name is too long")
            changes["voiceName"] = voice_name.strip()
        for name, value, lower, upper in (
            ("rate", rate, 0.5, 1.75),
            ("pitch", pitch, 0.5, 1.5),
            ("volume", volume, 0.0, 1.0),
        ):
            if value is not None:
                if not math.isfinite(value) or not lower <= value <= upper:
                    raise ValueError(f"{name} must be between {lower} and {upper}")
                changes[name] = value
        if not changes:
            raise ValueError("Supply at least one voice setting")

        before = await self.records.get(self.KEY)
        current = {**DEFAULT_VOICE_SETTINGS, **(before or {})}
        if current["revision"] != expected_revision:
            raise CommitConflict("Voice settings changed; read them again before updating")
        after = {**current, **changes, "revision": expected_revision + 1}
        if before is None:
            try:
                await self.records.create(self.KEY, after)
            except CommitConflict as exc:
                raise CommitConflict("Voice settings changed; read them again") from exc
        elif not await self.records.replace(self.KEY, before, after):
            raise CommitConflict("Voice settings changed; read them again")
        return after
