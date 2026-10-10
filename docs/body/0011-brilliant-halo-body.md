# 0011 — Brilliant Labs Halo Body V0.1

**Status:** Experimental hardware adapter; hardware not required.

## Purpose

Treat Brilliant Labs Halo as a replaceable Axiom Body implementation. Halo owns sensing and
expression hardware only. Axiom continues to own identity, cognition, memory and governance.

## Integration path

```text
Halo / halo-emulator
        |
  Brilliant SDK protocol
        |
Android bridge (Flutter) / development host
        |
     HaloIngress
        |
    BodyRuntime
        |
       Mind
```

Noa or another Brilliant-hosted reasoning service is not required by this design.

## Development without glasses

Brilliant publishes `halo-emulator`, which executes the same device-side Lua application used
on Halo. Install it in a disposable Python environment:

```bash
python -m venv .venv-halo
source .venv-halo/bin/activate
pip install halo-emulator brilliant-sdk
halo-emulator ./halo_app/
```

The emulator provides the 256x256 display plus button, IMU and microphone event injection. The
Axiom device shell is `halo_app/main.lua`.

Current controls:

- single click -> `AXIOM:LOOK`
- double click -> `AXIOM:LISTEN`
- long press -> `AXIOM:STATUS`

These are transport messages, not cognitive decisions.

## Android target

The production phone bridge should use Brilliant's Flutter packages (`brilliant_ble`,
`brilliant_msg`, `brilliant_sdk`). It will pair to Halo over BLE, upload/run the Lua app,
translate Halo photos/audio/events into the existing Axiom Body contracts, and send expression
back to Halo.

## Boundary

Do not put memory, identity, reasoning or provider-specific AI logic into the Halo app or Android
bridge. Continuous sensor data remains transient. Deliberate observations enter the existing
sensory-evidence path before interpretation.

## Emulator round-trip proof

The emulator smoke check exercises the device-side half of a host round trip:

1. The app renders `Axiom / Ready`.
2. A single button press emits `AXIOM:LOOK` through BLE.
3. A host reply injected through BLE is rendered on the display.

Install `halo-emulator` in the active Python environment, then run:

```bash
python scripts/halo_emulator_smoke.py
```

For interactive inspection, launch `halo-emulator ./halo_app/` and use Space, D, or L for
the single, double, or long button press. The app accepts host replies as text bytes
through its registered BLE receive callback. This proves the Lua/emulator protocol loop only;
it does not prove an Android bridge, authenticated Axiom Body request, continuous sensing,
or physical Halo behavior.

## Development host bridge

`scripts/halo_emulator_body_bridge.py` connects the emulator's `AXIOM:LOOK` event to the
existing authenticated Body API. Since the emulator has no camera, the host sends a caller-
selected JPEG fixture through `/v1/body/eyes/observe`, requests `/v1/mind/body/see`, and sends
the returned `response_text` back to the emulator display. The fixture source is labeled
`brilliant-halo-emulator-test-image`.

Run it from an environment with this project, Pillow, and `halo-emulator` installed. Use a
local or mock Axiom service URL while developing:

```bash
python scripts/halo_emulator_body_bridge.py \
  --base-url http://127.0.0.1:8000 \
  --image path/to/test-image.jpg
```

The script prompts for the Axiom account username and password; it keeps the login cookie in
memory and generates a separate `X-Body-Session` for this emulator session. A single button
press makes one deliberate vision interaction in the selected service. Double press and long
press only return development status text. This does not capture real Halo camera data or prove
the Android/Flutter host.

## Next integration step

Implement the Android/Flutter host that subscribes to the three `AXIOM:*` commands, invokes
the authenticated Axiom Body APIs, and returns an expression to Halo over BLE. Exercise that
host against a local/mock Body API before sending any deliberate sensory evidence to a live
account. Do not fork Halo firmware unless the stock Lua runtime/SDK proves insufficient.
