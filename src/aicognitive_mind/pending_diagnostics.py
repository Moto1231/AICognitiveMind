"""Best-effort, content-free diagnostics for an existing pending-queue read.

Cursor advances include driver/server/network/decoding/scheduling time. Payload
sizes count decoded string values and binary data, not serialized or wire bytes.
No payload is encoded, copied, converted to text, or sent to the logger.
"""

from __future__ import annotations

from typing import Any

from aicognitive_mind import timing


def _payload_sizes(rows: list[dict]) -> dict[str, int | bool]:
    remaining = 65_536
    complete = True
    active: set[int] = set()

    def visit(value: Any, depth: int) -> tuple[int, int]:
        nonlocal remaining, complete
        if remaining <= 0:
            complete = False
            return 0, 0
        remaining -= 1
        if depth > 16:
            complete = False
            return 0, 0
        if isinstance(value, str):
            return str.__len__(value), 0
        if isinstance(value, bytes):
            return 0, bytes.__len__(value)
        if isinstance(value, bytearray):
            return 0, bytearray.__len__(value)
        if type(value) is memoryview:
            return 0, value.nbytes
        if value is None or type(value) in (bool, int, float):
            return 0, 0
        if type(value) not in (dict, list, tuple):
            complete = False
            return 0, 0
        if depth == 16:
            complete = False
            return 0, 0
        identity = id(value)
        if identity in active:
            complete = False
            return 0, 0
        active.add(identity)
        chars = binary = 0
        try:
            values = value.values() if type(value) is dict else value
            for item in values:
                if remaining <= 0:
                    complete = False
                    break
                item_chars, item_binary = visit(item, depth + 1)
                chars += item_chars
                binary += item_binary
        finally:
            active.remove(identity)
        return chars, binary

    chars_total = chars_max = binary_total = binary_max = 0
    for row in rows:
        if remaining <= 0:
            complete = False
            break
        chars, binary = visit(row, 0)
        chars_total += chars
        chars_max = max(chars_max, chars)
        binary_total += binary
        binary_max = max(binary_max, binary)
    return {
        "string_chars_total": chars_total, "string_chars_max": chars_max,
        "binary_bytes_total": binary_total, "binary_bytes_max": binary_max,
        "sizes_complete": complete,
    }


class PendingReadDiagnostics:
    """Synchronous observation only; failures must never affect the queue read."""

    def __init__(self, backend: str, database: Any) -> None:
        self._started: float | None = None
        try:
            if not timing.ENABLED:
                return
            client = database.client if backend == "mongo" else database
            self._client = type(client).__name__
            self._backend = backend
            self._phases: dict[str, float] = {}
            self._received = False
            self._event = "start"
            self._last = self._started = timing.time.perf_counter()
        except Exception:
            self._started = None

    def _mark(self, event: str, now: float) -> None:
        elapsed = now - self._last
        if event == "cursor_construct":
            self._phases["cursor_construct_s"] = elapsed
        elif event in {"row", "cursor_exhausted"}:
            phase = "remaining_next_s" if self._received else "first_next_s"
            self._phases[phase] = self._phases.get(phase, 0.0) + elapsed
            if event == "row":
                self._received = True
        elif event == "materialize":
            self._phases["materialize_s"] = self._phases.get("materialize_s", 0.0) + elapsed
        self._last, self._event = now, event

    def mark(self, event: str) -> None:
        try:
            if self._started is not None:
                self._mark(event, timing.time.perf_counter())
        except Exception:
            self._started = None

    def log(self, rows: list[dict], outcome: str) -> None:
        try:
            if self._started is None:
                return
            finished = timing.time.perf_counter()
            wall = finished - self._started
            if self._backend == "mongo":
                # Include failed/cancelled advances and terminal empty exhaustion.
                if self._event in {"cursor_construct", "materialize"}:
                    self._mark("cursor_exhausted", finished)
                elif self._event == "row":
                    self._mark("materialize", finished)
                elif self._event == "start":
                    self._mark("cursor_construct", finished)
            else:
                self._phases["query_s"] = wall
            sizes = _payload_sizes(rows)
            size_seconds = timing.time.perf_counter() - finished
            phases = " ".join(f"{key}={value:.3f}" for key, value in self._phases.items())
            counts = " ".join(f"{key}={value}" for key, value in sizes.items())
            timing.emit(
                "timing runtime_records.pending backend=%s client=%s wall_s=%.3f %s "
                "rows=%d %s size_s=%.3f outcome=%s",
                self._backend, self._client, wall, phases, len(rows), counts,
                size_seconds, outcome,
            )
        except Exception:
            # Diagnostics may be unavailable; preserve the original result/error.
            pass
