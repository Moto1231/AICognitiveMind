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

## September 23 demo console

Version 0.4 adds a single-screen pre-sales console served directly by FastAPI.

- **User Mode** is the conversation surface.
- **Admin Mode** shows Mind identity, durable-memory and journal counts, and the active reasoning implementation.
- Admin Mode can replace the active reasoning model at runtime without recreating the Cognitive Core or its Mongo-backed cognitive stores.
- The active model remains visible in the header so an audience can see the switch while the Mind remains continuous.
- An optional `ADMIN_PIN` protects the model-switch control for demonstrations outside a trusted local environment.

Configure selectable OpenAI models in `.env`:

```dotenv
OPENAI_API_KEY=...
OPENAI_MODEL=<default-model>
OPENAI_MODELS=<default-model>,<second-model>
ADMIN_PIN=
```

The configured `OPENAI_MODELS` list is an allow-list for Admin Mode. A deterministic echo engine is also available as a diagnostic adapter.

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
- A dependency-free HTML/CSS/JavaScript demo console

## Run in the Codespace

After rebuilding the dev container:

```bash
python -m unittest discover -s tests -v
uvicorn aicognitive_mind.api:app --reload --host 0.0.0.0 --port 8000
```

Open the forwarded port root URL for the demo console. FastAPI's `/docs` remains available for developer inspection.

## Project status

The current code is an architecture prototype, not a claim of consciousness. It establishes protected boundaries among identity, memory, stewards, and interchangeable reasoning engines and now exposes those boundaries through a focused continuity demonstration.
