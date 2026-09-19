# ADR 0016: Scoped Belief Reframing

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

Resolution readiness can determine that an apparent contradiction should not be settled by choosing
one value. Some values are both valid because truth changed over time or differs by context.

In those cases, superseding one value would destroy useful structure. The Mind needs to preserve
both values while representing the scope in which each remains valid.

## Decision

Belief reframing is an explicit governed Memory Steward operation, separate from belief transition.

The Conscious Workspace may propose a reframe only for the exact subject, attribute, existing value,
and proposed value of a latest deliberation whose readiness is `reframe_required`.

The Memory Steward independently revalidates that deliberation before committing any change.

## Evidence-backed scopes

A `TensionInvestigationFinding` may carry:

- `existing_scope`; and
- `proposed_scope`.

These are human-readable descriptions established by evidence, such as:

- `before September 1` and `on or after September 1`; or
- `Customer A` and `Customer B`.

`reframe_required` alone is not enough to commit a reframe. Both scopes must be present in the
latest verified finding. The host is not allowed to invent scopes merely to close a tension.

## Reframe relationship

The Steward classifies the committed representation as:

- `temporal` when the finding establishes `changed_over_time`;
- `contextual` when the finding establishes `different_contexts`; or
- `temporal_contextual` when both apply.

## Scoped beliefs

When a reframe is accepted, neither value becomes `current` or `superseded`.

Instead, the Steward appends a `scoped_belief` artifact to durable evidence supporting each value.
The artifact records:

- subject and attribute;
- value;
- evidence-backed scope;
- relationship type;
- `valid_in_scope` status; and
- deliberation revision.

The original evidence memory, semantic interpretation, provenance, appraisal, tension, and
deliberation history are preserved unchanged.

## Reframe artifact and journal

One durable evidence memory also receives a `belief_reframe` artifact recording:

- committed status;
- semantic slot;
- relationship;
- both values and scopes;
- deliberation revision; and
- evidence basis.

A dedicated `belief_reframe` journal experience additionally records both preserved evidence sets.

## Recall

Recall surfaces a committed representation as a scoped belief, for example:

`service · owner = Alice [before September 1] ; Bob [on or after September 1]`

Once committed, the exact historical tension's investigation questions and `reframe_required`
readiness note are no longer active guidance. The original tension and deliberation remain
available for audit.

## Rejection and idempotency

A reframe is rejected without durable mutation when:

- no matching deliberation exists;
- the latest deliberation is not `reframe_required`;
- either scope is missing;
- the evidence no longer establishes temporal or contextual distinction;
- both durable evidence sides cannot be located; or
- the same or newer deliberation revision has already been reframed.

## Consequences

- The Mind can resolve false contradictions without discarding either valid proposition.
- Temporal change and contextual variation become first-class belief representations.
- Scope remains grounded in evidence rather than invented by the reasoning host.
- Reframing remains auditable and storage-provider neutral.
- Belief transition and belief reframing stay cognitively distinct operations.
- A future slice can make semantic interpretation itself scope-aware for reasoning about new
  evidence inside or outside established scopes.
