# ADR 0014: Resolution Readiness Before Belief Transition

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

The Mind can detect semantic tension, appraise evidence, investigate gaps, and re-deliberate as
new current evidence arrives. The next cognitive boundary is deciding when the evidence is
sufficiently developed that one value may be considered for a later belief transition.

This must not collapse Confidence and Weight into one score or silently convert evidence quantity
into majority vote.

## Decision

Each evidence deliberation now includes a `ResolutionReadiness` assessment with one of three states:

- `blocked` — the evidence map is not sufficiently developed for belief transition;
- `candidate_ready` — one value has passed a conservative readiness gate and may be considered by
  a later belief-transition process; or
- `reframe_required` — the competing values are better represented as time- or context-scoped
  knowledge rather than one universally true value.

Resolution readiness never rewrites durable belief by itself.

## Tension investigation findings

A current research observation may include an evidence-backed `TensionInvestigationFinding` that
records:

- whether provenance independence is verified, shared, or unknown;
- whether the values apply to the same timeframe or changed over time;
- whether they apply to the same context or different contexts; and
- concise evidence-backed basis statements.

The finding is retained on later deliberation revisions. A later research observation does not need
to restate a relationship finding that the Mind has already established unless newer evidence
changes it.

## Candidate readiness gate

`candidate_ready` requires all of the following:

1. all competing evidence used by the deliberation has provenance, Confidence, and Weight appraisal;
2. an evidence-backed finding verifies provenance independence;
3. the competing values apply to the same timeframe;
4. the competing values apply to the same context;
5. the candidate value has at least two supporting evidence items from at least two distinct
   immediate sources; and
6. the candidate evidence strictly dominates the competing evidence on the **separate** Confidence
   and Weight dimensions.

Strict dominance means the candidate side's lowest Confidence is at least the competing side's
highest Confidence, and the candidate side's lowest Weight is at least the competing side's highest
Weight, with at least one dimension strictly greater.

This is a conservative Pareto-style gate. Confidence and Weight are never multiplied, averaged, or
otherwise collapsed into one credibility score.

## Reframe required

If evidence establishes that the values apply at different times, the Mind should represent temporal
change instead of selecting one timeless value.

If evidence establishes that the values apply in different contexts, the Mind should represent
contextual scope instead of selecting one universal value.

These cases may be cognitively resolved by richer representation rather than winner selection.

## Compact deliberation evidence history

Research observations remain current evidence and are not automatically promoted to durable
semantic memory. However, evidence that materially contributed to a deliberation is retained in a
compact deliberation evidence history containing:

- query;
- bounded response excerpt;
- evidence appraisal; and
- semantic interpretation.

Full articles are not embedded in the durable deliberation artifact.

This allows later revisions to preserve prior research contributions and recalculate support and
readiness without treating research observations as durable factual memories.

## Consequences

- The Mind has an explicit boundary between unresolved tension and belief-transition eligibility.
- Candidate readiness remains auditable and reversible.
- More evidence does not automatically mean stronger belief.
- A candidate cannot qualify by a single high score or by repeated reporting from one source.
- Time/context differences can trigger representational refinement instead of false contradiction.
- Prior research evidence and verified relationship findings survive across later deliberations.
- The next cognitive slice can focus specifically on belief transition and memory revision rather
  than mixing that operation into evidence assessment.
