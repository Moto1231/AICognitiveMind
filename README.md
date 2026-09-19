# AICognitiveMind

A working prototype of the Digital Genesis Cognitive Core: one persistent cognitive mind whose memory, values, and developmental history remain independent of any one reasoning model.

> A reasoning engine produces thought. It must not own identity.

## Project journey and current usage milestone

The full development path is documented in
[`docs/BUILD_JOURNEY_AND_USAGE.md`](docs/BUILD_JOURNEY_AND_USAGE.md).

That document records the architecture's evolution, major failures and corrections, evidence and
belief-governance model, what has been proven, and the current priority:

> **Use before expanding.**

The Cognitive Mind is already usable through MCP. The next milestone is to connect the existing
Mind to the everyday reasoning host rather than adding another cognitive subsystem first.

## Mind and Body

The project now has two parallel workstreams that belong to the same whole:

```text
Mind
  +
Body
```

The **Mind** owns identity, memory, belief, reasoning, governance, and continuity.

The **Body** owns eyes, ears, mouth, face, sensors, and physical/computer interfaces.

The Body does not own durable memory or identity. Raw sensory input remains transient until the Mind
interprets it and normal memory governance decides whether anything should persist.

Body foundation documentation lives in
[`docs/body/0001-foundation.md`](docs/body/0001-foundation.md).

Mind and Body development proceed in parallel through narrow integration contracts.

## Development workflow

Routine development is GitHub-first:

```text
branch → pull request → GitHub Actions validation → merge
```

A fresh GitHub-hosted Ubuntu runner performs the normal test/build work for each pull request.
Codespaces are now an interactive exception rather than the default development machine.

Use the local Windows machine when Body work requires actual camera, microphone, speakers, display,
or OS device APIs.

See [`docs/DEVELOPMENT_WORKFLOW.md`](docs/DEVELOPMENT_WORKFLOW.md).

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

## Canonical storage: SurrealDB

SurrealDB is the architectural and runtime default for the Cognitive Mind.

- `mind` contains the whole current identity and developmental state.
- `journal` contains whole cognitive experiences in chronological order.
- `memory` contains whole durable memories curated by the Memory Steward.
- `diagnostics` contains implementation details such as the reasoning model used.

Nothing in `diagnostics` is part of identity, memory, or persona.

MongoDB/Atlas remains supported as a temporary bridge and backup/reference implementation while
the canonical SurrealDB deployment is brought online. New runtime wiring, MCP continuity smoke
tests, and default configuration target SurrealDB. MongoDB must not silently become the canonical
store merely because it is already available.

The Atlas genesis remains preserved as migration/reference state until its contents have been
deliberately transferred or retired.

## Portable Mind backup

The repository includes a verified portable backup capability for identity and cognitive-history
documents. The backup utility preserves BSON values and `_id`s, checks integrity, refuses identity
merges, and rolls back a failed partial restore.

See [`docs/MIND_BACKUP.md`](docs/MIND_BACKUP.md).

## Memory Steward Tool V0.1

Every interaction gives the reasoning process a Memory Steward boundary. The reasoning engine can
propose durable learning; the Mind owns the policy that accepts or rejects it. Identity and values
remain outside the Steward's V0.1 write authority.

## MCP interface

MCP is the external integration standard for Digital Genesis. The connected MCP host supplies the
reasoning model; the Cognitive Mind owns identity, memory, stewardship policy, and cognitive
history.

The server exposes four tools:

1. `initialize_mind` — one-time genesis for the deployment.
2. `mind_status` — identity and continuity counters for administration/demonstration.
3. `begin_interaction` — mandatory recall/context step before the host reasons as the Mind.
4. `complete_interaction` — Memory Steward review/commit plus append-only interaction journaling.

No ChatGPT-, Claude-, Gemini-, or other vendor-specific adapter is part of the Cognitive Mind.


## Reference MCP reasoning host

The repository now includes a small reference host whose only job is to connect a replaceable
reasoning model to the persistent Mind through MCP.

After installing the package, run:

```bash
export OPENAI_API_KEY="..."
export STORAGE_PROVIDER="surreal"
export SURREALDB_URI="surrealkv://.surreal/cognitive_mind"
export SURREALDB_NAMESPACE="mir_ai"
export SURREALDB_DATABASE="ai_cognitive_mind"
cognitive-mind
```

For a single turn:

```bash
cognitive-mind --message "When is my birthday?"
```

The host sequence is enforced in code:

```text
human message
    ↓
begin_interaction over MCP
    ↓
replaceable reasoning model
    ↓
complete_interaction over MCP
    ↓
Memory Steward review + journal commit
    ↓
human-facing response
```

The host does not initialize a new Mind automatically. Its configured SurrealDB target must point
to the canonical existing Mind so changing host processes or reasoning models does not create a new
identity. The first reference reasoner uses the OpenAI Responses API, but it remains outside the
Mind and can be replaced without changing identity or durable memory.

## September 23 demo: VS Code as the MCP host

The workspace includes `.vscode/mcp.json`. In a Codespace, VS Code starts the Cognitive Mind as a
local stdio MCP server. No port needs to be public and no MCP URL needs to be shared.

The configured process is equivalent to:

```bash
python -m aicognitive_mind.mcp_server --transport stdio
```

In VS Code:

1. Open Copilot Chat.
2. Confirm the **digital-genesis** MCP server when VS Code asks whether you trust it.
3. Use Agent/Chat with the Cognitive Mind tools enabled.
4. Teach the Mind a durable fact.
5. Change the reasoning model with VS Code's model picker.
6. Ask the new model for the learned fact.

The model changes. SurrealDB-backed identity, durable memory, and cognitive history do not.

The intended host sequence for every turn remains:

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

## Streamable HTTP deployment

For remote MCP hosts, run:

```bash
python -m aicognitive_mind.mcp_server --transport streamable-http --host 0.0.0.0 --port 8001
```

The endpoint is `/mcp`. Keep it private unless a deliberate remote deployment has an appropriate
network and authorization boundary.

## Initial stack

- Python 3.12
- MCP Python SDK
- FastAPI and Pydantic
- SurrealDB as the canonical/default cognitive store
- MongoDB/Atlas retained as a bridge, backup, and migration source
- GitHub branches / pull requests
- GitHub Actions as the default disposable validation machine
- Codespaces / VS Code for interactive Linux or MCP-host work when needed
- Local Windows for Body hardware/device testing
- Standard-library unit tests plus MCP protocol smoke tests

## Validation

```bash
python -m unittest discover -s tests -v
python scripts/mcp_stdio_smoke.py
```

The project remains an architecture prototype, not a claim of consciousness.
