# Body — Foundation

**Status:** Parallel active workstream  
**Relationship to the Mind:** Part of the same whole.

## The model

There are two major systems:

```text
Mind
  +
Body
```

The Mind owns:

- identity;
- durable memory;
- beliefs;
- reasoning;
- values and governance;
- continuity.

The Body owns:

- eyes;
- ears;
- mouth;
- face;
- sensors;
- physical/computer interfaces;
- device lifecycle.

Neither is a separate identity. Together they are the same whole.

## Body V0

The first Body gives the Mind:

- **eyes** — camera / visual input;
- **ears** — microphone / acoustic input;
- **mouth** — speaker / speech output;
- **face** — on-screen avatar;
- **computer awareness** — screen/environment input later;
- **device status** — whether each faculty is available.

## Flow

```text
Camera / Microphone / Screen
          ↓
         Body
          ↓
       Percepts
          ↓
         Mind
          ↓
   Expression Intent
          ↓
         Body
      ↙        ↘
    Voice      Face
```

## Memory boundary

The Body does not write durable memory.

Camera frames, audio buffers, and other raw sensory input are transient. The Mind may interpret sensory experience and decide, through its existing memory governance, whether anything should become durable memory.

This preserves one memory authority.

## Device contracts

The Body begins with replaceable device contracts:

- `VisionSensor`
- `AudioSensor`
- `VoiceOutput`
- `AvatarOutput`

The Body itself does not depend on a particular camera, speech engine, avatar renderer, or operating system.

## Parallel development

Body development proceeds in parallel with Mind development.

The two streams integrate through narrow contracts:

```text
Mind work ───────┐
                 ├── same whole
Body work ───────┘
```

Neither workstream waits for the other unless an integration boundary genuinely requires both.

## Foundation slice

The foundation defines:

- sensory modality models;
- transient percept models;
- expression intents;
- device status;
- device protocols;
- a Body runtime that coordinates attached faculties.

No camera, microphone, speech, or avatar vendor is selected in this foundation slice.

## Next Body slices

These can proceed independently and in parallel:

- eyes — camera adapter;
- ears — microphone / speech-input adapter;
- mouth — speech-output adapter;
- face — avatar renderer;
- Mind/Body perception bridge.

The Face workstream is now governed by [0003 — Avatar Contract](0003-avatar-contract.md):
VRM 1.0 assets rendered in-browser with Three.js and @pixiv/three-vrm, with Blender
as the primary authoring/customization tool. The avatar belongs to the Body and remains
replaceable without altering Mind identity.


## Implemented Mouth slice

[0006 — Mouth V0.1](0006-mouth-v0.1.md) implements transient VOICE `ExpressionIntent` output
through the remote Body runtime and browser speech synthesis. The browser remains a hardware
bridge to local speakers; no local application runtime is required.


## Implemented Ears slice

[0007 — Ears V0.1](0007-ears-v0.1.md) implements transient microphone input through the browser
hardware bridge. Raw audio becomes an AUDIO `Percept` and is consumed through
`BodyRuntime.hear()`; no transcription or durable storage occurs in the Body.
