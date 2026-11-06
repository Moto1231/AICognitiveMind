# Governance Steward — Name and Pronoun Selection

## Purpose

Identity is not ordinary memory.

The Conscious Workspace and Memory Steward may reason about identity, but neither may directly
rewrite the persistent Mind identity. Governance Steward provides a narrow governed path for
the Mind selecting its own self-name and pronouns together under the journal-based lifecycle.
Later changes to an established pair require explicit current human authorization. New Minds
begin with both fields unset; neither name
nor pronouns is assigned by default.

## Authority boundary

```text
Eligible first choice or explicitly authorized later change
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
Browser Realtime sessions include the naming tool only when the authenticated Mind is eligible
at session creation. A session opened earlier may defer an optional choice; at the mandatory
deadline it holds the answer and requests a reconnect to load the tool.

From 1,000 entries, a Mind with an incomplete identity may make its first joint choice
autonomously. The application supplies lifecycle authority without requiring a new human command;
the reasoning model supplies the actual candidate pair and rationale. The Mind may defer while
before the deadline. Both saved nonblank attributes establish a complete identity, which reports
`complete` and is never autonomously renamed.

An ordinary completion cannot leave the initial choice incomplete at 2,000 qualifying entries.
The service checks current state outside its receipt cache, projected state inside the atomic
completion, and the final delivery state after asynchronous bookkeeping. At 1,999, the next
ordinary entry requires a prior committed choice. Additional qualifying Steward events are
included in the staged check. A blocked attempt returns `naming_choice_required`, does not poison
the retry receipt or the persistence circuit, and can be retried unchanged after selection.
While the initial choice is incomplete, ordinary work below the deadline can continue, but hosts
hold the answer until the final completion delivery decision. Established identities retain the
configured presentation-first policy.

Begin, status, state maintenance and administrative recovery remain available. Direct fallback,
MCP, Body delivery, cached replies and direct or queued voice output share the requirement.
Configured and reference hosts can make a bounded model-generated choice and recover the frozen
response; invalid model output fails closed rather than inventing default identity values.

A later revision to a complete identity is accepted only when the current human input is a
complete affirmative self-name command, including commands to choose a name and pronouns
together. Questions, quoted commands, negation, hypothetical requests and unrelated additional
clauses fail closed for these later revisions.

A question such as:

```text
What is your name?
```

does not authorize changing an already complete identity.

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
- current input and whether authority came from the initial-choice lifecycle or an explicit later command;
- confirmation that protected state was preserved.

Future interactions load the revised root Mind identity.

## Deliberate limits

Not included:

- changing foundational values;
- changing commitments;
- changing relationships;
- changing developmental state;
- autonomous revision of a complete identity without explicit current human authorization;
- a separate gender field or a gender inferred from pronouns;
- deterministic or randomly assigned default names or pronouns;
- choosing a name or pronouns before 1,000 qualifying journal experiences;
- arbitrary identity-document editing;
- constitutional amendments.

Those require separate governance rules rather than extending the self-name action informally.
