"""Persistent, event-driven current-state ledger for Axiom.

The ledger stores the latest supported answer to foundational state questions.
The journal remains append-only; each ledger revision is recorded as a checkpoint.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, ClassVar, Literal

from pydantic import BaseModel, Field

from aicognitive_mind.commit import atomic
from aicognitive_mind.domain import CognitiveActor, JournalEntry, JournalKind, utc_now


AnswerStatus = Literal["current", "unknown", "disputed", "stale"]


class StateAnswer(BaseModel):
    value: Any = None
    status: AnswerStatus = "unknown"
    source: str = "not established"
    observed_at: datetime = Field(default_factory=utc_now)
    note: str | None = None


class CurrentStateLedger(BaseModel):
    """Readable current answers; unknown is explicit and never guessed."""

    schema_version: int = 1
    revision: int = 0
    updated_at: datetime = Field(default_factory=utc_now)
    fields: dict[str, StateAnswer] = Field(default_factory=dict)
    last_event: str = "initialized"

    FUNDAMENTAL_FIELDS: ClassVar[tuple[str, ...]] = (
        "identity",
        "foundations",
        "behaviors",
        "skills",
        "locality",
        "interlocutor",
        "presence",
        "active_topic",
        "active_task",
        "decisions_and_open_questions",
        "connection_status",
        "capabilities",
        "pending_work",
        "current_scene",
    )

    @classmethod
    def empty(cls) -> "CurrentStateLedger":
        return cls(fields={key: StateAnswer() for key in cls.FUNDAMENTAL_FIELDS})

    def answer(
        self,
        key: str,
        value: Any,
        *,
        source: str,
        status: AnswerStatus = "current",
        note: str | None = None,
    ) -> None:
        if key not in self.FUNDAMENTAL_FIELDS:
            raise ValueError(f"Unsupported current-state field: {key}")
        current = self.fields.get(key)
        if current is not None and (
            current.value == value
            and current.status == status
            and current.source == source
            and current.note == note
        ):
            return
        self.fields[key] = StateAnswer(
            value=value,
            status=status,
            source=source,
            observed_at=utc_now(),
            note=note,
        )

    def invalidate(self, key: str, *, event: str, note: str | None = None) -> None:
        if key not in self.FUNDAMENTAL_FIELDS:
            raise ValueError(f"Unsupported current-state field: {key}")
        source = f"invalidated by event:{event}"
        note = note or "A state-changing event invalidated the previous answer."
        current = self.fields.get(key)
        if current is not None and current.value is None and current.status == "unknown" and current.source == source and current.note == note:
            return
        self.fields[key] = StateAnswer(
            value=None,
            status="unknown",
            source=source,
            observed_at=utc_now(),
            note=note,
        )

    def apply_event(
        self,
        event: str,
        updates: dict[str, Any] | None = None,
        *,
        source: str = "state_event",
    ) -> "CurrentStateLedger":
        """Invalidate only the answers affected by an explicit event, then apply grounded updates."""
        invalidations = {
            "session_started": ("interlocutor", "presence", "active_topic", "active_task"),
            "location_changed": ("locality", "current_scene"),
            "speaker_changed": ("interlocutor", "presence"),
            "topic_changed": ("active_topic", "decisions_and_open_questions"),
            "task_changed": ("active_task", "pending_work"),
            "connection_changed": ("connection_status", "capabilities", "pending_work"),
            "scene_changed": ("current_scene", "presence"),
            "evidence_conflict": (),
            "state_refreshed": (),
        }
        if event not in invalidations:
            raise ValueError(f"Unsupported state event: {event}")
        updated = self.model_copy(deep=True)
        for key in invalidations[event]:
            updated.invalidate(key, event=event)
        payload = updates or {}
        invalidate_keys = payload.get("invalidate", [])
        for key in invalidate_keys:
            updated.invalidate(str(key), event=event)
        values = payload.get("values", {})
        if not isinstance(values, dict):
            raise ValueError("State event values must be an object.")
        for key, item in values.items():
            if key not in self.FUNDAMENTAL_FIELDS:
                raise ValueError(f"Unsupported current-state field: {key}")
            if isinstance(item, dict) and "value" in item:
                updated.answer(
                    key,
                    item.get("value"),
                    source=str(item.get("source") or source),
                    status=item.get("status", "current"),
                    note=item.get("note"),
                )
            else:
                updated.answer(key, item, source=source)
        updated.revision += 1
        updated.updated_at = utc_now()
        updated.last_event = event
        return updated

    def as_context(self) -> dict[str, Any]:
        return self.model_dump(mode="json")



class CurrentStateLedgerRepository:
    """Atomic journal-backed persistence for the latest state ledger."""

    def __init__(self, journal: Any) -> None:
        self._journal = journal

    @atomic
    async def apply_event(
        self,
        event: str,
        updates: dict[str, Any] | None = None,
        source: str = "state_event",
    ) -> CurrentStateLedger:
        ledger = CurrentStateLedger.empty()
        for entry in reversed(await self._journal.read()):
            if entry.kind == JournalKind.CHECKPOINT and entry.experience.get("checkpoint_type") == "current_state_ledger":
                try:
                    ledger = CurrentStateLedger.model_validate(entry.experience["state_ledger"])
                    break
                except Exception:
                    continue
        updated = ledger.apply_event(event, updates, source=source)
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                experience={
                    "checkpoint_type": "current_state_ledger",
                    "state_ledger": updated.as_context(),
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        return updated


async def apply_current_state_event(
    journal: Any,
    event: str,
    updates: dict[str, Any] | None = None,
    *,
    source: str = "state_event",
) -> CurrentStateLedger:
    """Apply and atomically persist a state event outside the MCP service."""
    return await CurrentStateLedgerRepository(journal).apply_event(
        event=event,
        updates=updates,
        source=source,
    )
