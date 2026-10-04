"""Smoke-check the Halo Lua app's display and BLE round trip using halo-emulator."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from halo_emulator import HaloEmulator


ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, description: str, timeout: float = 3.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise RuntimeError(f"Timed out waiting for {description}")


def has_visible_pixels(image) -> bool:
    return any(r + g + b > 30 for r, g, b, _ in image.getdata())


def main() -> int:
    with HaloEmulator(print_handler=None) as emulator:
        emulator.load_directory(ROOT / "halo_app")
        emulator.start("main.lua")

        try:
            wait_for(lambda: has_visible_pixels(emulator.get_framebuffer()), "startup display")

            emulator.inject_button_single()
            wait_for(
                lambda: b"AXIOM:LOOK" in emulator.get_bluetooth_sent(),
                "single-button LOOK BLE message",
            )

            before_reply = emulator.get_framebuffer().tobytes()
            emulator.inject_bluetooth_data(b"Axiom response")
            wait_for(
                lambda: emulator.get_framebuffer().tobytes() != before_reply,
                "host response display",
            )

            emulator.clear_bluetooth_sent()
            emulator.inject_button_double()
            wait_for(
                lambda: b"AXIOM:LISTEN" in emulator.get_bluetooth_sent(),
                "double-button LISTEN BLE message",
            )

            emulator.clear_bluetooth_sent()
            emulator.inject_button_long()
            wait_for(
                lambda: b"AXIOM:STATUS" in emulator.get_bluetooth_sent(),
                "long-button STATUS BLE message",
            )

            print("PASS: Halo emulator rendered the app, sent all three button commands, and displayed a host reply.")
            return 0
        finally:
            if emulator.is_running():
                emulator.stop()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
