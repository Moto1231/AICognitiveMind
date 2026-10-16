"""Keep encoded sensory media out of append-only journal experiences."""

from __future__ import annotations

import re
from typing import Any

_SENSORY_DATA_URL = re.compile(
    r"data:[^,\s\"']+;base64,[A-Za-z0-9+/=\r\n]+",
    re.IGNORECASE,
)
_SENSORY_PAYLOAD_KEYS = {"payload_base64", "image_data", "audio_data"}


def journal_safe_value(value: Any, *, key: str | None = None) -> Any:
    """Redact encoded media from the journal while leaving reasoning inputs untouched."""
    if isinstance(value, dict):
        return {
            str(child_key): journal_safe_value(child_value, key=str(child_key).lower())
            for child_key, child_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [journal_safe_value(item) for item in value]
    if not isinstance(value, str):
        return value
    if key in _SENSORY_PAYLOAD_KEYS:
        return "[encoded sensory payload omitted from journal; see preserved evidence reference]"
    return _SENSORY_DATA_URL.sub(
        "[encoded sensory payload omitted from journal; see preserved evidence reference]",
        value,
    )
