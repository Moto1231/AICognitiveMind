# Person + Presence Identity Foundation

## Decision

Axiom distinguishes **who a person is** from **who appears to be present now**.

A `PersonIdentity` is persistent cognitive/social knowledge about a known person. It has no
database/application ID. Names, aliases, relationship context, and grounding are cognitive
information; provider-native storage keys are not identity.

A `Presence` is transient Body state for somebody currently perceived. It begins `unknown`
and may accumulate exact sensory evidence references.

Resolution states are:

- `unknown` — a person is perceived but no known identity is justified;
- `candidate` — evidence suggests a known person, but the association is not established;
- `resolved` — sensory evidence and existing identity grounding justify the association.

## Boundary

This slice does **not** implement face recognition, voiceprints, speaker diarization, or
audio/visual fusion. Those become evidence producers for this contract.

The intended path is:

```text
Eyes / Ears
    ↓
immutable sensory evidence
    ↓
person / speaker observations
    ↓
Presence (unknown → candidate → resolved)
    ↓
Conscious Workspace / Memory Steward
```

Identity resolution must never be inferred merely because a camera or microphone belongs to a
particular account. Physical sensory evidence and established cognitive knowledge remain distinct.

## Why

Face recognition and voice recognition answer similarity questions. They should not own the
meaning of personhood or relationships inside Axiom. Keeping Person identity in the Mind and
Presence at the sensory/cognitive boundary allows multiple evidence types to corroborate or
challenge an association without silently rewriting identity.

## Next increment

Add a Presence Resolver that can consume visual and auditory identity observations, retain
multiple simultaneous unknown presences, and expose resolved/candidate presence as structured
`input_context` to the Cognitive Core.
