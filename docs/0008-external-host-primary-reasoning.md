# 0008 — External Host Primary Reasoning

Copyright (c) 2026 William Enright. All rights reserved.

## Decision

Axiom is the persistent Cognitive Mind and tool boundary. A reasoning model is not part of Axiom's identity.

The primary reasoning mode is an **external host using MCP**:

1. the host calls `begin_interaction`,
2. Axiom supplies identity, durable memory, continuity, and governed context,
3. the host model performs reasoning,
4. the host calls `complete_interaction`,
5. Axiom's stewards decide what is committed to memory and journal.

A different compatible reasoning host may take over on a later interaction without changing Axiom's identity. Inter-reasoning-model continuity is therefore a core capability, not a fallback behavior.

## Standalone Body fallback

The desktop/browser Body can operate when no external host is actively driving cognition. In that case the API may invoke a configured **standalone fallback reasoning provider**.

The fallback provider is infrastructure, not identity. Gemini, OpenAI, or later providers may be replaced without migrating the Mind.

Configuration uses:

- `STANDALONE_REASONING_PROVIDER` — preferred setting.
- `REASONING_PROVIDER` — legacy compatibility setting.

Existing deployments do not need to change immediately. If both are present, `STANDALONE_REASONING_PROVIDER` wins.

## Boundary

The following remain owned by Axiom regardless of the current reasoning model:

- identity and governed identity revision,
- durable memory and Memory Steward decisions,
- journal continuity,
- governance and permission boundaries,
- sensory evidence and provenance,
- Body state and interfaces.

The following belong to the active reasoning host/provider:

- inference,
- model-specific tool invocation mechanics,
- model context/window behavior,
- provider quota and billing.

The Unity summary must identify **External Host / MCP** as primary reasoning and display any configured provider as **Standalone Fallback**.
