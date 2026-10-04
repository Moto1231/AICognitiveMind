from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

PROTOCOL = "axiom.body/0.1"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


@dataclass(slots=True)
class BodyCommand:
    action: str
    payload: Dict[str, Any] = field(default_factory=dict)
    body_id: str = "axiom.reference.unity"
    command_id: str = field(default_factory=lambda: new_id("cmd"))
    protocol: str = PROTOCOL
    message_type: str = "command"

    def to_wire(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BodyResult:
    command_id: str
    body_id: str
    success: bool
    code: str = "OK"
    message: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    protocol: str = PROTOCOL
    message_type: str = "result"

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "BodyResult":
        return cls(
            command_id=str(data.get("command_id", "")),
            body_id=str(data.get("body_id", "")),
            success=bool(data.get("success", False)),
            code=str(data.get("code", "OK" if data.get("success") else "INTERNAL_BODY_ERROR")),
            message=data.get("message"),
            payload=dict(data.get("payload") or {}),
            protocol=str(data.get("protocol", PROTOCOL)),
            message_type=str(data.get("message_type", "result")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BodyEvent:
    event: str
    body_id: str
    payload: Dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: new_id("evt"))
    occurred_at: str = field(default_factory=utc_now_iso)
    protocol: str = PROTOCOL
    message_type: str = "event"

    @classmethod
    def from_wire(cls, data: Dict[str, Any]) -> "BodyEvent":
        return cls(
            event=str(data.get("event", "body.unknown")),
            body_id=str(data.get("body_id", "")),
            payload=dict(data.get("payload") or {}),
            event_id=str(data.get("event_id") or new_id("evt")),
            occurred_at=str(data.get("occurred_at") or utc_now_iso()),
            protocol=str(data.get("protocol", PROTOCOL)),
            message_type=str(data.get("message_type", "event")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
