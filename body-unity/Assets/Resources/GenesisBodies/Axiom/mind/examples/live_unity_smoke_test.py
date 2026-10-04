"""Smoke-test a real Unity Axiom body connected to the Mind host.

Prerequisite: run the Mind/FastAPI host with /body/ws installed, then put the
Unity scene in Play mode so AxiomBodyWebSocketClient connects to it.

Run from the mind directory:
    python -m examples.live_unity_smoke_test
"""

import asyncio
import json

from axiom_body.service import AxiomBodyService
from axiom_body.session import BodySessionManager


async def wait_for_body(session: BodySessionManager, timeout: float = 30.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not session.connected:
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("No Unity body connected within 30 seconds.")
        await asyncio.sleep(0.1)


async def run_smoke_test(session: BodySessionManager) -> None:
    body = AxiomBodyService(session)
    await wait_for_body(session)

    print("[Mind] Unity body connected")

    steps = [
        ("status", body.status),
        ("capabilities", body.capabilities),
        ("expression", lambda: body.expression("curious", intensity=0.55, duration_ms=1500)),
        ("speak", lambda: body.speak("Axiom body connection confirmed.", emotion="curious")),
        ("stop", body.stop),
    ]

    for name, call in steps:
        result = await call()
        print(f"\n[{name}]\n{json.dumps(result, indent=2)}")
        if result.get("success") is False:
            raise RuntimeError(f"Smoke test failed at {name}: {result}")

    print("\nPASS: Mind -> Body -> Mind round trip completed against the live Unity body.")


if __name__ == "__main__":
    raise SystemExit(
        "This module is intended to be called from the running Mind host where the shared "
        "BodySessionManager already owns /body/ws. Import run_smoke_test(session) and pass "
        "that live session manager."
    )
