"""Mind-scoped operational health for interaction persistence.

This state contains no conversation or memory content. It intentionally lives in
runtime records, outside the cognitive journal/memory transaction whose failure it
tracks.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.continuity_settings import ContinuitySettings
from aicognitive_mind.host_runtime import RuntimeRecords

STATE_KEY = "interaction_continuity_health"
BREAKER_NAME = "The Breaker"
CONSECUTIVE_FAILURE_LIMIT = 5
ROLLING_FAILURE_LIMIT = 35
ROLLING_WINDOW_SIZE = 100
MAX_ROLLING_WINDOW_SIZE = 500


class InteractionContinuityHealth:
    """Record one final persistence outcome per interaction key."""

    def __init__(self, records: RuntimeRecords) -> None:
        self.records = records

    @staticmethod
    def _empty() -> dict[str, Any]:
        return {
            "kind": STATE_KEY,
            "version": 2,
            "consecutive_failures": 0,
            "recent_outcomes": [],
            "last_interaction_id": None,
            "last_failure_class": None,
            "last_degradation_class": None,
            "last_reset_at": None,
            "reset_count": 0,
            "updated_at": None,
        }

    @staticmethod
    def _failure_count(outcomes: list[dict[str, Any]]) -> int:
        return sum(item.get("succeeded") is False for item in outcomes)

    @staticmethod
    def _degradation_count(outcomes: list[dict[str, Any]]) -> int:
        return sum(item.get("degraded") is True for item in outcomes)

    @staticmethod
    def _consecutive_failures(outcomes: list[dict[str, Any]]) -> int:
        count = 0
        for item in reversed(outcomes):
            if item.get("succeeded") is not False:
                break
            count += 1
        return count

    @classmethod
    def _public(
        cls, state: dict[str, Any], *, interaction_id: str | None = None,
        settings: ContinuitySettings | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        policy = cls._settings(settings)
        outcomes = list(state.get("recent_outcomes", ()))
        outcomes = outcomes[-policy.rolling_window_size:]
        consecutive = cls._consecutive_failures(outcomes)
        failures = cls._failure_count(outcomes)
        degradations = cls._degradation_count(outcomes)
        rolling_window_ready = len(outcomes) >= policy.rolling_window_size
        reasons = []
        if consecutive >= policy.consecutive_failure_limit:
            reasons.append("consecutive_failures")
        if rolling_window_ready and failures >= policy.rolling_failure_limit:
            reasons.append("rolling_failures")
        result: dict[str, Any] = {
            "name": BREAKER_NAME,
            "status": "open" if reasons else "closed",
            "circuit_open": bool(reasons),
            "open_reasons": reasons,
            "consecutive_failures": consecutive,
            "rolling_window_size": policy.rolling_window_size,
            "rolling_sample_size": len(outcomes),
            "rolling_window_ready": rolling_window_ready,
            "rolling_failures": failures,
            "degraded_reviews": degradations,
            "thresholds": {
                "consecutive_failures": policy.consecutive_failure_limit,
                "rolling_failures": policy.rolling_failure_limit,
                "rolling_window_size": policy.rolling_window_size,
            },
            "last_interaction_id": state.get("last_interaction_id"),
            "last_failure_class": state.get("last_failure_class"),
            "last_degradation_class": state.get("last_degradation_class"),
            "last_reset_at": state.get("last_reset_at"),
            "reset_count": state.get("reset_count", 0),
            "updated_at": state.get("updated_at"),
        }
        if interaction_id is not None:
            outcome = next(
                (
                    item for item in outcomes
                    if item.get("interaction_id") == interaction_id
                ),
                None,
            )
            if outcome is not None:
                result["interaction_outcome"] = {
                    "succeeded": outcome["succeeded"],
                    "failure_class": outcome.get("failure_class"),
                    "degraded": outcome.get("degraded", False),
                    "degradation_class": outcome.get("degradation_class"),
                    "presentation_allowed": outcome["presentation_allowed"],
                    "report_persistence_error": (
                        outcome["succeeded"] is False
                        and not outcome["presentation_allowed"]
                    ),
                    "recorded_at": outcome["recorded_at"],
                }
        return result

    @staticmethod
    def _settings(settings: ContinuitySettings | dict[str, Any] | None) -> ContinuitySettings:
        if isinstance(settings, ContinuitySettings):
            return settings
        if settings is None:
            return ContinuitySettings()
        return ContinuitySettings.model_validate({
            key: settings[key]
            for key in ContinuitySettings.model_fields
            if key in settings
        })

    async def snapshot(
        self, settings: ContinuitySettings | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._public(
            await self.records.get(STATE_KEY) or self._empty(), settings=settings,
        )

    async def record(
        self,
        interaction_id: str,
        *,
        succeeded: bool,
        failure_class: str | None = None,
        degraded: bool = False,
        degradation_class: str | None = None,
        settings: ContinuitySettings | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(interaction_id, str) or not interaction_id:
            raise ValueError("interaction_id must be a nonblank string")
        if degraded and not succeeded:
            raise ValueError("a degraded interaction must have completed critical persistence")
        for _ in range(8):
            current = await self.records.get(STATE_KEY)
            base = deepcopy(current) if current is not None else self._empty()
            outcomes = list(base.get("recent_outcomes", ()))
            existing_index = next(
                (
                    index for index, item in enumerate(outcomes)
                    if item.get("interaction_id") == interaction_id
                ),
                None,
            )
            if existing_index is not None:
                existing = outcomes[existing_index]
                if existing.get("succeeded") is True or not succeeded:
                    return self._public(
                        base, interaction_id=interaction_id, settings=settings,
                    )
                # An identical retry that succeeds replaces the provisional
                # failure; attempts never count as separate interaction outcomes.
                before_open = self._public(base, settings=settings)["circuit_open"]
                outcomes[existing_index] = {
                    **existing,
                    "succeeded": True,
                    "failure_class": None,
                    "degraded": degraded,
                    "degradation_class": degradation_class if degraded else None,
                    "presentation_allowed": True,
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "recovered_after_retry": True,
                    "recovery_was_required": before_open,
                }
            else:
                before_open = self._public(base, settings=settings)["circuit_open"]
                outcomes.append({
                    "interaction_id": interaction_id,
                    "succeeded": succeeded,
                    "failure_class": None if succeeded else failure_class,
                    "degraded": degraded,
                    "degradation_class": degradation_class if degraded else None,
                    # Failure number five (or rolling number 35) is still shown.
                    # A later interaction is held only if the circuit was already open.
                    "presentation_allowed": succeeded or not before_open,
                    "recorded_at": datetime.now(UTC).isoformat(),
                    "recovered_after_retry": False,
                    "recovery_was_required": before_open,
                })
            outcomes = outcomes[-MAX_ROLLING_WINDOW_SIZE:]
            failures = [item for item in outcomes if item.get("succeeded") is False]
            degradations = [item for item in outcomes if item.get("degraded") is True]
            updated = {
                **base,
                "version": 2,
                "recent_outcomes": outcomes,
                "consecutive_failures": self._consecutive_failures(outcomes),
                "last_interaction_id": interaction_id,
                "last_failure_class": (
                    failures[-1].get("failure_class") if failures else None
                ),
                "last_degradation_class": (
                    degradations[-1].get("degradation_class") if degradations else None
                ),
                "updated_at": datetime.now(UTC).isoformat(),
            }
            if current is None:
                try:
                    await self.records.create(STATE_KEY, updated)
                except Exception:
                    if await self.records.get(STATE_KEY) is not None:
                        continue
                    raise
                return self._public(
                    updated, interaction_id=interaction_id, settings=settings,
                )
            if await self.records.replace(STATE_KEY, current, updated):
                return self._public(
                    updated, interaction_id=interaction_id, settings=settings,
                )
        raise CommitConflict("Interaction continuity health changed concurrently; retry")

    async def reset(
        self, settings: ContinuitySettings | dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Clear operational breaker history without touching cognitive records."""
        for _ in range(8):
            current = await self.records.get(STATE_KEY)
            reset_at = datetime.now(UTC).isoformat()
            updated = {
                **self._empty(),
                "last_reset_at": reset_at,
                "reset_count": int((current or {}).get("reset_count", 0)) + 1,
                "updated_at": reset_at,
            }
            if current is None:
                try:
                    await self.records.create(STATE_KEY, updated)
                except Exception:
                    if await self.records.get(STATE_KEY) is not None:
                        continue
                    raise
                return self._public(updated, settings=settings)
            if await self.records.replace(STATE_KEY, current, updated):
                return self._public(updated, settings=settings)
        raise CommitConflict("Interaction continuity health changed concurrently; retry")
