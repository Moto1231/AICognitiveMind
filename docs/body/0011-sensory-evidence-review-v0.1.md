# Mind ↔ Body — Sensory Evidence Review V0.1

**Status:** Focused re-examination of preserved sensory evidence.

## Purpose

Sensory Evidence Artifacts V0.1 preserved the exact image/audio admitted into cognition.

Evidence Review V0.1 gives the conscious reasoning process a way to return to that original media
when a prior interpretation is uncertain, contradicted, incomplete, or materially important.

The key rule is:

> Review creates a new interpretation. It never rewrites the evidence or silently replaces the old interpretation.

## Flow

```text
recalled memory / journal
        ↓
evidence reference
SHA-256 + captured_at
        ↓
sensory_evidence_review
        ↓
retrieve exact artifact
        ↓
verify SHA-256 + byte length
        ↓
focused reinterpretation
        ↓
evidence_review journal event
        ↓
Memory Steward current-evidence path
        ↓
reasoning / possible belief revision
```

## Tool

The conscious reasoning process receives:

```text
sensory_evidence_review
```

Required arguments:

- `sha256`
- `captured_at`
- `focus`

The focus must state the specific uncertainty being examined.

Examples:

- check whether the sign says October 8 or October 18;
- check whether the speaker said Tuesday or Thursday;
- inspect whether the observed object was actually red;
- re-examine a detail that a later contradiction made important.

## Evidence integrity

Before reinterpretation the tool:

1. retrieves the artifact by SHA-256 and exact capture time;
2. decodes the stored media;
3. recalculates SHA-256;
4. verifies byte length;
5. refuses review if integrity verification fails.

The evidence artifact itself has no update operation.

## Focused interpretation

For vision, the review focus is included in the image-interpretation request so the Mind can inspect
a specific visual detail rather than merely repeat a generic caption.

For audio, the original clip is transcribed again from the preserved bytes. The conscious reasoning
process receives that fresh transcription together with the explicit review focus and can compare it
with the earlier interpretation.

## Recall path

The Memory Steward now carries exact sensory evidence references with recalled journal experiences.

A recalled experience may therefore contain:

```json
{
  "evidence_references": [
    {
      "sha256": "...",
      "captured_at": "...",
      "modality": "vision",
      "source": "browser-camera",
      "media_type": "image/jpeg",
      "byte_length": 12345
    }
  ]
}
```

The raw media is never placed into recall context.

## Journal history

A successful review produces an append-only `evidence_review` journal entry containing:

- the exact evidence reference;
- review focus;
- integrity-verification result;
- new interpretation.

The original `sensory_evidence` admission and original interaction remain unchanged.

This means the history can contain:

```text
Evidence E
  ├─ Interpretation A at initial observation
  ├─ Interpretation B after focused review
  └─ Interpretation C after later review
```

without pretending those interpretations are the same thing as the evidence.

## Memory Steward boundary

A review result is current evidence, not automatic truth.

If the conscious reasoning process materially uses a review result, it must submit that result to
the Memory Steward through `consider_evidence`.

The Steward continues to own:

- evidence appraisal;
- confidence;
- weight;
- provenance reasoning;
- semantic tension;
- belief transition;
- durable memory.

## V0.1 success criterion

Evidence Review V0.1 is proven when the Mind can:

1. recall an exact sensory evidence reference;
2. retrieve the original media;
3. verify content integrity;
4. request focused re-examination;
5. retain the new interpretation as a separate journal event;
6. route materially relevant review findings through the Memory Steward;
7. leave the original evidence and prior interpretation unchanged.

## Deliberately not included yet

- automatic evidence review on every recall;
- autonomous recursive review without a material question;
- comparison UI showing multiple interpretations side by side;
- automatic confidence recalculation from media alone;
- video-frame navigation;
- waveform/timecode targeting;
- speaker identification;
- automatic belief revision.

Those can build on this review contract later.
