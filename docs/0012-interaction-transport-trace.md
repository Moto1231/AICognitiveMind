# 0012 — Per-interaction transport trace

Axiom now exposes a diagnostic trace for the ChatGPT-facing MCP surface.

Each `begin_interaction` generates an interaction trace ID (the existing idempotency key) and records the exact request and returned context. The corresponding `complete_interaction` records the exact completion request and either the committed response or an error.

Use `interaction_trace(interaction_id)` to retrieve the server-observed trace.

The trace is independent evidence of what reached Axiom. It answers:

- Did the host call `begin_interaction`?
- What exact user message and host context reached Axiom?
- What exact Mind context did Axiom return?
- Did the host call `complete_interaction` with the same interaction ID?
- What response and memory/evidence proposals did the host submit?
- Did Axiom commit the interaction or return an error?

An interaction with only a `begin` event is explicitly reported as `incomplete`.

This trace does not expose model-internal reasoning or traffic that never reaches the Axiom MCP server. That distinction is intentional: the trace proves what Axiom actually received and returned, rather than trusting a host's claim that it used Axiom.
