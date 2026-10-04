# Unity Round-Trip Integration v0.3

## Goal

Prove this exact path before adding TTS, camera capture, or animation polish:

```text
Axiom Mind
  -> body_speak / body_status
  -> AxiomBodyService
  -> BodySessionManager
  -> /body/ws
  -> AxiomBodyWebSocketClient
  -> AxiomBodyCommandRouter
  -> AxiomBodyController
  -> result
  -> Mind
```

## Mind host

Install the bridge into the existing FastAPI application:

```python
body_session = BodySessionManager()
body_service = AxiomBodyService(body_session)
install_body_websocket(app, body_session)
register_body_tools(mcp, body_service)
```

The body connects to:

```text
ws://<mind-host>/body/ws?body_id=axiom.reference.unity
```

Use `wss://` when the host is exposed through HTTPS.

## Unity

The reference client is:

```text
Assets/AxiomBody/Scripts/AxiomBodyWebSocketClient.cs
```

It:

1. connects outward to the Mind host;
2. announces `body.ready`;
3. receives `axiom.body/0.1` commands;
4. moves command execution onto Unity's main thread;
5. routes semantic actions to `AxiomBodyController`;
6. sends the correlated result back;
7. reconnects after transport loss.

## Required Unity dependency

```text
com.unity.nuget.newtonsoft-json
```

This is required because `axiom.body/0.1` payloads are JSON objects. Unity's built-in
`JsonUtility` is deliberately not used for the wire protocol.

## First live test

With the Mind host running on port 8000 and the Unity scene in Play mode:

1. Unity should connect to `/body/ws`.
2. `body_status` should return `connected: true`.
3. `body_expression("curious")` should update body semantic state.
4. `body_speak("Hello")` should set `speaking: true` even before a TTS provider is installed.
5. `body_stop()` should clear speaking state.

At this stage "speak" proves control flow only. Audio/TTS is a separate adapter and should not be hardwired into the Body protocol.
