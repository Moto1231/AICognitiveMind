# ADR 0017: Scope-Aware Semantic Interpretation

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

The Mind can preserve temporal/contextual differences as `scoped_belief` artifacts after a governed
belief reframe. Until now, however, the semantic comparison layer still identified propositions
only by subject, attribute, and value.

That meant future evidence risked collapsing `service.owner = Alice [before September 1]` into the
same proposition as `service.owner = Alice [today]`, or creating false tension between values that
belong to different customer contexts.

## Decision

`SemanticInterpretation` now has optional semantic scope:

- `kind`: `temporal`, `contextual`, `temporal_contextual`, or `other`; and
- `label`: an evidence-grounded human-readable scope description.

Scope participates in proposition identity.

The initial semantic signature is therefore:

`subject + attribute + value + scope`

where an unscoped proposition has an empty scope identity.

## Comparison rules

For the same subject and attribute:

- same value + same scope → corroborating/equivalent evidence;
- different value + same scope → unresolved semantic tension;
- different scope → distinct scoped proposition; no automatic corroboration or contradiction.

A scope mismatch is recorded as a `semantic_scope_distinction` artifact on newly accepted durable
evidence. This records that related evidence exists under another scope without claiming those
scopes are necessarily disjoint.

## Scope equality

V0.1 scope equality is deliberately conservative and deterministic: scope kind and normalized
scope label must match.

The Steward does not currently infer that differently worded scope labels are semantically
equivalent, overlapping, or disjoint. That is a later reasoning problem rather than a string
normalization shortcut.

## Reframed beliefs become active semantic meaning

A governed belief reframe does not rewrite the original `semantic_interpretation` artifact.

Instead, when a durable memory carries `scoped_belief: valid_in_scope`, the semantic comparison
layer treats that Steward-owned scoped belief as the active interpretation for the same
subject/attribute/value and suppresses the original unscoped interpretation from active comparison.

The original interpretation remains preserved for audit.

Thus, after a reframe such as:

- `Alpha [Customer A]`
- `Beta [Customer B]`

new `Alpha [Customer A]` evidence corroborates only the Customer A proposition, while
`Gamma [Customer A]` creates tension only against the Customer A proposition.

## Deliberation and current evidence

Semantic tension now carries its scope. Deliberation, retained research evidence, and current
research observations contribute to that tension only when their semantic slot matches:

`subject + attribute + scope`.

An evidence-backed `TensionInvestigationFinding` may also carry scope. For a scoped tension, its
scope must match before it can affect resolution readiness.

## Belief transition

Belief-transition proposals may carry semantic scope. The Steward matches candidate readiness,
current-belief state, status artifacts, and committed transition artifacts within that scope only.

A transition in `Customer A` therefore cannot close a tension or supersede evidence in `Customer B`.

## Exact text is not semantic identity

Exact memory text is no longer sufficient reason to reject a proposed durable memory when semantic
interpretations are present.

Identical wording under different scopes may be accepted as distinct durable evidence. Exact text
is rejected as duplicate only when equivalent semantic evidence already exists in the same scope.

## Proposition-level tension

Multiple evidence memories may support the same scoped value. A later competing value creates one
semantic tension for the scoped proposition, not one tension per evidence document.

Deliberation still counts each supporting evidence item separately.

## Consequences

- Scoped beliefs now affect actual reasoning/comparison rather than only recall presentation.
- Reframed historical evidence no longer produces false cross-scope contradictions.
- Research evidence cannot accidentally re-deliberate a tension in another scope.
- Belief transition can evolve one context without changing another.
- Original unscoped semantic history remains auditable.
- The next refinement can address semantic relationships between differently worded or potentially
  overlapping scopes without changing this storage-neutral proposition model.
