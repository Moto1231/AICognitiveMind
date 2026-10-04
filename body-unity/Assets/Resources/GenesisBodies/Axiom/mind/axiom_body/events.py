from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Dict

from .models import BodyEvent

EvidenceSink = Callable[[Dict[str, Any]], Awaitable[None]]
JournalSink = Callable[[Dict[str, Any]], Awaitable[None]]


class BodyEventBridge:
    """Routes body events toward Mind evidence/journal systems without coupling them."""

    def __init__(
        self,
        *,
        evidence_sink: EvidenceSink | None = None,
        journal_sink: JournalSink | None = None,
    ) -> None:
        self.evidence_sink = evidence_sink
        self.journal_sink = journal_sink

    async def handle(self, event: BodyEvent) -> None:
        payload = event.to_dict()

        if event.event in {"body.saw", "body.heard"} and self.evidence_sink is not None:
            await self.evidence_sink(payload)

        if self.journal_sink is not None:
            await self.journal_sink(
                {
                    "kind": "body_event",
                    "occurred_at": event.occurred_at,
                    "experience": payload,
                }
            )
