# Axiom Mind-side Body Adapter

This package exposes the stable Body contract to the Axiom Mind while keeping Unity implementation details outside cognition.

## Layers

```text
Reasoning Host / ChatGPT / Claude
            |
            v
        Axiom Mind
            |
        MCP Body tools
            |
     AxiomBodyService
            |
   BodySessionManager
            |
       WebSocket
            |
       Unity Body
```

The WebSocket is a reference transport only. The semantic Body contract remains transport-independent.

## MCP registration

```python
from axiom_body.mcp_tools import register_body_tools
from axiom_body.service import AxiomBodyService
from axiom_body.session import BodySessionManager

session = BodySessionManager()
service = AxiomBodyService(session)
register_body_tools(mcp, service)
```

## FastAPI/Unity bridge

```python
from axiom_body.fastapi_bridge import install_body_websocket

install_body_websocket(app, session, "/body/ws")
```

Unity connects to:

```text
wss://<mind-host>/body/ws?body_id=axiom.reference.unity
```

## Tool surface

- `body_status`
- `body_capabilities`
- `body_look_at`
- `body_expression`
- `body_gesture`
- `body_speak`
- `body_listen`
- `body_observe`
- `body_posture`
- `body_stop`

## Event direction

Unity sends result/event envelopes back on the same connection. `BodyEventBridge` can route `body.saw` and `body.heard` events into the Mind's evidence store and all body events into the journal.
