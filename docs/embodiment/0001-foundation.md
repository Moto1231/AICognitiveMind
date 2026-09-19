# Embodiment Workstream — Foundation

**Status:** Parallel active workstream  
**Relationship to Cognitive Mind:** Faculty of the same whole, not a second identity or agent.

## Purpose

The Embodiment workstream gives the persistent Cognitive Mind a sensory and expressive presence:

- **eyes** — camera / visual perception
- **ears** — microphone / acoustic perception
- **mouth** — speech output
- **face/body** — on-screen avatar and visible expression
- **environment interface** — screen/computer state and later physical-device access

The architectural invariant is:

> There is one being. Embodiment is how that being perceives and expresses itself.

## Boundary

The Embodiment layer does **not** own:

- identity
- durable memory
- beliefs
- values
- continuity
- Memory Steward policy

Those remain owned by the Cognitive Mind.

Embodiment owns:

- device access
- raw sensor streams
- transient percept formation
- output rendering
- avatar state
- speech playback
- device lifecycle and health

## Initial flow

```text
Camera / Microphone / Screen
          ↓
     Sensor Adapters
          ↓
   transient Percepts
          ↓
 Perception Interpretation
          ↓
 Conscious Workspace / Mind
          ↓
       Response
          ↓
 Expression Intent
      ↙        ↘
    Voice      Avatar
```

## Critical memory rule

Raw sensory media is not durable memory by default.

A camera frame, microphone buffer, or screen image is transient sensory input. Only interpreted experience that passes through normal cognitive governance may become durable memory.

This prevents the body from bypassing the Memory Steward.

## V0 target

A desktop embodiment running beside the Cognitive Mind with:

1. webcam input;
2. microphone input;
3. speaker / text-to-speech output;
4. simple 2D on-screen avatar;
5. device-status reporting;
6. transient sensory events exposed to the reasoning host;
7. no autonomous background recording;
8. no direct durable-memory writes.

## Provider-neutral device contracts

Hardware and media vendors must remain replaceable.

The core contracts are:

- `VisionSensor`
- `AudioSensor`
- `VoiceOutput`
- `AvatarOutput`

Concrete adapters may later target browser APIs, desktop APIs, cloud speech services, local speech services, or dedicated hardware without changing the Mind.

## Parallel-work rule

The Embodiment branch is intentionally independent of ongoing cognitive development.

Changes should integrate through narrow contracts rather than editing Memory Steward internals unless a real integration requirement proves necessary.

This allows:

```text
Cognitive workstream ───────┐
                            ├── one Digital Being
Embodiment workstream ──────┘
```

## First implementation slice

The foundation slice defines:

- sensory modality models;
- transient percept models;
- expression-intent models;
- device protocols;
- a small embodiment runtime that can attach devices without owning cognition.

No camera, microphone, speech, or avatar vendor dependency is selected in the foundation slice.

The next implementation slices can proceed independently:

- vision adapter;
- audio-input adapter;
- speech-output adapter;
- avatar renderer;
- perception bridge into the reasoning host.
