"""Lightweight latency diagnostics.

Logs how long named stages take so slow paths can be measured on the deployed
instance. Timing never changes results. Set AXIOM_TIMING=0 to silence it.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger("aicognitive_mind.timing")
if not logger.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False

ENABLED = os.environ.get("AXIOM_TIMING", "1") != "0"


def emit(message: str, *args: object) -> None:
    if ENABLED:
        logger.info(message, *args)


def caller(depth: int = 2) -> str:
    """Name the logical caller of the function that invoked this helper."""
    try:
        code = sys._getframe(depth).f_code
    except ValueError:
        return "unknown"
    return f"{os.path.basename(code.co_filename)}:{code.co_name}"


class StageTimer:
    """Accumulate named stage durations for one operation, then log one line."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        self._started = time.perf_counter()
        self._stages: list[tuple[str, float]] = []

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        finally:
            self._stages.append((name, time.perf_counter() - started))

    def log(self) -> None:
        if not ENABLED:
            return
        total = time.perf_counter() - self._started
        stages = " ".join(f"{name}={seconds:.3f}s" for name, seconds in self._stages)
        logger.info("timing %s total=%.3fs %s", self.operation, total, stages)
