# AICognitiveMind

A working prototype of the Digital Genesis Cognitive Core: one persistent cognitive mind whose memory, values, and developmental history remain independent of any one reasoning model.

> A reasoning engine produces thought. It must not own identity.

## First milestone

Prove continuity across a reasoning-engine swap:

1. Initialize the one mind belonging to this application instance.
2. Preserve whole experiences in an append-only cognitive journal.
3. Replace Reasoning Engine A with Reasoning Engine B.
4. Verify that identity and cognitive history remain intact.
5. Keep engine provenance outside the mind in diagnostic storage.

The initial implementation deliberately avoids agent frameworks. Reasoning engines are adapters; the Cognitive Core owns identity and memory.

## One instance, one mind

This is not a registry or population manager. The deployment contains one root `mind` document. It cannot initialize a second individual.

The cognitive model contains no application-level primary keys, foreign keys, mind IDs, host IDs, or journal-entry IDs. MongoDB creates a private `_id` for physical storage, but the Cognitive Core does not assign it, expose it, or use it as part of cognition.

## MongoDB document shape

- `mind` contains the whole current identity and developmental state.
- `journal` contains whole cognitive experiences in chronological order.
- `memory` contains whole durable memories curated by the Memory Steward.
- `diagnostics` contains implementation details such as the reasoning model used.

Nothing in `diagnostics` is part of identity, memory, or persona.

## Memory Steward Tool V0.1

Every interaction now gives the reasoning engine one interaction-scoped tool named
`memory_steward`. The Conscious Workspace system prompt requires this sequence:

1. `recall` related memory before reaching a conclusion;
2. `consider_evidence` for research results materially used in the answer;
3. compare the user message, recalled context, and current evidence;
4. `propose_memory` for stable learning that may deserve durable retention;
5. return the response, after which the Cognitive Core journals the whole experience.

The runtime rejects a response if the reasoning engine skipped recall. The reasoning engine can
only propose memory. The Conscious Memory Steward accepts or rejects the proposal and is the only
process in this path allowed to write it. V0.1 accepts semantic, procedural, and reflective memory;
episodic experience belongs in the append-only journal, while identity and values remain outside
the Steward's authority.

The implementation remains provider-neutral. A live model adapter receives the system prompt and
tool schema through the `ReasoningEngine` interface; the deterministic echo adapter exercises the
same mandatory recall boundary in tests and local development.

## Initial stack

- Python 3.12
- FastAPI and Pydantic
- MongoDB with the official asynchronous PyMongo client
- A reproducible GitHub Codespaces dev container
- Standard-library unit tests for the core domain

## Run in the Codespace

After rebuilding the dev container:

```bash
python -m unittest discover -s tests -v
uvicorn aicognitive_mind.api:app --reload --host 0.0.0.0 --port 8000
```

Then open `/docs` on the forwarded port to use the API.

## Project status

The current code is an architecture skeleton, not a claim of consciousness. It establishes the protected boundaries among identity, memory, stewards, and interchangeable reasoning engines before connecting a live model.


## MCP interface

The September 23 demonstration path is MCP-first. The connected MCP host supplies the reasoning
model; the Cognitive Mind owns identity, memory, stewardship policy, and cognitive history.

The server exposes four tools:

1. `initialize_mind` — one-time genesis for the deployment.
2. `mind_status` — identity and continuity counters for administration/demonstration.
3. `begin_interaction` — mandatory recall/context step before the host reasons as the Mind.
4. `complete_interaction` — Memory Steward review/commit plus append-only interaction journaling.

Install the project and run the MCP server:

```bash
pip install -e .
python -m aicognitive_mind.mcp_server
```

The Streamable HTTP MCP endpoint is:

```text
http://localhost:8001/mcp
```

For a Codespace or hosted demo, expose port 8001 through HTTPS and give the resulting `/mcp`
endpoint to an MCP-compatible host.

The intended host sequence for every conversation turn is:

```text
human message
    ↓
begin_interaction
    ↓
connected host/model reasons using recalled Mind context
    ↓
complete_interaction
    ↓
Memory Steward commits accepted learning + journal experience
    ↓
host presents final response
```

No ChatGPT-, Claude-, Gemini-, or other vendor-specific adapter is part of the Cognitive Mind.
MCP is the external integration standard.
