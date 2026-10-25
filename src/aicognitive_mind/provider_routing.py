"""Daily task ordering and Mind-scoped provider cooldowns; no credential values are stored."""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Callable

from aicognitive_mind.provider_endpoints import ProviderEndpoint


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProviderRoutingRegistry:
    """Remember availability across requests, dispatchers and process restarts.

    A changed endpoint URL, key or model starts a new availability episode. The
    stored key is a digest, and the record contains only redacted status fields.
    """

    def __init__(self, records: Any, *, clock: Callable[[], datetime] | None = None) -> None:
        self.records = records
        self.clock = clock or utc_now

    def now(self) -> datetime:
        return self.clock().astimezone(UTC)

    @staticmethod
    def _key(endpoint: ProviderEndpoint, model: str) -> str:
        configuration = json.dumps([
            endpoint.id, endpoint.base_url, endpoint.api_key, model.casefold(),
        ], separators=(",", ":"))
        return "provider_cooldown_" + hashlib.sha256(configuration.encode()).hexdigest()

    async def cooldown(self, endpoint: ProviderEndpoint, model: str) -> dict[str, Any] | None:
        record = await self.records.get(self._key(endpoint, model))
        if record is None:
            return None
        try:
            until = datetime.fromisoformat(record["cooldown_until"])
            if until.tzinfo is None or until <= self.now():
                return None
        except (KeyError, TypeError, ValueError):
            return None
        return record

    @staticmethod
    def _duration(value: str) -> float | None:
        """Parse provider reset durations, including Groq's 1h2m3.5s hints."""
        value = value.strip().lower()
        try:
            numeric = float(value)
            return numeric if math.isfinite(numeric) and numeric >= 0 else None
        except ValueError:
            pass
        parts = re.findall(r"(\d+(?:\.\d+)?)(ms|s|m|h|d)", value)
        if not parts or "".join(number + unit for number, unit in parts) != value:
            return None
        units = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
        return sum(float(number) * units[unit] for number, unit in parts)

    def rate_limit_delay(self, headers: Any) -> float:
        now = self.now()
        normalized = {str(key).lower(): str(value) for key, value in headers.items()}
        hint = normalized.get("retry-after", "")
        delay = self._duration(hint)
        if delay is None and hint:
            try:
                reset = parsedate_to_datetime(hint)
                if reset.tzinfo is not None:
                    delay = max(0.0, (reset - now).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
        if delay is None:
            resets = [self._duration(normalized.get(key, "")) for key in (
                "x-ratelimit-reset-requests", "x-ratelimit-reset-tokens",
            )]
            delay = max((value for value in resets if value is not None), default=60.0)
        # Provider hints never cause a blocking sleep here. Reconsider within a
        # day even if a broken upstream emits a wildly distant reset time.
        return min(86400.0, max(1.0, delay))

    async def record_http_failure(
        self, endpoint: ProviderEndpoint, model: str, status_code: int, headers: Any,
    ) -> None:
        if status_code == 429:
            delay, reason = self.rate_limit_delay(headers), "rate_limited"
        elif status_code in (401, 403):
            delay, reason = 300.0, "authentication_failed"
        elif status_code in (408, 500, 502, 503, 504):
            delay, reason = 30.0, "temporarily_unavailable"
        else:
            return
        await self._record_failure(endpoint, model, delay, reason, status_code)

    async def record_transport_failure(self, endpoint: ProviderEndpoint, model: str) -> None:
        await self._record_failure(endpoint, model, 30.0, "transport_failed", None)

    async def _record_failure(
        self, endpoint: ProviderEndpoint, model: str, delay: float, reason: str,
        status_code: int | None,
    ) -> None:
        until = self.now() + timedelta(seconds=delay)
        key = self._key(endpoint, model)
        for _ in range(3):
            before = await self.records.get(key)
            # A shorter concurrent failure must not shorten an active cooldown.
            if before:
                try:
                    existing = datetime.fromisoformat(before["cooldown_until"])
                    if existing.tzinfo is not None and existing >= until:
                        return
                except (KeyError, TypeError, ValueError):
                    pass
            after = {
                "endpoint_id": endpoint.id, "model": model,
                "status_code": status_code, "reason": reason,
                "cooldown_until": until.isoformat(),
            }
            if before is None:
                try:
                    await self.records.create(key, after)
                    return
                except Exception:
                    # A competing creator may have won. A real storage failure
                    # remains visible to the caller instead of claiming a save.
                    if await self.records.get(key) is None:
                        raise
            elif await self.records.replace(key, before, after):
                return
        raise RuntimeError("Provider cooldown changed concurrently; retry on the next request")
