# Axiom Body v0.1

Initial documentation and Unity-side reference skeleton for Axiom embodiment.

## Contents

- `docs/body/axiom-unity-rig-spec-v0.1.md` — rig, mesh, prefab, animation boundaries.
- `docs/body/axiom-body-api-v0.1.md` — semantic Mind ↔ Body contract.
- `unity/Assets/AxiomBody/Scripts/AxiomBodyTypes.cs` — shared contract types.
- `unity/Assets/AxiomBody/Scripts/IAxiomBody.cs` — body interface.
- `unity/Assets/AxiomBody/Scripts/AxiomBodyController.cs` — initial Unity adapter.
- `unity/Assets/AxiomBody/Config/body-manifest.json` — reference capability manifest.
- `docs/body/axiom-body-message-contract-v0.1.md` — stable Mind ↔ body command/result/event envelope.
- `unity/Assets/AxiomBody/Scripts/AxiomBodyMessages.cs` — serializable protocol envelopes and payloads.
- `unity/Assets/AxiomBody/Scripts/AxiomBodyCommandRouter.cs` — transport-independent semantic command router.

## Current v0.1 scope

Implemented contract stubs:
- connect/disconnect
- status/capabilities
- presence
- gaze
- expression
- gesture
- speech intent
- listen intent
- observe intent
- posture
- stop

Intentionally deferred:
- locomotion
- actual TTS provider
- lip-sync provider
- camera/audio evidence capture
- MCP transport bindings
- finished model/rig/animations

The approved Axiom character design remains canonical and must not be regenerated or visually reinterpreted during implementation.
