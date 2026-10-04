# Axiom Body Message Contract v0.1

This contract sits between the Mind-side Body service and a concrete body runtime such as Unity.

## Command envelope

```json
{
  "protocol": "axiom.body/0.1",
  "message_type": "command",
  "command_id": "cmd_01",
  "body_id": "axiom.reference.unity",
  "action": "expression",
  "payload": {
    "expression": "curious",
    "intensity": 0.65
  }
}
```

Required fields:
- `protocol`
- `message_type`
- `command_id`
- `body_id`
- `action`
- `payload`

Initial actions:
- `connect`
- `disconnect`
- `status`
- `capabilities`
- `presence`
- `look_at`
- `expression`
- `gesture`
- `speak`
- `listen`
- `observe`
- `posture`
- `stop`

## Result envelope

```json
{
  "protocol": "axiom.body/0.1",
  "message_type": "result",
  "command_id": "cmd_01",
  "body_id": "axiom.reference.unity",
  "success": true,
  "code": "OK",
  "payload": {}
}
```

## Event envelope

```json
{
  "protocol": "axiom.body/0.1",
  "message_type": "event",
  "event_id": "evt_01",
  "body_id": "axiom.reference.unity",
  "event": "body.speech_finished",
  "occurred_at": "2026-09-21T20:00:00-05:00",
  "payload": {}
}
```

## Evidence event

Evidence-producing sensors attach an artifact reference rather than replacing the artifact with a summary.

```json
{
  "protocol": "axiom.body/0.1",
  "message_type": "event",
  "event_id": "evt_02",
  "body_id": "axiom.reference.unity",
  "event": "body.saw",
  "occurred_at": "2026-09-21T20:00:02-05:00",
  "payload": {
    "artifact_id": "vision_23871",
    "artifact_type": "image",
    "summary": "A person is seated in front of the display.",
    "confidence": 0.96
  }
}
```

## Boundary

MCP tools map to these semantic messages. Unity does not need to know which reasoning host invoked the Mind, and the reasoning host does not need to know how Unity animates the body.
