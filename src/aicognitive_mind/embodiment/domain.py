from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SensoryModality(StrEnum):
    VISION = "vision"
    AUDIO = "audio"
    SCREEN = "screen"


class ExpressionModality(StrEnum):
    VOICE = "voice"
    AVATAR = "avatar"


class Percept(BaseModel):
    """Transient sensory information produced by an embodiment adapter."""

    modality: SensoryModality
    observed_at: datetime = Field(default_factory=utc_now)
    source: str = Field(min_length=1)
    summary: str | None = None
    content_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExpressionIntent(BaseModel):
    """Transient intent describing how the being should express a response."""

    modality: ExpressionModality
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DeviceStatus(BaseModel):
    device: str = Field(min_length=1)
    available: bool
    detail: str | None = None
