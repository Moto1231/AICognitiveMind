# Body — Sensory Evidence Artifacts V0.1

**Status:** Durable evidence layer for deliberate See/Hear observations.

## Corrected boundary

The earlier Body rule treated all raw sensory media as transient. That was too broad.

The corrected rule is:

> Continuous sensory streams are transient. The exact observation deliberately admitted into cognition becomes durable evidence.

This distinguishes three layers:

```text
raw sensory stream
      ↓
deliberate observation
      ↓
Sensory Evidence Artifact
      ↓
Mind-side interpretation
      ↓
Memory Steward / belief / response
```

Evidence is not interpretation, and interpretation is not memory.

## What becomes an evidence artifact

Today:

- **See** admits the JPEG frame actually sent for visual interpretation.
- **Hear** admits the recorded audio clip actually sent for transcription.

The artifact is preserved **before** interpretation begins.

If interpretation fails, the evidence still exists and its admission remains journaled.

When Eyes later admits a short video clip rather than a still frame, that exact video clip should
be preserved through the same contract. V0.1 does not fabricate video evidence for a visual
operation that currently interpreted only one image frame.

## Artifact contents

Each `SensoryEvidenceArtifact` contains:

- capture timestamp;
- sensory modality;
- Body source;
- media type;
- SHA-256 content hash;
- exact byte length;
- exact media payload encoded as base64;
- physical capture metadata such as dimensions or duration.

There is no artificial cognitive primary key.

The durable reference is content-addressed by SHA-256 together with capture time, which preserves
the distinction between identical media observed at different moments.

## Immutability

Evidence storage exposes only:

- `preserve()`;
- exact retrieval by SHA-256 and capture time.

There is no update operation.

If the same exact hash/capture-time pair is preserved again, the existing artifact is returned.

## Journal provenance

Before interpretation, `MindBodyBridge` writes a `sensory_evidence` journal entry with:

- admission status;
- Body source;
- evidence reference;
- safe capture metadata.

After interpretation, the normal interaction journal entry includes the same evidence reference
inside the input context.

Raw media bytes are not copied into journal documents.

## Evidence retrieval

The authenticated application exposes:

```text
GET /v1/evidence/{sha256}?captured_at=<timestamp>
GET /v1/evidence/{sha256}/metadata?captured_at=<timestamp>
```

The first returns the original media bytes with their media type.

The second returns the immutable evidence reference.

The whole Render application remains protected by the existing application access authentication.

## Live Body

After a completed See/Hear cycle, `/body/live` displays:

- media type;
- SHA-256;
- capture time;
- a direct authenticated link to the preserved visual or audio evidence.

This makes the distinction visible:

```text
Evidence:
  what physically entered cognition

Interpretation:
  what the Mind currently thinks it means

Response / memory:
  what cognition did with that interpretation
```

## Storage

The current Atlas implementation stores the bounded V0.1 media artifact in the `evidence`
collection.

Current sensory limits keep artifacts below MongoDB's single-document size ceiling:

- Eyes: bounded JPEG observation;
- Ears: maximum 30-second / 8 MB audio observation.

Longer video evidence should move to a large-object mechanism such as GridFS or object storage while
keeping the same evidence-reference contract.

## Re-evaluation

V0.1 preserves and retrieves the original evidence needed for future reconsideration.

A later slice should give the reasoning process an explicit evidence-review tool so, when a memory
or interpretation is challenged, the Mind can deliberately retrieve and reinterpret the original
artifact rather than trusting only the prior transcription or description.

## Memory authority

Preserving evidence does **not** allow the Body to write cognitive memory.

The Memory Steward remains responsible for deciding whether an interpretation, fact, relationship,
or belief should influence the Mind beyond the immediate interaction.
