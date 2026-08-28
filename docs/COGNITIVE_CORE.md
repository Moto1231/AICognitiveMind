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
- memory documents preserve whole Steward-curated semantic, procedural, and reflective memory;
- diagnostic documents preserve implementation provenance outside the persona.

MongoDB's internal `_id` is physical storage metadata. It is neither exposed to nor used by the Cognitive Core.

## Cognitive stewards

- **Conscious Memory Steward:** governs memory entering and leaving the active workspace.
- **Subconscious Memory Steward:** maintains dormant associations, patterns, and unresolved material.
- **Reflection Steward:** accepts, links, defers, rejects, or preserves candidate interpretations as tension.
- **Governance and Values Steward:** protects values, constitutional constraints, and behavioral boundaries.
- **Skills and Knowledge Steward:** distinguishes facts, procedures, demonstrated abilities, and unverified claims.

### Executable Memory Steward boundary

The V0.1 Conscious Memory Steward is exposed to the reasoning engine as an interaction-scoped
tool. The system prompt requires recall before response, permits research evidence to be submitted
for comparison, and permits durable memory to be proposed but not written by the reasoning
engine. The runtime rejects a response that bypasses recall.

Whole interactions remain episodic journal experiences. Only Steward-approved stable learning is
written to durable memory; identity and value changes remain subject to constitutional governance.

## Memory classes

| Memory class | Purpose |
| --- | --- |
| Working | Temporary information used in the current conscious task |
| Episodic | Events and experiences: what happened, when, and with whom |
| Semantic | Concepts, facts, relationships, and accumulated understanding |
| Procedural | Methods, skills, routines, and learned ways of doing things |
| Identity | Values, commitments, relationships, self-understanding, and continuity |
| Reflective | Interpretations, lessons, questions, tensions, and changes in understanding |

Raw experiential history is append-only. Corrections and reinterpretations become later journal documents rather than destructive replacements.

## First proof

The first executable proof is a continuity test:

1. The mind develops across multiple interactions using Reasoning Engine A.
2. Its experiences, reflections, values, and relationship history are preserved by the Cognitive Core.
3. Reasoning Engine A is replaced by Reasoning Engine B.
4. The same individual resumes with the same identity, memories, commitments, and developmental trajectory.
5. Differences introduced by the new engine remain visible in diagnostics but do not enter or silently rewrite the persona.

Passing this test does not prove consciousness. It proves that identity continuity is architecturally independent from model continuity.
