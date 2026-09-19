# ADR 0013: Tension Re-deliberation from Current Evidence

**Status:** Accepted for initial implementation  
**Date:** September 18, 2026

## Context

The Mind can detect semantic tension, appraise evidence, and generate bounded investigation
questions. The missing loop is what happens after the Conscious Workspace follows those questions
and returns with new evidence.

Current research evidence must be able to change the Mind's understanding of an unresolved tension
without silently becoming durable semantic memory and without erasing the reasoning history that
produced the earlier deliberation.

## Decision

A `ResearchObservation` may carry an optional semantic interpretation:

- `subject`;
- `attribute`; and
- `value`.

When current evidence is semantically linked to one of the competing values in a recalled unresolved
tension, the Memory Steward re-deliberates that tension.

Re-deliberation recalculates the evidence map using:

- durable evidence already supporting each side;
- semantically linked current evidence gathered during the interaction;
- available provenance chains;
- separate Confidence and Weight appraisals;
- source context and condition differences; and
- unresolved appraisal or corroboration gaps.

## Deliberation revisions

Each new deliberation is appended as a new Steward-owned `evidence_deliberation` artifact on the
durable memory carrying the tension. Earlier deliberation artifacts are retained.

Each deliberation records a monotonically increasing `revision` and a `trigger`:

- `tension_detected` for the initial evidence map; or
- `current_evidence_reassessment` when a previously existing tension is reconsidered using newly
  supplied current evidence.

Recall uses the latest deliberation revision for active investigation guidance while preserving older
revisions for audit and developmental history.

## Current evidence remains current evidence

Research observations used in re-deliberation are recorded in the interaction trace and in a
`tension` journal experience whose phase is `reassessment`.

They are **not** automatically promoted to durable semantic memory. If a finding deserves durable
retention as knowledge, the connected reasoning host must separately propose it and the Memory
Steward must accept that proposal through the normal memory path.

## Transaction boundary

Re-deliberation may occur several times during one interaction as evidence is gathered.

The Memory Steward maintains a working view of the revised durable memory during the interaction.
The final artifact history is persisted through the storage-neutral `replace_exact` contract only
when the Steward completes the interaction. This preserves MongoDB/SurrealDB parity and prevents a
partially completed reasoning turn from silently changing durable deliberation state.

Each reassessment is also journaled with the evidence snapshot available at that point, so successive
revisions show how the evidence map changed rather than reconstructing history from the final state.

## No resolution

Re-deliberation still does not select an authoritative value. Increased corroboration, higher
Confidence, higher Weight, deeper provenance, or a newer observation may alter the evidence map and
the remaining investigation questions, but none of those facts alone is a resolution rule.

## Consequences

- The rabbit-hole investigation now forms a closed loop: recall → investigate → submit evidence →
  re-deliberate → recall updated guidance.
- New evidence can remove obsolete investigation questions or expose new gaps.
- Deliberation history remains inspectable rather than being overwritten.
- Current evidence does not bypass normal durable-memory governance.
- The loop remains reasoning-engine independent and storage-provider neutral.
