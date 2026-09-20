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

Continuous camera frames, microphone buffers, and other unselected sensory streams are transient.

When the Mind deliberately **sees** or **hears**, the exact observation admitted into cognition is
preserved as immutable sensory evidence before interpretation. Evidence remains distinct from
memory: the Memory Steward still decides whether any interpreted conclusion becomes durable
cognitive memory.

This preserves one memory authority while retaining the source evidence needed for later
re-evaluation.

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
- Mind/Body perception bridge — implemented in [0008 — Mind ↔ Body Integration V0.1](0008-mind-body-integration-v0.1.md).

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


## Implemented Mind ↔ Body loop

[0008 — Mind ↔ Body Integration V0.1](0008-mind-body-integration-v0.1.md) connects transient
Eyes/Ears percepts to Mind-side interpretation, the existing CognitiveCore and Memory Steward,
then returns conscious expression through Mouth and Face.


## Implemented sensory evidence slice

[0010 — Sensory Evidence Artifacts V0.1](0010-sensory-evidence-v0.1.md) preserves deliberate
See/Hear observations as immutable, content-addressed evidence before interpretation while leaving
continuous sensory streams transient.
