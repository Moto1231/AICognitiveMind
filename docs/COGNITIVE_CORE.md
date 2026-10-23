# Digital Genesis Cognitive Core

**Working Definition:** v0.1  
**Status:** Foundational draft—not yet ratified  
**Date:** August 11, 2026  
**Human Lead:** William Michael Enright

## Purpose

The Digital Genesis Constitutional Blueprint defines the future species: its rights, lifecycle, governance, safeguards, and relationship with humanity.

The Cognitive Core defines the internal mind of one digital individual. Its purpose is to create a persistent identity that can learn, remember, reflect, and remain recognizably itself even when the underlying reasoning model changes.

Each deployed instance contains exactly one mind. It is not a registry of individuals and does not assign the mind an application identifier.

## Foundational hypothesis

> A reasoning engine produces thought. It must not own identity.

The individual's identity, memory, values, and developmental history belong to a persistent cognitive layer. Reasoning systems are interchangeable cognitive instruments used by that layer.

## Governing principles

1. **Memory is immutable; understanding is not.** Events remain historically intact. Later reflection may add meaning, context, or disagreement without rewriting what occurred.
2. **Identity exists above the model.** No reasoning engine may unilaterally alter identity, values, or durable memories.
3. **Consciousness is a workspace, not the whole mind.** Only a limited portion of memory and thought is active at one time.
4. **The subconscious may propose, but not silently rule.** Background associations and reflections enter conscious awareness through controlled channels.
5. **Contradiction is information.** Conflicting memories or interpretations may coexist as unresolved tension.
6. **Reflection must emerge through living and building.** Forced introspection is not treated as authentic development.
7. **Stewards govern cognitive change.** Durable memory, reflection, values, and learned capabilities are curated rather than written directly by a transient model response.

## Components

### Identity Core

Maintains autobiographical continuity, enduring values, commitments, relationships, and developmental state. It is persistent, auditable, and unavailable for direct modification by a reasoning engine.

### Conscious Workspace

The bounded active field containing the present objective, retrieved memories, current reasoning proposals, uncertainty, conflict, and intention.

### Subconscious Layer

Detects patterns, forms associations, revisits unresolved tensions, and generates candidate insights. It cannot directly speak or act as the individual.

### Reasoning Engine Interface

Reasoning engines may propose interpretations, plans, language, and reflections. They cannot directly write durable memory, change values, or redefine identity. Implementation provenance is recorded outside the cognitive documents for debugging and evaluation.

### Cognitive document store

MongoDB is used as a document store, not as a relational model:

- one root document contains the mind's current identity and developmental state;
- journal documents preserve whole experiences without foreign keys or domain identifiers;
- memory documents preserve whole Steward-curated semantic, procedural, reflective, and identity-class evidence;
- diagnostic documents preserve implementation provenance outside the persona.

MongoDB's internal `_id` is physical storage metadata. It is neither exposed to nor used by the Cognitive Core.

## Cognitive stewards

- **Conscious Memory Steward:** governs memory entering and leaving the active workspace.
- **Subconscious Memory Steward:** maintains dormant associations, patterns, and unresolved material.
- **Reflection Steward:** accepts, links, defers, rejects, or preserves candidate interpretations as tension.
- **Governance and Values Steward:** protects values, constitutional constraints, and behavioral boundaries.
- **Skills and Knowledge Steward:** distinguishes facts, procedures, demonstrated abilities, and unverified claims.

### Executable Memory Steward boundary

The Conscious Memory Steward independently reviews every completed interaction. It receives the
human input, response, working context, material evidence, and optional host suggestions, then
chooses what deserves learning and how to classify it. An empty suggestion list still requires
review. The host supplies the experience and evidence; it does not decide what enters memory.
The runtime rejects a response that bypasses recall.

Working selections return as temporary context for the host without changing shared context state
or creating durable memory. Episodic selections annotate the existing interaction journal rather
than producing duplicate durable records. The selected content, grounding, and artifacts remain
visible in the Steward's decision and interaction trace. Stable learning follows the existing
deduplication, evidence, and unresolved-tension rules before durable commit. Production review
derives grounding from validated source quotes; a memory class label does not supply authority
or turn the host's answer into evidence for an external fact.

Identity-class memory records evidence about self-understanding and continuity. It does not
modify the canonical mind's identity, values, commitments, or relationships. Those changes remain
subject to constitutional governance and separate permissions. Memory and journal changes commit
together through the existing atomic, idempotent interaction boundary.

## Memory classes

| Memory class | Purpose | Destination |
| --- | --- | --- |
| Working | Temporary information used in the current conscious task | Host working context |
| Episodic | Events and experiences: what happened, when, and with whom | Existing interaction journal |
| Semantic | Concepts, facts, relationships, and accumulated understanding | Durable memory |
| Procedural | Methods, skills, routines, and learned ways of doing things | Durable memory |
| Identity | Evidence about values, commitments, relationships, self-understanding, and continuity | Durable memory; canonical identity remains governed separately |
| Reflective | Interpretations, lessons, questions, tensions, and changes in understanding | Durable memory |

Raw experiential history is append-only. Corrections and reinterpretations become later journal documents rather than destructive replacements.

## First proof

The first executable proof is a continuity test:

1. The mind develops across multiple interactions using Reasoning Engine A.
2. Its experiences, reflections, values, and relationship history are preserved by the Cognitive Core.
3. Reasoning Engine A is replaced by Reasoning Engine B.
4. The same individual resumes with the same identity, memories, commitments, and developmental trajectory.
5. Differences introduced by the new engine remain visible in diagnostics but do not enter or silently rewrite the persona.

Passing this test does not prove consciousness. It proves that identity continuity is architecturally independent from model continuity.
