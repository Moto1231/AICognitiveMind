# Axiom Body v0.4

Reference embodiment package for Axiom's Mind-as-a-Tool architecture.

The body contract is semantic and transport-independent. The Unity reference body is one implementation of that contract; third-party avatar/body packs can implement the same interface without changing the Mind.

## v0.4 milestone

v0.4 turns the Unity side into a near drop-in runtime package for the approved Axiom model.

New in this version:

- `AxiomBodyBootstrap` automatically adds/wires the Body runtime components.
- `AxiomBodyConnectionDebug` gives a dependency-free live connection indicator in the Unity Console.
- Existing Controller/Router/Transport/EventEmitter now expose explicit configuration methods for bootstrap wiring.
- `docs/body/unity-live-setup-v0.4.md` defines the first real Unity acceptance test.
- `mind/examples/live_unity_smoke_test.py` provides the Mind-side smoke-test sequence for a real connected Unity body.

## Package layout

- `docs/body/` — rig, Body API, wire protocol, and Unity setup docs.
- `unity/Assets/AxiomBody/` — Unity reference body runtime scripts and manifest.
- `mind/axiom_body/` — Python Body service, MCP tool registration, WebSocket session manager and event bridge.
- `mind/tests/` — protocol/session tests.
- `mind/examples/` — simulated and live-body integration examples.

## First live Unity path

1. Copy `unity/Assets/AxiomBody` into the Unity project.
2. Install Unity's `com.unity.nuget.newtonsoft-json` package.
3. Add `AxiomBodyBootstrap` to the approved Axiom model root.
4. Run the Mind host with `/body/ws` installed.
5. Enter Unity Play mode.
6. Verify `body_status`, `body_capabilities`, `body_expression`, `body_speak`, and `body_stop`.

See `docs/body/unity-live-setup-v0.4.md` for acceptance criteria.

## Deliberately not in v0.4

- TTS provider selection
- lip sync
- final blendshape mapping
- microphone capture
- camera evidence capture
- locomotion

The point of v0.4 is to prove the real Mind ↔ Unity embodiment circuit before adding those subsystems.
