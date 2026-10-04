# Unity Reference Body - v0.3

## Required Unity package

The wire implementation uses Unity's maintained Newtonsoft JSON package:

```text
com.unity.nuget.newtonsoft-json
```

Add it with Package Manager before compiling these scripts.

## Scene wiring

Create or use your Axiom root GameObject and attach:

1. `AxiomBodyController`
2. `AxiomBodyCommandRouter`
3. `AxiomBodyWebSocketClient`
4. `AxiomBodyEventEmitter`

Assign the Controller to the Router, and the Router to the WebSocket Client.
Assign the WebSocket Client to the Event Emitter.

The default Mind endpoint is:

```text
ws://127.0.0.1:8000/body/ws
```

Change this in the Inspector if the Mind host runs elsewhere.

## What works in v0.3

The client connects outward, announces `body.ready`, receives semantic commands,
routes them on Unity's main thread, and returns protocol results. It automatically
reconnects after connection loss.

This transport intentionally knows nothing about ChatGPT, MCP, memory, or reasoning.

## v0.4 drop-in bootstrap

For a new scene, the preferred setup is now simpler:

1. Put the approved Axiom model under one root GameObject.
2. Add `AxiomBodyBootstrap` to that root.
3. Set the Mind WebSocket URL if it is not the default.
4. Enter Play mode.

The bootstrap adds and wires the controller, router, WebSocket transport and event emitter. It never changes the visual character design.

For first-run diagnostics, add `AxiomBodyConnectionDebug` to the same root.
