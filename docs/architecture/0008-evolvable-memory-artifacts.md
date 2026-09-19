# ADR 0008: Evolvable Memory Artifacts

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

The Memory Steward needs to interpret evidence beyond its surface wording. Future distinctions may
include evidentiary role, semantic equivalence, contradiction, corroboration, temporal context,
provenance interpretation, confidence, weight, and other cognitive structure that has not yet been
discovered.

Encoding each new distinction as a permanent top-level memory field or relational proposition model
would require the designers to predict the final cognitive representation in advance.

## Decision

A durable memory may carry zero or more **Memory Artifacts**.

An artifact is a Steward-owned annotation with:

- a `kind`, identifying the interpretation being represented;
- an open-ended `payload`, whose structure is defined by that artifact kind;
- `formed_at`, recording when the annotation was formed; and
- `formed_by`, recording the cognitive role that materialized it.

Artifacts are embedded in the whole durable memory document. They do not receive domain IDs and do
not create a second relational memory model.

The connected reasoning host may propose artifacts along with a memory proposal. A proposal is not a
write. The Memory Steward decides whether the memory is accepted and materializes accepted artifacts
under Steward authority.

Human administrative edits to ordinary memory fields do not silently rewrite Steward artifacts.

## Important distinction

The original memory remains evidence. An artifact is an interpretation **of** that evidence.

An artifact must therefore not replace or rewrite the remembered statement merely because the
Steward has formed an interpretation of it. Later evidence may support a different interpretation,
and the architecture must retain enough provenance to understand why.

## Initial use

The mechanism is intentionally general before any fixed artifact taxonomy is declared.

Likely early uses include:

- `evidentiary_role`;
- `semantic_interpretation`;
- `semantic_equivalence`;
- `contradiction`;
- `corroboration`;
- future confidence and weight observations.

These names are examples, not a closed schema.

## Compatibility

Existing durable memories without an `artifacts` field remain valid and are interpreted as having an
empty artifact collection.

MongoDB and SurrealDB both persist artifacts as part of the whole memory document.

## Consequences

- Cognitive representation can evolve without repeated database redesign.
- Evidence remains distinct from interpretation.
- The Memory Steward owns durable annotations even when a reasoning host proposed them.
- The system avoids introducing domain IDs solely to support annotations.
- Future semantic interpretation can be developed incrementally and tested through the existing
  Memory Inspector.
