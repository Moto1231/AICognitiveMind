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

## First connection

Before genesis, verify that the target Atlas database contains no existing Cognitive Mind data.

Then run the normal one-time Mind initialization against Atlas. After that first successful genesis:

- Atlas is the canonical persistent Mind.
- Do not initialize a second Mind in the same deployment.
- Reasoning hosts and models may change while Atlas preserves identity, journal, and durable memory.

## Old MongoDB

Keep the previous MongoDB data private and unchanged as backup/reference material.

Do not automatically import, copy, replay, or merge its `mind`, `journal`, `memory`, or `diagnostics` collections into the canonical Atlas Mind.

The migration tooling remains in the repository as a recovery/maintenance capability, but it is not the active storage plan.
