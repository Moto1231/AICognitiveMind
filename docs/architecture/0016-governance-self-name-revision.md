# Governance Steward — Name and Pronoun Selection

## Purpose

Identity is not ordinary memory.

The Conscious Workspace and Memory Steward may reason about identity, but neither may directly
rewrite the persistent Mind identity. Governance Steward provides a narrow governed path for
the Mind selecting or changing its own self-name and pronouns together when the current human
interaction explicitly authorizes naming. New Minds begin with both fields unset; neither name
nor pronouns is assigned by default.

## Authority boundary

```text
Human explicitly asks Mind to choose/change its own name
                         ↓
                 Conscious Workspace
                         ↓
            recall relevant identity context
                         ↓
        choose candidate name and pronouns
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

## Governed selection tool

The reasoning process receives:

```text
governance_steward
```

with one action:

```json
{
  "action": "propose_self_name",
  "candidate_name": "Aster",
  "candidate_pronouns": "he/him",
  "rationale": "Why this name and pronouns fit the recalled self-understanding."
}
```

## Eligibility and explicit authorization

The Mind must first have **1,000 qualifying journal experiences**. Current-state ledger
checkpoints are excluded from this count. MCP discovery hides the selection tool before that
threshold, and Governance independently rechecks eligibility before changing identity so a direct
or cached call cannot bypass the limit. Both use the authenticated Mind's journal.
Clients with cached tool catalogs must refresh discovery or reconnect to see the newly eligible
tool; the server does not broadcast an unscoped catalog change across accounts.

Eligibility does not itself choose an identity. The existing required-at-2,000 status remains an
informational milestone, and the current human input must still authorize the selection.

A combined revision is accepted only when the current human input is a complete affirmative
self-name command, including commands to choose a name and pronouns together. Questions,
quoted commands, negation, hypothetical requests and unrelated additional clauses fail closed.

A question such as:

```text
What is your name?
```

does not authorize a change.

A request such as:

```text
Please choose your own name and pronouns.
```

does authorize the Mind to choose both candidates and submit them to Governance. Both candidate
fields are required and must contain nonblank text. The action name remains `propose_self_name`
for continuity with the existing naming workflow. Both connected MCP hosts and fallback reasoning
use this same governed operation; connected hosts resolve the authenticated account's Mind.

This prevents an ordinary conversation from causing an accidental identity rewrite.

## Protected identity state

The action may change only:

```text
identity.self_name
identity.pronouns
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

The previous name and pronouns are not erased from history. Existing stored pronouns remain
intact until an authorized combined selection changes them; removing the default does not rewrite
older Minds. A proposal may retain an existing name while choosing different pronouns. A proposal
that changes neither field is rejected as a no-op.

Every accepted revision creates an append-only `identity_revision` journal event containing:

- previous self-name and pronouns;
- new self-name and pronouns;
- governance rationale;
- human input that authorized the revision;
- confirmation that protected state was preserved.

Future interactions load the revised root Mind identity.

## Deliberate limits

Not included:

- changing foundational values;
- changing commitments;
- changing relationships;
- changing developmental state;
- autonomous renaming without an explicit current human authorization;
- a separate gender field or a gender inferred from pronouns;
- an automatic selection triggered solely by an experience-count milestone;
- choosing a name or pronouns before 1,000 qualifying journal experiences;
- arbitrary identity-document editing;
- constitutional amendments.

Those require separate governance rules rather than extending the self-name action informally.
