# Unity Live Setup v0.4

This is the shortest path from the approved Axiom model to the first live body connection.

## 1. Copy the package

Copy `unity/Assets/AxiomBody` into the Unity project's `Assets` directory.

Install Unity package:

`com.unity.nuget.newtonsoft-json`

## 2. Prepare the Axiom root

Select the root GameObject that owns the approved Axiom model. Add:

`AxiomBodyBootstrap`

Do not remodel, replace, or regenerate the approved body. The bootstrap only adds runtime components.

Optional references:

- Animator: leave empty to auto-discover the first child Animator.
- Look Target: leave empty to create `Targets/LookTarget`.
- Voice Source: leave empty to auto-discover a child AudioSource.

Default Mind endpoint:

`ws://127.0.0.1:8000/body/ws`

## 3. Enter Play mode

When the scene starts, the bootstrap wires:

- AxiomBodyController
- AxiomBodyCommandRouter
- AxiomBodyWebSocketClient
- AxiomBodyEventEmitter

The body connects outward to the Mind host and emits `body.ready`.

For the first verification, optionally add `AxiomBodyConnectionDebug` to the same root. The Unity console will log CONNECTED/DISCONNECTED transitions.

## 4. First live commands

From the Mind host, execute in this order:

1. `body_status`
2. `body_capabilities`
3. `body_expression(expression="curious", intensity=0.55)`
4. `body_speak(text="Axiom body connection confirmed.", emotion="curious")`
5. `body_stop`

At v0.4 the body proves protocol execution and state changes. It intentionally does not yet provide a TTS provider, lip sync, or final facial blendshape mapping.

## 5. Acceptance criteria

The first live Unity milestone is complete when all are true:

- Unity logs a successful WebSocket connection.
- `body_status` returns `ready=true` and `connected=true`.
- `body_capabilities` returns the reference manifest.
- `body_expression` returns `success=true` and updates semantic body state.
- `body_speak` returns `success=true` and sets `IsSpeaking` when an Animator is present.
- `body_stop` returns `success=true` and clears speaking state.
- Disconnecting/restarting the Mind host causes Unity to reconnect automatically.

That proves the embodiment circuit before adding audio, blendshapes, vision, or hearing.
