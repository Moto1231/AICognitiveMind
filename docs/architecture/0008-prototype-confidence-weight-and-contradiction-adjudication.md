# ADR 0008: Prototype Confidence, Weight, and Contradiction Adjudication

**Status:** Accepted for prototype implementation  
**Date:** September 17, 2026

## Context

ADR 0004 establishes that individual memories are evidence, knowledge summaries are synthesized
understanding, and both carry independent confidence and weight. It deliberately left numeric scales
and scoring formulas undefined.

Speaker-provenance tests now demonstrate a concrete contradiction case:

- William provides evidence that Michael's birthday is January 3.
- Michael later provides first-person evidence that his birthday is January 4.

Both claims correctly survive retrieval and reach the Memory Steward synthesis boundary. The next
prototype requirement is therefore not retrieval but adjudication: how much should the Mind believe
each competing proposition, and when should it refuse to choose and ask for clarification?

This ADR defines a deliberately simple starting rule. It is not intended to be the final cognitive
mathematics.

## Decision

### Confidence and weight remain independent

Every evidence item and synthesized knowledge candidate may carry:

- **confidence** in the closed interval `[0.0, 1.0]`;
- **weight** in the closed interval `[0.0, 1.0]`.

They remain independently stored and independently meaningful.

Confidence represents factual reliability. Weight represents reinforcement, significance, or
cognitive establishment. Neither value may be overwritten by the combined support score described
below.

### Prototype normalized support

When the Memory Steward must compare competing knowledge candidates, it may calculate a temporary
normalized support value:

```text
support = confidence * weight
```

Because both inputs are normalized to `[0.0, 1.0]`, support is also in `[0.0, 1.0]`.

Support is an adjudication aid, not a stored replacement for confidence or weight.

### Contradiction comparison

For two conflicting candidate propositions with support values `S1` and `S2`:

```text
delta = abs(S1 - S2)
```

The prototype near-equality tolerance is:

```text
epsilon = 0.05
```

If `delta > epsilon`, the higher-support proposition may become the current synthesized
understanding, subject to governance and any evidence-specific rules. The lower-support proposition
and its supporting evidence remain preserved as contradiction history.

If `delta <= epsilon`, the Memory Steward must treat the contradiction as unresolved rather than
arbitrarily choosing a winner. ADR 0009 permits bounded recursive recall of supporting evidence
before the unresolved contradiction is surfaced for clarification.

### Clarification on unresolved contradiction

When the contradiction is unresolved and the current interaction offers an appropriate person who
can clarify it, the Conscious Workspace should ask a direct clarifying question.

For example:

```text
I have conflicting information about your birthday. Is it January 3 or January 4?
```

The question itself has evidence weight 0 under ADR 0004. The answer becomes new evidence and is
evaluated normally; it does not erase either prior memory merely because it is newer.

If clarification is not possible in the current interaction, the synthesized knowledge must preserve
the uncertainty instead of manufacturing certainty.

## What this ADR does not yet define

The following remain deliberately open:

- how initial confidence is assigned from different evidence sources;
- how initial weight is assigned;
- how multiple evidence items supporting the same proposition combine into candidate confidence and
  candidate weight;
- source authority or trust models;
- reinforcement increments;
- corroboration rules;
- temporal decay;
- contradiction-specific decay or persistence;
- whether confidence and weight require nonlinear normalization later;
- domain-specific thresholds;
- how repeated clarification affects confidence and weight;
- when a contradiction becomes sufficiently resolved to stop surfacing;
- retention and forgetting thresholds.

Those rules require observation and calibration. They must not be inferred from the simple
`confidence * weight` prototype formula.

## Consequences

- Confidence and weight remain first-class independent cognitive attributes.
- The prototype has a deterministic way to compare competing propositions.
- Near-equal support produces uncertainty and a clarification request instead of an arbitrary answer.
- Stronger evidence can change current synthesized knowledge without deleting weaker contradictory
  evidence.
- Newness alone never determines truth.
- The formula can later evolve without changing the evidence-versus-knowledge boundary established
  by ADR 0004 and ADR 0006.

## Prototype principle

> Preserve the evidence. Keep confidence and weight separate. Use normalized support only to decide
> how strongly competing conclusions should influence present knowledge. When support is effectively
> equal, ask rather than guess.
