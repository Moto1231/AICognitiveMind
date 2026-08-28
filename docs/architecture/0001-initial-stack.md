# ADR 0001: Initial implementation stack

**Status:** Accepted for prototype; cognitive storage amended by ADR 0002  
**Date:** August 11, 2026

## Decision

The first Cognitive Core prototype will use:

- Python 3.12;
- FastAPI for the external interface;
- Pydantic for explicit cognitive-domain contracts;
- MongoDB through the official asynchronous PyMongo client;
- Docker Compose as the GitHub Codespaces dev-container definition;
- direct, project-owned interfaces for reasoning engines and memory;
- a deterministic mock reasoning engine before any live model adapter.

## Why

The prototype is an architectural experiment. Python minimizes friction around model integration, while typed domain contracts keep the experiment explicit and auditable. MongoDB naturally stores evolving, provenance-rich cognitive documents.

An agent framework is intentionally excluded from the Cognitive Core. Such frameworks commonly bring their own memory, orchestration, and identity assumptions. Those responsibilities are the subject of this project and must remain under our control.

## Consequences

- Reasoning providers can be added later without altering the domain core.
- The initial implementation is a modular monolith, not a distributed multi-agent system.
- Cognitive history is append-only; its document shape is governed by ADR 0002.
- A mock engine allows continuity and permission tests to run without API keys, cost, or provider behavior affecting the result.

