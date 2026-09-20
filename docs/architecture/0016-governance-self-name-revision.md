# Governance Steward V0.1 — Self-Name Revision

## Purpose

Identity is not ordinary memory.

The Conscious Workspace and Memory Steward may reason about identity, but neither may directly
rewrite the persistent Mind identity. Governance Steward V0.1 introduces a narrow governed path for
one identity transition: the Mind selecting or changing its own self-name when the current human
interaction explicitly authorizes that act.

## Authority boundary

```text
Human explicitly asks Mind to choose/change its own name
                         ↓
                 Conscious Workspace
                         ↓
            recall relevant identity context
                         ↓
            choose candidate self-name
                         ↓
               Governance Steward
                         ↓
      validate authorization + protected state
                         ↓
             persistent Mind identity
                         ↓
          identity_revision journal event
```

The Memory Steward is not allowed to perform the write.

## V0.1 tool

The reasoning process receives:

```text
governance_steward
```

with one action:

```json
{
  "action": "propose_self_name",
  "candidate_name": "Aster",
  "rationale": "Why this name fits the recalled self-understanding."
}
```

## Explicit authorization

A self-name revision is accepted only when the current human input explicitly asks the Mind to
choose, select, pick, decide, rename, or otherwise establish its own name.

A question such as:

```text
What is your name?
```

does not authorize a change.

A request such as:

```text
You have to select yourself a name.
```

does authorize the Mind to choose a candidate and submit it to Governance.

This prevents an ordinary conversation from causing an accidental identity rewrite.

## Protected identity state

V0.1 may change only:

```text
identity.self_name
```

It must preserve exactly:

- foundational values;
- commitments;
- relationships;
- developmental state;
- original creation timestamp.

The persistence layer independently requires `VALUES_STEWARD` authority for the exact Mind
replacement.

## Continuity

The previous name is not erased from history.

Every accepted revision creates an append-only `identity_revision` journal event containing:

- previous self-name;
- new self-name;
- governance rationale;
- human input that authorized the revision;
- confirmation that protected state was preserved.

Future interactions load the revised root Mind identity.

## Deliberate V0.1 limits

Not included:

- changing foundational values;
- changing commitments;
- changing relationships;
- changing developmental state;
- autonomous renaming without an explicit current human authorization;
- arbitrary identity-document editing;
- constitutional amendments.

Those require separate governance rules rather than extending the self-name action informally.
