# ADR 0003: Memory Steward Tool V0.1

**Status:** Accepted for prototype implementation  
**Date:** August 14, 2026

## Context

A stored memory is not useful merely because it exists. It must participate in present thought
when association makes it relevant. The immediate failure case was a reasoning process treating
"constitution" generically instead of recalling its established relationship with mir.ai
Technology, Digital Genesis, and the Cognitive Mind.

The reasoning engine must not own durable memory, but it needs a controlled way to consult and
propose changes to memory while responding.

## Decision

Each user interaction receives an isolated `memory_steward` tool belonging to the one Mind. The
reasoning engine is instructed through its system prompt to use three operations:

- `recall`: retrieve an associative context brief before forming a response;
- `consider_evidence`: submit material research queries, results, and articles as temporary
  working evidence;
- `propose_memory`: offer stable learning to the Steward without directly writing it.

The runtime enforces the initial recall. Research remains optional because not every interaction
requires external information.

The tool instance holds working evidence only for the current interaction. Accepted memory
proposals are committed by the Conscious Memory Steward after the reasoning engine completes.
The Conscious Workspace then records one whole journal experience containing the human input, the
Memory Steward's concise trace, and the final expression. Hidden chain-of-thought and reasoning
engine provenance do not enter cognitive memory.

## Cognitive boundaries

- The reasoning engine may consult and propose; it may not write durable memory.
- The Conscious Memory Steward may curate semantic, procedural, and reflective memory.
- Episodic experience is recorded automatically in the append-only journal.
- Working research evidence expires with the interaction unless it grounds an accepted memory.
- Identity or value changes are rejected because they require constitutional governance.
- MongoDB's `_id` remains private storage metadata; no cognitive or tool-call identifiers are
  introduced.

## Same Mind, separate process

The Conscious Workspace and Conscious Memory Steward are not different individuals. They are
separate cognitive processes belonging to one identity and may ultimately be powered by separate
runtime instances of the same reasoning model. Their prompts, working contexts, authority, and
timing remain distinct.

V0.1 uses deterministic associative selection behind the tool boundary so the protocol can be
tested without choosing a model provider. A later model-backed Steward can replace that selection
process without changing the Conscious Workspace tool contract.

## Consequences

- A response cannot be accepted when the reasoning engine bypasses memory recall.
- Research used during a response becomes visible to the Steward before final synthesis.
- The journal preserves what was experienced; durable memory preserves only what the Steward
  accepts as lasting learning.
- Association is explicit enough to connect related concepts beyond literal prompt wording.
- Provider-specific tool-call loops remain reasoning-engine adapter concerns.
