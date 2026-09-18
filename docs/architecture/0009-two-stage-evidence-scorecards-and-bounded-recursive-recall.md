# ADR 0009: Two-Stage Evidence Scorecards and Bounded Recursive Recall

**Status:** Accepted for prototype implementation  
**Date:** September 17, 2026

## Context

ADR 0004 separates memories as evidence from summaries as knowledge. ADR 0008 introduces independent
confidence and weight and a prototype support calculation for contradiction adjudication.

Those rules are insufficient if a recalled memory's stored confidence and weight are treated as the
final values used in the present interaction. The same remembered information can deserve different
effective treatment depending on who originally supplied it, how that person obtained it, the
conditions and context in which it was learned, who is speaking now, the current subject, current
evidence, and the purpose of the present inquiry.

Recall may also require examining supporting evidence behind recalled evidence before the Memory
Steward can responsibly synthesize current knowledge. This recursive supporting-evidence process is
informally called "going down the rabbit hole."

## Decision

### Two scorecards exist at two cognitive boundaries

Each candidate proposition can carry two distinct scorecards.

The **prior scorecard** belongs to long-term memory and is supplied by the Memory Steward's retained
assessment of the evidence:

- prior confidence;
- prior weight.

The prior scorecard reflects what the Mind had already established about that evidence before the
current conscious situation.

The **effective scorecard** belongs to the present evidence-synthesis context:

- effective confidence;
- effective weight.

It is derived from the prior assessment plus material current evidence and context. The effective
scorecard is what contradiction adjudication uses for the present synthesis.

The effective scorecard must never overwrite the prior scorecard merely because it was calculated
for the current interaction.

### Evidence provenance can be recursive

An evidence item may depend on supporting evidence about:

- who supplied it;
- whether that source was a direct observer;
- who that source obtained it from;
- the reliability and context of upstream sources;
- the conditions under which the information was learned;
- corroborating or contradicting memories;
- relevant temporal context.

The architecture therefore permits recursive supporting-evidence recall. Evidence about evidence is
not flattened into an unexplained scalar if the supporting chain materially affects the result.

### Bounded rabbit-hole recall

Recursive recall must be bounded. The prototype exposes an explicit recall budget with:

- maximum recursion depth;
- maximum number of evidence items examined.

When a contradiction is unresolved, the Memory Steward follows this decision order:

1. If effective support materially favors one proposition, synthesize that proposition while
   preserving the contradictory evidence.
2. If support is effectively tied and relevant supporting evidence remains available inside the
   recall budget, expand recall and reassess.
3. If support remains effectively tied and no useful bounded expansion remains, surface unresolved
   contradiction so the Conscious Workspace can ask a clarifying question when appropriate.

This changes the interpretation of ADR 0008's clarification rule: near-equality makes clarification
eligible, but the Steward may first inspect material supporting evidence within its bounded recall
budget.

### Current scoring mathematics remain intentionally incomplete

This ADR defines *where* scoring occurs and *which scorecard* adjudication uses. It does not define
the final algorithm for converting source identity, source history, observation quality, context,
corroboration, or other provenance into confidence and weight.

Those factors will be developed and calibrated separately.

## Consequences

- Long-term confidence/weight become a prior assessment rather than an unquestioned final score.
- Present context can change effective confidence/weight without corrupting long-term assessment.
- Contradiction adjudication operates on effective, not prior, support.
- Recall may recursively inspect support for recalled evidence.
- Recursive recall has explicit stopping conditions and resource bounds.
- Clarification is preferred over arbitrary selection when evidence remains effectively equal after
  useful bounded supporting-evidence recall.
- Future source-trust and context-scoring functions can evolve without changing this cognitive
  boundary.

## Core principle

> Long-term memory supplies the prior. Present evidence supplies the effective assessment. When the
> two do not yield a sufficiently clear conclusion, follow the evidence chain within bounded
> resources; if it remains unresolved, ask rather than guess.
