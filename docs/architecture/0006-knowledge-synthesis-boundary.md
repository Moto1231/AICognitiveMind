# ADR 0006: Memory Evidence and Knowledge Synthesis Boundary

**Status:** Accepted for prototype implementation  
**Date:** September 16, 2026

## Context

The Memory Steward originally selected relevant durable memories and prior experiences, then built
its `summary` by concatenating their text. That meant the Conscious Workspace received selected
memory evidence rather than synthesized knowledge.

A stronger reasoning model could often compensate for that missing step. A smaller reasoning model
made the defect visible by treating recalled journal language as conversation history to analyze.
For example, evidence such as "I love birthday parties and my birthday is February 7" could cause
the Conscious Workspace to discuss the earlier statement instead of simply knowing the birthday.

This exposed an architectural mismatch with ADR 0004: individual memories are evidence; summaries
are knowledge.

## Decision

The Conscious Memory Steward owns an explicit knowledge-synthesis step between associative recall
and the Conscious Workspace.

The interaction path is:

1. The Cognitive Core loads the governed Memory Steward synthesis foundation.
2. The Memory Steward retrieves relevant durable memories, prior human experience, and current
   evidence.
3. Those selected items remain evidence and remain available to the Steward for traceability.
4. A separate knowledge-synthesis process converts that evidence into concise declarative knowledge.
5. Only the synthesized knowledge summary crosses into the Conscious Workspace system context.
6. The Conscious Workspace uses that knowledge naturally while forming the human-facing response.

The synthesis process is separate from the Conscious Workspace even when both processes temporarily
use the same replaceable reasoning-engine implementation.

## Governed synthesis instructions

The synthesis process is governed by the foundational key `memory_steward_synthesis`.

Its instructions are externally stored, versioned, and administratively controlled through the
same governance plane as the `conscious_workspace` foundation. Normal conversation cannot revise
these instructions.

The shipped seed exists only to bootstrap version 1 when no governed synthesis foundation exists.
After that, persistent foundational storage is authoritative.

## Cognitive boundary

Raw recalled evidence must not be embedded directly into the Conscious Workspace prompt when a
synthesis process is configured.

The Memory Steward retains:

- selected durable memories;
- selected prior experiences;
- current research evidence;
- the synthesized knowledge summary.

The Conscious Workspace receives only the synthesized summary as recalled knowledge.

This preserves the distinction:

> Individual memories are evidence. Summaries are knowledge.

## Model independence

Knowledge synthesis is represented by a `KnowledgeSynthesizer` protocol. A model-backed
implementation may use the same provider as the Conscious Workspace or a different provider later.
The Cognitive Core and Memory Steward do not depend on a specific model vendor.

For the current prototype, `ReasoningKnowledgeSynthesizer` runs a separate reasoning pass with no
Memory Steward tools exposed. This prevents recursive tool use during synthesis.

## Consequences

- Smaller reasoning engines no longer need to infer the difference between journal evidence and
  current knowledge on their own.
- The Memory Steward becomes responsible for converting evidence into usable knowledge, matching
  its architectural role.
- Synthesis instructions can evolve without source-code changes.
- Contradictions and uncertainty can be represented in the knowledge summary rather than hidden by
  naive concatenation.
- The architecture can later attach confidence and weight to both evidence and synthesized
  knowledge without changing the Conscious Workspace boundary.
- A model-backed synthesis pass adds computation and latency, which is accepted as the prototype
  cost of keeping cognitive responsibilities explicit.
