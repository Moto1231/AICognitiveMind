# ADR 0015: Governed Belief Transition

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

The Mind can now detect semantic tension, investigate evidence, re-deliberate, and determine when
one value is `candidate_ready` for a later belief transition. The remaining operation is changing
which proposition the Mind currently relies on without erasing the evidence or reasoning history
that led there.

Candidate readiness must not itself mutate belief. The connected reasoning host also must not be
able to force a transition merely by asserting a preferred value.

## Decision

Belief transition is an explicit, governed Memory Steward operation.

The connected Conscious Workspace may submit a transition proposal containing:

- subject;
- attribute; and
- candidate value.

The Memory Steward independently finds the latest matching deliberation and accepts the transition
only when that deliberation remains `candidate_ready` for the exact requested value.

Blocked, reframing-required, stale, wrong-value, or already-committed transition requests are
rejected without staging durable mutation.

## Supersede, do not erase

When a transition is accepted, the Steward does not rewrite or delete either competing evidence
memory.

Instead, it appends Steward-owned artifacts:

- `belief_status: current` to durable evidence supporting the new current value;
- `belief_status: superseded` to durable evidence supporting the prior value; and
- one `belief_transition` artifact recording the semantic slot, prior value, current value,
  deliberation revision, readiness basis, and committed status.

`superseded` describes belief status, not evidence invalidity. The original memory content,
grounding, provenance, appraisal, tension, and deliberation artifacts remain intact.

## Journal

Each committed transition appends a dedicated `belief_transition` journal experience containing:

- subject and attribute;
- superseded and current values;
- deliberation revision;
- readiness basis;
- durable evidence content supporting the candidate;
- durable evidence content supporting the superseded value; and
- committed status.

This creates an auditable sequence of what the Mind believed and why that belief changed.

## Recall

Recall surfaces the latest committed transition for a semantic slot as `Current belief`.

Historical evidence remains recalled as established memory when relevant, but deliberation and
investigation guidance for the exact tension closed by the transition is no longer presented as
active work.

Likewise, a historical `candidate_ready` note for that closed tension is suppressed after the
transition has committed.

## Future contradictory evidence

A committed transition closes only that specific historical tension. It does not make the semantic
slot immutable.

If later durable evidence proposes a third or changed value, the Steward compares it against the
current belief. Evidence explicitly marked as supporting a superseded value is not used to create
additional duplicate tensions against the new statement.

Thus belief can evolve again while historical evidence remains available.

## Transaction boundary

Belief-state artifacts are staged during the interaction and written through the storage-neutral
`replace_exact` contract when the Memory Steward completes the interaction.

A rejected transition leaves no staged belief mutation.

MongoDB and SurrealDB therefore retain the same cognitive semantics.

## Consequences

- Evidence, reasoning history, and current belief state remain distinct.
- Belief changes are explicit and auditable rather than silent overwrites.
- A connected reasoning model cannot bypass the Steward's readiness gate.
- Superseded evidence remains available for later reconsideration.
- Closed tensions stop generating stale investigation work.
- Later evidence can create a new tension against the current belief, allowing continued learning.
