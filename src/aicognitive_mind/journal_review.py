"""Bounded, independent background reviews of committed interaction journal entries."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from aicognitive_mind.domain import JournalEntry, JournalKind, utc_now

LOG = logging.getLogger(__name__)
LANES = ("current_state_review", "memory_review")
STARTUP_LOOKBACK = timedelta(days=1)
COMMIT_GRACE = timedelta(minutes=2)
STATE_FIELDS = (
    "who_is_speaking", "who_is_present", "locality", "current_scene", "mood",
    "active_topic", "active_task",
)


class StateFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: Literal[
        "who_is_speaking", "who_is_present", "locality", "current_scene", "mood",
        "active_topic", "active_task",
    ]
    issue: Literal["missed", "mishandled"]
    quote: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)


class StateReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: tuple[StateFinding, ...] = Field(max_length=7)


def journal_review_key(entry: JournalEntry) -> str:
    encoded = json.dumps(entry.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def observed_state(state: Any) -> dict[str, Any]:
    return {field: state.fields[field].model_dump(mode="json")
            for field in STATE_FIELDS if field in state.fields}


def interaction_speaker(context: Any) -> dict[str, str]:
    """Preserve attribution only from the host context for this exact interaction."""
    context = context or {}
    speaker_id = context.get("active_speaker")
    if speaker_id:
        for participant in context.get("participants") or ():
            if (participant.get("participant_id") == speaker_id
                    and participant.get("identity_status") == "confirmed"
                    and participant.get("name") and participant.get("grounding")):
                # Participant IDs are host-session-local, not durable identity keys.
                return {"name": participant["name"], "status": "confirmed"}
    return {"status": "unknown"}


class JournalReviewRunner:
    """One shared fetch when cursors align; either lane can fail and retry alone."""

    def __init__(self, service: Any, journal: Any, records: Any, *, batch_size: int = 4) -> None:
        self.service, self.journal, self.records = service, journal, records
        self.batch_size = batch_size
        self._lock = asyncio.Lock()

    async def _lane_record(self, key: str, initial: datetime) -> dict:
        existing = await self.records.get(key)
        if existing is not None:
            return existing
        candidate = {"since": initial.isoformat(), "offset": 0}
        try:
            await self.records.create(key, candidate)
        except Exception:
            existing = await self.records.get(key)
            if existing is None:
                raise
            return existing
        return candidate

    async def _run_lane(self, lane: str, record: dict, rows: list[JournalEntry]) -> int:
        count = 0
        key = "journal_review_" + lane
        for entry in rows:
            try:
                outcome = await self.service.review_journal_entry(
                    lane, entry, idempotency_key=journal_review_key(entry),
                )
                stamp = entry.occurred_at.isoformat()
                offset = record["offset"] + 1 if stamp == record["since"] else 1
                next_record = {**record, "since": stamp, "offset": offset}
                if lane == "current_state_review" and outcome.get("findings"):
                    old = record.get("findings", [])
                    next_record["findings"] = (old + outcome["findings"])[-20:]
                if not await self.records.replace(key, record, next_record):
                    break
            except Exception as exc:
                # Evidence, prompts and provider error bodies are intentionally not logged.
                LOG.warning("journal review lane=%s failed: %s", lane, type(exc).__name__)
                break
            count += 1
            record = next_record
        return count

    async def run_once(self, *, now: datetime | None = None) -> dict[str, int]:
        async with self._lock:
            now = now or utc_now()
            if await self.service._mind.load() is None:
                return dict.fromkeys(LANES, 0)
            records = {lane: await self._lane_record("journal_review_" + lane, now - STARTUP_LOOKBACK)
                       for lane in LANES}
            pages: dict[tuple[str, int], list[JournalEntry]] = {}
            for record in records.values():
                cursor = (record["since"], record["offset"])
                if cursor in pages:
                    continue
                pages[cursor], _ = await self.journal.query_page(
                    offset=cursor[1], limit=self.batch_size, newest_first=False,
                    kind=JournalKind.INTERACTION.value, occurred_from=datetime.fromisoformat(cursor[0]),
                    occurred_to=now - COMMIT_GRACE,
                )
            results = {}
            # Sequential lanes avoid doubling provider pressure. Failures are isolated.
            for lane, record in records.items():
                results[lane] = await self._run_lane(
                    lane, record, pages[(record["since"], record["offset"])],
                )
            return results

    async def run_forever(self, interval_seconds: int) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self.run_once()
            except Exception as exc:
                LOG.warning("journal review pass failed: %s", type(exc).__name__)

    @asynccontextmanager
    async def running(self, interval_seconds: int) -> AsyncIterator[None]:
        task = asyncio.create_task(self.run_forever(interval_seconds))
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
