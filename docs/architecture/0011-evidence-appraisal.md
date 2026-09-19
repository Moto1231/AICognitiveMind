# ADR 0011: Evidence Appraisal — Provenance, Confidence, and Weight

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

The Mind can now preserve semantically equivalent evidence and detect unresolved tension between
competing values. It still needs a way to describe why one piece of evidence may deserve more or
less belief or influence than another.

The checkpoint established three essential dimensions:

- provenance: where the information came from, under what context and condition, and where that
  source obtained it when the chain is known;
- confidence: how strongly the evidence is believed; and
- weight: how much significance or influence that evidence deserves in the relevant deliberation.

Confidence and Weight are related but not interchangeable.

## Decision

Define a structured `EvidenceAppraisal` with:

- `confidence`: normalized from 0 to 1;
- `weight`: normalized from 0 to 1;
- `provenance`: one or more ordered provenance hops; and
- optional `basis`: concise reasons supporting the appraisal.

Each provenance hop records:

- `source`;
- optional `context`; and
- optional `condition`.

The chain is ordered from the immediate source presented to the Mind outward through upstream
sources. This allows evidence such as 'A told B, who told the Mind' to preserve the context and
condition of both A and B without flattening them into one source label.

## Two appraisal locations

The same appraisal structure is used in two distinct cognitive locations:

1. **Long-term memory appraisal** — stored as a Steward-owned `evidence_appraisal` Memory Artifact
   on durable memory.
2. **Current evidence appraisal** — stored on a `ResearchObservation` supplied during the active
   interaction and retained in the interaction's Memory Steward trace.

This keeps recalled long-term memory evidence separate from evidence newly supplied to the
Conscious Workspace while allowing later comparison between them.

## No combined score

This slice intentionally defines no normalized function that combines Confidence and Weight.

A value with high Confidence but low Weight is meaningfully different from evidence with low
Confidence but high Weight. Collapsing the dimensions now would discard information before the
Mind has developed the evidence-resolution process needed to interpret them responsibly.

Likewise, higher numeric values do not automatically resolve semantic tension. Provenance, source
conditions, temporal applicability, corroboration, context, and reflective reasoning may all
matter.

## Search and inspection

Evidence appraisal remains part of the whole memory/evidence document. The portal renders
Confidence, Weight, and provenance explicitly, and full-collection search includes provenance
content across both MongoDB and SurrealDB storage paths.

## Consequences

- The Mind can compare evidence dimensions without yet choosing a winner.
- Source chains can preserve source-of-source context rather than losing it in a flat citation.
- Current evidence and long-term memory can carry comparable but distinct scorecards.
- The representation remains compatible with the evolvable Memory Artifact architecture.
- Later tension resolution can build on these dimensions without changing the evidence documents.
