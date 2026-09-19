# ADR 0010: Unresolved Semantic Tension

**Status:** Accepted for initial implementation  
**Date:** September 19, 2026

## Context

Semantic interpretation allows the Memory Steward to recognize when differently worded evidence
expresses the same proposition. The inverse case also matters: two memories may refer to the same
interpreted subject and attribute while asserting different values.

Such evidence must not be silently collapsed, overwritten, or resolved by recency alone.

## Decision

When two `semantic_interpretation` artifacts have the same normalized subject and attribute but
different normalized values, the Memory Steward creates an unresolved **semantic tension**.

The newer evidence remains a separate durable memory. It receives a Steward-owned
`semantic_tension` artifact containing:

- `status: unresolved`;
- the interpreted subject and attribute;
- the proposed value;
- the competing existing value; and
- the existing evidence content that created the tension.

The Memory Steward also appends a `tension` journal experience containing both competing values
and both evidence statements.

The MCP interaction result surfaces the tension in the Memory Steward decision so the connected
Conscious Workspace can reason with the conflict immediately.

## No automatic winner

This slice does not decide which value is correct, newer in meaning, more reliable, or more
authoritative. Recency alone is not resolution.

Resolving tension requires later evidence-comparison mechanisms such as provenance, source chain,
context, confidence, weight, temporal applicability, corroboration, and reflection.

## Terminology

The initial term is **tension**, not contradiction. Competing values may represent actual
contradiction, a change over time, differing contexts, an imprecise statement, or incomplete
evidence. The Mind should preserve that uncertainty until it has grounds to distinguish them.

## Consequences

- Conflicting evidence remains visible and durable.
- The Conscious Workspace is explicitly warned not to manufacture agreement.
- Journal history records when the tension was first recognized.
- Memory inspection exposes the tension as a Steward artifact.
- Future confidence/weight work has a concrete unresolved evidence structure to operate on.
