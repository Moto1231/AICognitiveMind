# Axiom Body API Contract v0.1

**Purpose:** Semantic interface between an Axiom Mind and an embodiment.  
**Reference implementation:** Unity  
**Transport:** MCP-first  
**Rule:** The Mind communicates intent; the Body determines implementation.

## 1. Discovery

Required operations:
- `body.connect`
- `body.disconnect`
- `body.get_identity`
- `body.get_capabilities`
- `body.get_state`

Example identity:

```json
{
  "body_id": "axiom.reference.unity",
  "name": "Axiom Reference Body",
  "body_type": "virtual_avatar",
  "provider": "Axiom",
  "version": "0.1.0"
}
```

Example capabilities:

```json
{
  "speech": true,
  "hearing": true,
  "vision": true,
  "gaze": true,
  "facial_expression": true,
  "gesture": true,
  "locomotion": false,
  "tail_expression": true,
  "ear_expression": true,
  "touch": false
}
```

A Mind must query capabilities rather than assume them.

## 2. Presence

`body.set_presence`

```json
{
  "presence": "attentive",
  "intensity": 0.7
}
```

Initial vocabulary:
- neutral
- attentive
- relaxed
- engaged
- thinking
- concerned
- excited
- sleeping

## 3. Attention and gaze

`body.look_at`

```json
{
  "target": { "type": "person", "id": "user" },
  "intensity": 0.8
}
```

Target types:
- person
- object
- screen_position
- world_position
- camera
- none

`body.set_attention`

Modes:
- observe
- listen
- inspect
- follow
- ignore

## 4. Expression

`body.set_expression`

```json
{
  "expression": "curious",
  "intensity": 0.65,
  "duration_ms": 2500
}
```

Baseline vocabulary:
- neutral
- happy
- amused
- curious
- thinking
- concerned
- surprised
- determined
- confused
- sad

Unsupported expressions should map to the closest supported expression instead of hard-failing.

## 5. Gesture

`body.gesture`

Reference gestures:
- acknowledge
- wave
- point
- nod
- shake_head
- shrug
- celebrate
- invite
- present
- stop

## 6. Speech

`body.speak`

```json
{
  "text": "I found something you may want to look at.",
  "voice": "default",
  "emotion": "curious",
  "attention_target": { "type": "person", "id": "user" }
}
```

The body owns:
- text-to-speech
- playback
- lip sync
- facial movement
- breathing
- speech gestures
- gaze behavior

Speech controls:
- `body.pause_speech`
- `body.resume_speech`
- `body.stop_speech`

## 7. Hearing

`body.listen`

Modes:
- conversation
- ambient
- command
- off

Hearing produces evidence artifacts. Example event:

```json
{
  "event": "body.heard",
  "artifact_id": "audio_83721",
  "transcript": "Do you remember where we left off?",
  "confidence": 0.94,
  "speaker": { "id": "user" }
}
```

The raw artifact remains independently addressable.

## 8. Vision

`body.observe`

Modes:
- current_view
- snapshot
- inspect_target
- continuous

Vision also produces evidence artifacts rather than only interpreted text.

## 9. Posture

`body.set_posture`

Initial postures:
- stand
- sit
- rest
- sleep

## 10. Stop

`body.stop` halts voluntary body action. This must not be used as a replacement for application shutdown or emergency process termination.

## 11. Body state

`body.get_state`

```json
{
  "ready": true,
  "connected": true,
  "presence": "attentive",
  "expression": "curious",
  "posture": "standing",
  "speaking": false,
  "listening": true,
  "moving": false,
  "attention": { "type": "person", "id": "user" },
  "sensors": {
    "vision": "available",
    "hearing": "active"
  }
}
```

Do not expose Unity-internal animator IDs, transform values, blendshape weights, shader parameters, frame rate, or NavMesh state through the public semantic contract.

## 12. Events

Initial event vocabulary:
- `body.ready`
- `body.speech_started`
- `body.speech_finished`
- `body.speech_interrupted`
- `body.heard`
- `body.saw`
- `body.attention_changed`
- `body.movement_started`
- `body.movement_completed`
- `body.movement_blocked`
- `body.contact`
- `body.capability_changed`
- `body.error`

## 13. Evidence artifacts

Minimum artifact types:
- audio
- image
- video
- sensor
- interaction

Perception pipeline:

```text
Body
 ↓
Evidence Artifact
 ↓
Perception / Interpretation
 ↓
Conscious Workspace
 ↓
Memory Steward
 ↓
Memory, if warranted
```

This preserves the distinction between what happened, what the Mind interpreted, and what the Mind later remembers.

## 14. Errors

Standard semantic errors:
- BODY_NOT_READY
- CAPABILITY_UNAVAILABLE
- TARGET_NOT_FOUND
- ACTION_BLOCKED
- ACTION_INTERRUPTED
- INVALID_INTENT
- SENSOR_UNAVAILABLE
- INTERNAL_BODY_ERROR

## 15. Initial MCP surface

Keep v0.1 deliberately small:
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

Locomotion is intentionally deferred from v0.1.

## 16. Avatar pack contract

A third-party body pack implements:
- Body Identity
- Capability Manifest
- Body Command Adapter
- Body Event Adapter
- Rig/Animation Implementation
- Materials
- Assets

The Mind does not change when the body changes.

## Governing test

> Could a completely different body implement this command without knowing anything about our Unity character?

If yes, it probably belongs in the Body API. If no, it probably belongs inside the Unity reference implementation.
