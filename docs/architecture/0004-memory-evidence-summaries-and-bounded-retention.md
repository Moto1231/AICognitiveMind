# ADR 0004: Memory Evidence, Knowledge Summaries, and Bounded Retention

**Status:** Accepted for architecture  
**Date:** September 16, 2026

## Context

The Cognitive Mind must preserve experience without treating every remembered statement as equally
true, equally important, or permanently worth the resources required to retain it.

A prior model that treated durable memory as a single current fact is insufficient. New information
must not simply overwrite old information, because apparently conflicting memories may represent a
correction, a change over time, an inference, or unresolved uncertainty.

At the same time, mir-ai is intentionally bounded. Unlimited retention is neither possible nor
desirable. The Memory Steward therefore needs a way to preserve evidence, synthesize present
knowledge, and eventually forget information whose value no longer justifies its resource cost.

## Decision

The memory model distinguishes **individual memories as evidence** from **knowledge summaries as
current synthesized understanding**.

### Individual memories are evidence

Each meaningful experience or learned item is recorded as its own memory rather than merged into or
overwriting an earlier memory.

While retained, an individual memory carries at least two independent attributes:

- **Confidence** — how strongly the Mind believes that specific memory is factually reliable.
- **Weight** — how reinforced, recurring, significant, or retention-worthy that specific memory has
  become through experience.

Confidence and weight are intentionally separate. A fact stated once by an authoritative source may
have high confidence and low weight. A frequently encountered inference may have high weight while
remaining only moderately confident.

Weight is not increased merely because a memory was retrieved. Reinforcement must come from new
experience, repetition, corroboration, successful use, or another materially meaningful encounter.
This prevents self-reinforcing recall loops.

Questions remain part of episodic experience and may be remembered as events, but a question has
**evidence weight 0** with respect to the fact it asks about. A question may establish recall intent,
context, interests, or behavioral history, but asking whether something is true does not itself make
that proposition more credible, reinforced, or established. Question-only experiences therefore do
not consume evidence-selection capacity during factual knowledge synthesis.

### Knowledge summaries are synthesized understanding

The Memory Steward synthesizes related individual memories into knowledge summaries.

A knowledge summary also carries:

- **Confidence** — how strongly the retained body of evidence supports the synthesized conclusion.
- **Weight** — how established or reinforced that summarized knowledge is across its supporting
  memories and experiences.

The summary is what normally crosses the memory boundary into the Conscious Workspace. The
reasoning engine should receive the Mind's current understanding rather than a raw retrieval log or
an unfiltered collection of historical experiences.

Individual memories remain the evidence. Summaries remain the knowledge derived from that evidence.

### Contradictions do not cause immediate overwrite

When a new memory conflicts with existing memories, the Steward preserves the conflicting evidence
and revises the current summary according to confidence, weight, authority, relevance, temporal
context, and other future governance rules.

A newer memory does not become true merely because it is newer, and an older memory does not become
false merely because it is contradicted.

Unresolved contradictions must remain represented until the Steward has sufficient basis to
synthesize a more confident conclusion.

## Bounded retention

Individual memories are not absolutely immutable. They are **non-destructive by default while they
remain cognitively useful**, but the Memory Steward has authority to remove memories when bounded
resources require consolidation or forgetting.

Retention decisions may consider:

- confidence;
- weight;
- age;
- recurrence or reinforcement;
- uniqueness;
- present and expected relevance;
- whether the information is already represented in a sufficiently strong summary;
- whether the memory is the only support for a summary;
- whether it participates in an unresolved contradiction; and
- the storage or processing cost of retaining it.

The Steward must not remove evidence that is still necessary to understand an unresolved
contradiction merely because that evidence is old or low-frequency.

Likewise, a low-weight but highly confident and unique memory may deserve retention, while a newer
low-confidence memory that adds nothing beyond an established summary may be expendable.

Protected foundational or governed memories are outside ordinary cleanup authority and will be
controlled by the separate governance model.

## Memory lifecycle

The intended lifecycle is:

```text
Experience
    ↓
Individual Memory
(confidence + weight)
    ↓
Association / Reinforcement / Contradiction
    ↓
Memory Steward Synthesis
    ↓
Knowledge Summary
(confidence + weight)
    ↓
Recall into Conscious Workspace
    ↓
Periodic Steward Review
    ↓
Retain / Consolidate / Archive / Forget
```

Forgetting is therefore not simple age-based deletion. It is an explicit cognitive resource
management function.

## Consequences

- Memories are normally appended as separate evidence rather than overwritten in place.
- Current knowledge can change without erasing the experiences from which earlier understanding
  arose.
- Confidence represents factual belief; weight represents reinforcement and cognitive retention
  value. They must not be collapsed into one score.
- Confidence and weight exist independently on both individual memories and synthesized summaries.
- Questions remain rememberable experiences but have zero evidentiary weight for the proposition
  they ask about.
- The Conscious Workspace normally consumes summaries, not raw memory histories.
- Memory cleanup becomes a responsibility of the Memory Steward rather than a database TTL or
  oldest-first deletion policy.
- Consolidation and forgetting are permitted because mir-ai is bounded, but deletion must be
  evidence-aware rather than merely chronological.
- The initial prototype scale and contradiction-support formula are defined by ADR 0008. Aggregate
  confidence/weight derivation, decay functions, reinforcement rules, and cleanup thresholds remain
  separate implementation decisions to be developed through validation.

## Core principle

> Individual memories are evidence. Summaries are knowledge. Both carry confidence and weight. The
> Memory Steward uses those values for recall, synthesis, consolidation, and eventual forgetting
> under bounded resources.
