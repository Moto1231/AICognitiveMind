# Development Checkpoint — September 17, 2026

## Status

This is a **continuity checkpoint, not a project stop**.

Development may continue immediately after this commit. Its purpose is to preserve the exact
architectural and implementation state reached after the speaker-provenance, contradiction,
confidence/weight, recursive-recall, and evidence-provenance work.

The last runtime-verified implementation commit before this documentation checkpoint is:

```text
129bfcf96aa77d0d9366f31f9ac5bf88c750cd9f
Add prototype evidence provenance envelope
```

At that commit, GitHub Actions **Cognitive Acceptance run 35294959194** passed:

- Ruff lint;
- mypy type checking;
- unit tests;
- acceptance Mind startup;
- local cognitive acceptance.

A future session should begin from this checkpoint and the accepted ADRs rather than reconstructing
these decisions from conversation history.

## Current branch

```text
repository: Moto1231/AICognitiveMind
branch: codex/autonomous-acceptance-loop
verified implementation head: 129bfcf96aa77d0d9366f31f9ac5bf88c750cd9f
```

## Core architectural identity

The system represents **one persistent Cognitive Mind**.

The reasoning engine is replaceable cognitive machinery, not the identity of the Mind.

Persistent identity, long-term memory, governed foundations, working context, evidence stewardship,
knowledge synthesis, and developmental continuity belong to the Mind rather than to any particular
LLM or inference provider.

Internal stewards are cognitive roles/functions of the same Mind, not separate beings.

Two foundational principles remain:

- **Understanding before Recommending**
- **Preserve continuity of identity**

## Proven behavioral boundaries

The current prototype has demonstrated the following.

### Model / Mind continuity

- A reasoning engine can be changed without intentionally resetting the Mind.
- Knowledge retained outside the reasoning engine can be used by a replacement engine.
- Raw historical evidence is not dumped directly into Conscious Workspace; the Memory Steward
  synthesizes knowledge first.

### Working identity and speaker provenance

- `current_speaker` belongs to temporary working context and is controlled at the Mind boundary.
- First-person experience is bound to the speaker who produced it.
- William's statement `My birthday is February 7.` is not usable as Michael's birthday.
- Switching back to William makes William's first-person evidence eligible again.
- An explicit third-person fact such as `Michael's birthday is January 3.` remains usable for
  Michael even when William originally supplied it.

### Subject versus source

The architecture distinguishes:

- **speaker/source of evidence** — who supplied the statement;
- **subject of evidence** — who or what the statement is about.

This is intentionally accomplished without introducing relational person IDs or a fixed identity
registry.

### Reference resolution

- An unresolved statement such as `His birthday is January 3.` is not allowed to become
  person-specific knowledge.
- If working context has already resolved `his` to Michael, that resolved subject is preserved
  with the experience.
- That resolved meaning survives working-memory flush and remains usable later.

The resulting path is:

```text
temporary working context
    ↓
reference resolution
    ↓
resolved meaning preserved with experience
    ↓
long-term evidence
```

### Contradictions

Conflicting evidence is preserved rather than overwritten.

Example:

```text
William: Michael's birthday is January 3.
Michael: No, my birthday is January 4.
```

Both claims reach synthesis together. Retrieval/provenance does not silently discard either claim.

Newness alone does not determine truth.

## Confidence and weight

ADR 0004 established that confidence and weight are independent.

The current prototype now represents them numerically in the normalized interval:

```text
0.0 .. 1.0
```

Their meanings remain distinct:

- **confidence** — factual reliability/belief in the evidence;
- **weight** — reinforcement, significance, or cognitive establishment.

They are not collapsed in storage.

The prototype contradiction support calculation from ADR 0008 is:

```text
support = confidence * weight
delta = abs(S1 - S2)
epsilon = 0.05
```

Behavior:

- `delta > epsilon` — the materially stronger proposition may become current synthesized
  understanding while conflicting evidence remains preserved.
- `delta <= epsilon` — the contradiction remains unresolved.

The support score is a temporary adjudication aid. It does not replace confidence or weight.

## Two-stage scorecards

ADR 0009 establishes two evidence scorecards.

### Prior scorecard

Supplied from long-term memory by the Memory Steward.

It represents what the Mind had already established about the evidence before the current
interaction.

### Effective scorecard

Supplied by the current evidence-synthesis context.

It represents how the evidence should be treated **now**, given current source, subject, context,
conditions, corroboration, contradiction, and other presently relevant evidence.

Contradiction adjudication operates on the **effective** scorecard.

The effective scorecard must not overwrite the prior scorecard merely because it was calculated for
the current interaction.

Conceptually:

```text
long-term evidence
    ↓
prior confidence + prior weight
    ↓
current evidence / condition / context
    ↓
effective confidence + effective weight
    ↓
contradiction adjudication
```

## Bounded recursive recall — "going down the rabbit hole"

Recall is not assumed to be a one-hop operation.

When a recalled claim remains uncertain or contradictory, the Memory Steward may inspect supporting
evidence behind that evidence.

Conceptually:

```text
question
    ↓
recalled claim
    ↓
uncertainty / contradiction
    ↓
supporting evidence
    ↓
source evidence
    ↓
context / conditions
    ↓
reassess effective confidence + weight
    ↓
synthesize or continue
```

Prototype bounds currently exist for:

- maximum recall depth;
- maximum evidence items examined.

Decision order:

1. If effective support materially favors one proposition, synthesize it while preserving competing
   evidence.
2. If support is effectively tied and material supporting evidence exists within budget, expand
   recall.
3. If the useful bounded rabbit hole is exhausted and the contradiction remains unresolved, surface
   uncertainty and ask for clarification when appropriate.

The Conscious Workspace does not need the entire evidence rabbit hole. It receives synthesized
knowledge or unresolved contradiction.

## Evidence provenance envelope

ADR 0010 establishes the current stopping point for provenance refinement.

An assessed proposition may preserve a human-readable provenance chain containing:

- **source** — who or what supplied the evidence;
- **obtained_from** — the upstream source when information is relayed;
- **condition** — relevant circumstances under which the evidence was supplied or observed;
- **context** — the meaning-bearing situation in which it was obtained;
- **scorecard** — optional confidence/weight associated with that provenance hop.

The current conscious assessment may separately preserve current condition and current context.

Example:

```text
William reports Michael's birthday
    ↓ obtained_from
Michael originally reports his own birthday
```

This is deliberately cognitive/document-oriented rather than a relational source graph.

The key principle is:

> Preserve enough provenance to reconsider belief later. Do not collapse the evidence chain into a
> number whose basis the Mind can no longer inspect.

## Current implementation artifacts

Important current files include:

```text
src/aicognitive_mind/core.py
src/aicognitive_mind/domain.py
src/aicognitive_mind/evidence.py
src/aicognitive_mind/memory_steward.py
src/aicognitive_mind/knowledge.py
src/aicognitive_mind/foundation.py
src/aicognitive_mind/working_memory.py
tests/test_memory_steward.py
tests/test_evidence.py
```

`DurableMemory` currently carries normalized confidence and weight.

`evidence.py` currently contains the prototype evidence scorecards, contradiction adjudication,
bounded recursive-recall planning, and provenance envelope structures.

## Accepted architecture decisions

The current ADR chain is:

1. **ADR 0001** — Initial Stack
2. **ADR 0002** — One Instance, One Mind
3. **ADR 0003** — Memory Steward Tool V0.1
4. **ADR 0004** — Memory Evidence, Knowledge Summaries, and Bounded Retention
5. **ADR 0005** — Governed Foundational Memory
6. **ADR 0006** — Memory Evidence and Knowledge Synthesis Boundary
7. **ADR 0007** — Conscious Expression Boundary
8. **ADR 0008** — Prototype Confidence, Weight, and Contradiction Adjudication
9. **ADR 0009** — Two-Stage Evidence Scorecards and Bounded Recursive Recall
10. **ADR 0010** — Prototype Evidence Provenance Envelope

These should be treated as the current architecture unless deliberately superseded by a later ADR.

## Deliberately deferred refinement

Do **not** continue refining the following merely because they are interesting:

- universal source-reputation scoring;
- trust-learning mathematics;
- nonlinear confidence/weight formulas;
- domain-specific authority models;
- reinforcement curves;
- temporal decay curves;
- contradiction decay;
- deep provenance graph structure;
- final epistemic calibration;
- full biological-memory simulation.

Those are valid future research topics, but the current prototype already has enough structure to
continue building and demonstrating the Cognitive Mind.

## Important unresolved implementation distinction

The architecture now has the structures required for:

- prior scorecards;
- effective scorecards;
- provenance chains;
- contradiction adjudication;
- bounded recursive recall.

However, the full live Memory Steward interaction path does **not yet automatically derive all of
those assessments from arbitrary raw conversational evidence**.

That is an implementation frontier, not an invitation to redesign the architecture again.

The next work should favor making the existing architecture operational end-to-end over further
refining the scoring theory.

## Recommended continuation direction

When development continues, prefer an executable vertical slice:

```text
raw human evidence
    ↓
preserve speaker / subject / provenance
    ↓
assign or retrieve prior assessment
    ↓
derive current effective assessment
    ↓
detect contradiction
    ↓
bounded supporting recall if materially useful
    ↓
synthesize current knowledge OR ask clarification
    ↓
Conscious Workspace response
```

Keep the first implementation intentionally simple and observable. The purpose is to prove that the
boundaries work together, not to produce the final mathematics of belief.

## Autonomous development guardrails

Continue using the established rules:

1. Three failed implementation/test cycles require a check-in.
2. Architecture, persistence, governance, security, or public-API changes require a check before
   broad implementation.
3. Environment failure means stop and report rather than hack around it.
4. Conflict with an established architecture principle means stop and report.
5. Acceptance pass means stop that implementation cycle, summarize, and return control.

Passing a test is not permission to violate the architecture.

## Resume instruction

This checkpoint is intentionally complete enough to resume without reconstructing the preceding
conversation.

Start from:

```text
branch: codex/autonomous-acceptance-loop
green implementation commit: 129bfcf96aa77d0d9366f31f9ac5bf88c750cd9f
checkpoint date: September 17, 2026
```

Then continue from the operational integration frontier above unless a new priority is chosen.
