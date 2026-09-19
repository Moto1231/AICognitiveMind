# Canonical Atlas Mind

Atlas is the canonical persistent MongoDB deployment for the Cognitive Mind.

## Current storage decision

The Atlas deployment named `Mind` starts clean.

The previous MongoDB deployment is **not migrated into Atlas**. It is retained only as a private backup/reference source. Do not merge the two histories.

The Cognitive Mind continues to use the application database name:

```text
ai_cognitive_mind
```

and these cognitive collections:

- `mind`
- `journal`
- `memory`
- `diagnostics`

## Application connection

Obtain the Atlas **Drivers** connection string and keep its database-user password out of the repository.

Runtime configuration:

```bash
export MONGODB_URI="mongodb+srv://<db-user>:<password>@<cluster-host>/?retryWrites=true&w=majority&appName=Mind"
export MONGODB_DATABASE="ai_cognitive_mind"
export OPENAI_API_KEY="..."
```

The existing `MongoRuntime` uses PyMongo's `AsyncMongoClient`, so the same application code accepts the Atlas SRV URI.

## GitHub Actions runtime path

Codespaces are not required to verify or initialize the canonical Atlas Mind.

Create the repository secret:

```text
CANONICAL_MONGODB_URI
```

Its value must be the private Atlas `mongodb+srv://...` Drivers connection string.

Then open **Actions → Canonical Atlas → Run workflow**.

Two manual operations are available:

- `check` — pings Atlas and reports document counts for `mind`, `journal`, `memory`, and `diagnostics`. It does not initialize the Mind.
- `genesis` — first verifies all four cognitive collections are empty, then performs the one-time initialization and verifies the resulting storage state.

The workflow uses the application database `ai_cognitive_mind`.

Genesis currently initializes:

```text
self_name: AICognitiveMind
foundational values:
- Understanding before Recommending
- Preserve continuity of identity
```

The workflow never prints the Atlas connection string.

## First connection

Run `check` first and verify the target Atlas cognitive collections contain no documents.

Then run `genesis` once. The application-level one-Mind guard still refuses a second initialization, and the Atlas admin script additionally refuses genesis if any cognitive collection contains documents.

After the first successful genesis:

- Atlas is the canonical persistent Mind.
- Do not initialize a second Mind in the same deployment.
- Reasoning hosts and models may change while Atlas preserves identity, journal, and durable memory.

## Old MongoDB

Keep the previous MongoDB data private and unchanged as backup/reference material.

Do not automatically import, copy, replay, or merge its `mind`, `journal`, `memory`, or `diagnostics` collections into the canonical Atlas Mind.

The migration tooling remains in the repository as a recovery/maintenance capability, but it is not the active storage plan.
