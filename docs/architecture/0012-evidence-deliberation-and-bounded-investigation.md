# ADR 0012: Evidence Deliberation and Bounded Investigation

**Status:** Accepted for initial implementation  
**Date:** September 18, 2026

## Context

The Mind can preserve semantically equivalent evidence, detect unresolved tension, and attach
separate Confidence, Weight, and provenance appraisals. The next requirement is not a winner
formula. It is the ability to determine what the evidence landscape looks like and what additional
evidence would materially improve understanding.

This is the point at which recall may need to go "down the rabbit hole": follow provenance, seek
corroboration, compare context and conditions, and determine whether an apparent contradiction is
actually temporal or contextual.

## Decision

For each unresolved semantic tension, the Memory Steward creates an `EvidenceDeliberation` and
stores it as a Steward-owned `evidence_deliberation` Memory Artifact.

The deliberation records:

- support count for the existing interpreted value;
- support count for the proposed interpreted value;
- observed provenance relationship: `overlap_detected`, `no_overlap_observed`, or `unknown`;
- provenance-chain depth for each primary evidence item;
- missing appraisal information;
- material context or source-condition differences; and
- concrete investigation questions.

The same deliberation is written into the Tension journal experience and returned through MCP as
part of the Memory Steward decision.

## Corroboration is not voting

Support counts describe how many distinct durable evidence memories currently support each
interpreted value. They do not select a winner.

Ten repetitions of one upstream source may be weaker than one independent first-party observation.
Likewise, a higher count does not override provenance, Confidence, Weight, context, temporal
applicability, or other evidence dimensions.

## Provenance overlap is directional evidence, not proof

`overlap_detected` means the known provenance chains share at least one normalized source label.

`no_overlap_observed` means only that no shared source is visible in the currently known chains. It
must not be interpreted as proof that the evidence is independent. The Steward therefore asks the
Conscious Workspace to verify apparent independence when that distinction matters.

`unknown` means one or both sides lack enough provenance to compare.

## Bounded investigation

The Conscious Workspace should pursue the Steward's investigation questions when answering them can
materially change or clarify the conclusion. Findings that materially matter are returned as
current evidence with their own appraisal.

Investigation stops when:

- the material gaps have been addressed sufficiently for the present decision;
- further evidence is unlikely to change or clarify the conclusion; or
- no additional material evidence is reasonably available.

This is not an instruction to research indefinitely.

## Recall continuity

Investigation guidance remains attached to the durable memory that carries the unresolved tension.
When that memory is recalled later, the Memory Steward includes the outstanding investigation
questions in its summary so unfinished evidence work is not silently forgotten.

## No resolution rule

This slice still does not combine Confidence and Weight, compute a truth score, apply majority vote,
or select an authoritative value. It maps the evidence and identifies the next useful investigation.

## Consequences

- The Mind can distinguish 'I have conflicting evidence' from 'I know what to investigate next.'
- Corroboration becomes visible without becoming a voting mechanism.
- Provenance chains can trigger deeper source-of-source investigation.
- Context and source-condition differences can be examined before labeling evidence contradictory.
- Unfinished investigation survives across reasoning-engine and interaction boundaries.
- A later resolution mechanism can consume a richer evidence map instead of raw scalar scores.
