# AICognitiveMind

A working prototype of the Digital Genesis Cognitive Core: a persistent digital identity whose memory, values, and developmental history remain independent of any one reasoning model.

> A reasoning engine produces thought. It must not own identity.

## First milestone

Prove continuity across a reasoning-engine swap:

1. Create one simulated Being.
2. Record interactions and engine provenance in an append-only event history.
3. Replace Reasoning Engine A with Reasoning Engine B.
4. Verify that identity, memories, commitments, and relationship history remain intact.

The initial implementation deliberately avoids agent frameworks. Reasoning engines are adapters; the Cognitive Core owns identity and memory.

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
