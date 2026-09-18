# ADR 0010: Prototype Evidence Provenance Envelope

**Status:** Accepted for prototype implementation  
**Date:** September 17, 2026

## Context

ADR 0009 establishes two scorecards: a long-term prior assessment and a current effective
assessment. It also permits bounded recursive recall when the Memory Steward needs supporting
evidence before synthesizing knowledge.

A score by itself is not sufficient evidence provenance. The Mind may need to know who supplied a
claim, who that source obtained it from, the conditions under which it was supplied, the context in
which it was understood, and the scorecard associated with supporting links in that chain.

The prototype needs to preserve those facts without prematurely building a universal reputation,
trust, or source-authority model.

## Decision

Each assessed proposition may carry a human-readable provenance chain.

Each provenance hop may preserve:

- **source** — who or what supplied that piece of evidence;
- **obtained_from** — an upstream source when the current source is relaying information;
- **condition** — relevant circumstances under which the information was supplied or observed;
- **context** — the meaning-bearing situation in which the evidence was obtained;
- **scorecard** — an optional confidence/weight assessment associated with that provenance hop.

The current assessment may separately preserve the condition and context of the present conscious
situation.

No database identity key or relational source graph is required. Provenance remains cognitive
content attached to the evidence assessment.

## Relationship to the two scorecards

The long-term Memory Steward supplies the **prior scorecard** together with the retained provenance
that supports its assessment.

The current evidence-synthesis process supplies the **effective scorecard** after considering the
present evidence and context.

The prototype does **not** define a universal formula that converts provenance text into confidence
or weight. Source identity, source history, directness, hearsay, conditions, context, corroboration,
and contradiction are legitimate inputs to those assessments, but their final calibration remains
future work.

This is intentional. The architecture preserves the information required for better scoring later
without pretending the current prototype has already solved human trust and epistemology.

## Recursive provenance

A provenance hop may name an upstream source. That gives the Memory Steward a reason to follow the
supporting chain during bounded recursive recall when the result could materially change the
effective assessment.

For example:

```text
William reports Michael's birthday
    ↓ obtained_from
Michael originally reports his own birthday
```

The Mind can preserve both links and their conditions rather than flattening them into the same kind
of evidence.

## Stopping point for the current prototype

At this stage the prototype intentionally stops refining provenance mathematics.

It has enough structure to demonstrate:

1. long-term memory supplies a prior confidence/weight assessment;
2. present evidence supplies an effective confidence/weight assessment;
3. source, upstream source, condition, and context remain available to explain or reconsider those
   assessments;
4. unresolved contradictions may follow supporting provenance within the bounded rabbit-hole rules;
5. unresolved near-equality ultimately produces clarification rather than guessing.

Trust learning, source reputation, nonlinear scoring, domain-specific authority, decay, and deeper
epistemic calibration are deferred.

## Core principle

> Preserve enough provenance to reconsider belief later. Do not collapse the evidence chain into a
> number whose basis the Mind can no longer inspect.
