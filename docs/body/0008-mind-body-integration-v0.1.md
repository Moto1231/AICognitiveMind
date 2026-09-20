# Mind ↔ Body Integration V0.1

**Status:** First complete sensory-expression loop.

## Purpose

This slice connects the already-existing Mind and Body without moving cognitive authority into the
Body.

The Body still owns device interaction. The Mind still owns interpretation, reasoning, memory
governance, and continuity.

```text
camera / microphone
        ↓
       Body
        ↓
     Percept
        ↓
Mind-side interpretation
        ↓
CognitiveCore
        ↓
Memory Steward + reasoning
        ↓
response text
        ↓
BodyRuntime.express()
      ↙             ↘
   Mouth             Face
    ↓                 ↓
speakers             avatar
```

## New integration boundary

`MindBodyBridge` coordinates the loop.

It does not own identity, durable memory, or device state. It connects:

- `BodyRuntime.see()` / `BodyRuntime.hear()`;
- a Mind-side `PerceptInterpreter`;
- the existing `CognitiveCore.interact()` path;
- `BodyRuntime.express()`.

## Sensory interpretation

Interpretation belongs to the Mind, not to Eyes or Ears.

When an OpenAI API key is configured:

- a visual percept is sent as image input to the configured reasoning model;
- an audio percept is transcribed by the configured transcription model;
- the resulting interpretation becomes the conscious input.

When no OpenAI API key is configured, a summary interpreter preserves the architecture and allows
the loop to run deterministically, but it does not claim semantic understanding of the raw media.

## Evidence, memory, and journal boundary

Continuous camera/microphone streams remain transient.

A deliberate **See** or **Hear** operation changes the status of the exact observation that enters
cognition: before interpretation, its media bytes are preserved as an immutable sensory evidence
artifact with capture time, source, media type, byte length, and SHA-256 content hash.

The journal first records a `sensory_evidence` admission event containing the artifact reference.
The later interaction journal entry records that same reference alongside the Mind-side
interpretation and response. Raw media bytes are kept in the evidence store, not embedded in the
journal.

Evidence is not memory. The interpreted perception still goes through the same Memory Steward path
as any other conscious input. The Memory Steward remains the sole authority deciding whether a
semantic conclusion from sensory evidence becomes durable cognitive memory.

See [0010 — Sensory Evidence Artifacts V0.1](0010-sensory-evidence-v0.1.md).

## Expression return

After the conscious workspace produces a response, `MindBodyBridge` calls
`BodyRuntime.express()`.

That queues the same response into:

- Mouth as a VOICE `ExpressionIntent`;
- Face as an AVATAR `ExpressionIntent`.

The browser consumes those transient outputs and drives the local speakers and VRM avatar.

## Live Body surface

The integrated proof surface is:

```text
/body/live
```

It loads Genesis and exposes two sensory actions:

- **See through camera**
- **Listen for 5 seconds**

A completed circuit reports:

```text
MIND ↔ BODY LOOP COMPLETE
```

and shows both the Mind-side sensory interpretation and the final response.

## V0.1 success criterion

The integration is proven when either a camera frame or microphone clip:

1. enters as a transient Body `Percept`;
2. is preserved as immutable sensory evidence;
3. receives a journaled evidence-admission record;
4. is interpreted on the Mind side;
5. passes through `CognitiveCore` and the Memory Steward;
6. is journaled with an evidence reference;
7. produces a conscious response;
8. returns through Mouth and Face.

## Deliberately not included yet

- continuous autonomous sensing;
- wake-word activation;
- persistent live video or audio;
- automatic gaze toward perceived objects;
- semantic facial-expression selection;
- lip synchronization;
- interruption / turn-taking policy;
- background sensory attention;
- autonomous decisions about when to look or listen.

Those belong after the first full loop is proven on actual hardware.
