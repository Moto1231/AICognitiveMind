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

## Next proof

Run the Lua shell under `halo-emulator` and verify display plus button-to-BLE messages. After
that proof, implement the Android/Flutter bridge. Do not fork Halo firmware unless the stock Lua
runtime/SDK proves insufficient.
