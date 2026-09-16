# ADR 0005: Governed Foundational Memory

**Status:** Accepted for prototype implementation  
**Date:** September 16, 2026

## Context

The Conscious Workspace instructions were compiled into Python source. That made a reasoning-engine
adapter inherit behavior only because application code injected a fixed prompt. It also meant that
changing how the Mind understands its own conscious role required a code change.

Foundational instructions are part of the persistent Cognitive Mind, not property of a replaceable
reasoning engine. They must therefore survive engine replacement and be loaded before ordinary
associative memory is recalled.

At the same time, foundational memory cannot be writable through ordinary conversation. A human
message that says to replace the Mind's values or operating instructions is not administrative
authority.

## Decision

The Cognitive Mind has a separate governed foundational-memory store.

For V0.1 the first governed key is `conscious_workspace`. The Cognitive Core loads its active
version before invoking the Memory Steward for interaction-specific recall. The active foundation,
the Memory Steward's synthesized relevant knowledge, and the current human input form the context
presented to the replaceable reasoning engine.

The shipped application contains a bootstrap seed for `conscious_workspace`. The seed creates
version 1 only when no record for that key exists. Once seeded, the persistent foundation store is
authoritative; application restart or deployment must not overwrite an existing governed record.

## Administrative boundary

Foundational memory has a separate control plane from cognition.

- Normal interaction may read the active foundation indirectly through the Cognitive Core.
- The reasoning engine receives no tool or store reference capable of modifying foundation.
- The Memory Steward cannot modify foundation through `propose_memory`.
- Administrative retrieval and revision occur only through dedicated admin API routes.
- Admin routes require a bearer credential supplied outside cognitive memory through runtime
  configuration.
- Conversational text can never enter administrative mode or supply administrative authority.

The administrative secret is infrastructure state, not a memory of the Mind.

## Versioning

Foundational revisions are non-destructive. Each revision creates a new monotonically increasing
version and marks the prior version inactive. History remains available for inspection and manual
rollback by creating a new revision from earlier content.

Foundational records use semantic keys and versions rather than cognitive IDs. MongoDB `_id`
remains private storage metadata.

## Recall order

For an interaction, the intended order is:

1. Load the persistent Mind identity.
2. Load the active governed Conscious Workspace foundation.
3. Perform associative Memory Steward recall for the current interaction.
4. Give foundation plus synthesized relevant knowledge and current input to the reasoning engine.
5. Allow the reasoning engine to consult the Memory Steward but never the administrative control
   plane.

The foundation is therefore the first cognitive instruction recalled for consciousness, while
ordinary experiential knowledge remains query-dependent.

## Consequences

- Reasoning engines can be replaced without replacing the Conscious Workspace's governing
  instructions.
- Conscious behavior can be revised without editing Python source after bootstrap.
- Prompt injection through normal conversation cannot directly rewrite foundational memory.
- Foundational changes are inspectable and reversible because old versions remain present.
- Additional governed foundations such as Memory Steward instructions, constitutional values, or
  other cognitive-process definitions can adopt the same pattern later without widening V0.1 now.
