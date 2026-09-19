# ADR 0009: Semantic Interpretation and Equivalence

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

Durable memories preserve evidence in the wording in which the Mind learned it. Literal wording alone
is not sufficient to determine whether two memories express the same underlying proposition.

For example, "The user's birthday is February 7" and "Will's birthday is February 7" may be
different evidence statements about the same underlying fact when the reasoning context establishes
that Will is the current human.

## Decision

The Memory Artifact mechanism defines an initial artifact convention named
`semantic_interpretation`.

Its payload uses:

- `subject` — the interpreted subject;
- `attribute` — the property or relation being asserted; and
- `value` — the interpreted value.

This is an artifact-level convention, not a relational database schema. The durable memory remains
the evidence document.

The connected reasoning host may propose a semantic interpretation when the evidence supports one.
The Memory Steward materializes the artifact and compares its normalized interpretation with
semantic interpretations already present on durable memories.

When two differently worded memories have the same semantic interpretation, the Steward:

1. preserves the new memory as separate evidence;
2. adds a Steward-owned `semantic_equivalence` artifact to the new memory; and
3. identifies the earlier evidence content that supported the equivalence judgment.

Exact duplicate durable-memory wording remains redundant and may be rejected; the repeated
interaction is still retained in the journal.

## Non-decision: contradiction

Matching subject and attribute with a different value is **not** semantic equivalence.

This slice does not decide which value is true, newer, stronger, or more authoritative. Such evidence
is preserved without an equivalence annotation and will be handled by a separate contradiction/tension
mechanism using provenance, confidence, weight, temporal context, and other evidence.

## Consequences

- The Mind can distinguish wording from interpreted meaning.
- Repeated knowledge can become corroborating evidence without collapsing its history.
- Semantic equivalence is determined by the Steward, not by database identity or string similarity.
- Evidence remains inspectable in its original wording.
- The Memory Inspector can show the interpretation and equivalence artifacts without a schema migration.
