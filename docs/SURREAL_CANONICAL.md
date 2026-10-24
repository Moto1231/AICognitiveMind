# Canonical Surreal Mind

SurrealDB is the intended single persistent home of the Cognitive Mind.

MongoDB Atlas is retained only as the migration source and temporary bridge until the canonical
Surreal deployment has been created, populated, verified, and adopted by the runtime.

## Canonical identity

Namespace:

```text
mir_ai
```

Database:

```text
ai_cognitive_mind
```

The canonical Surreal deployment contains these cognitive tables:

- `mind`
- `journal`
- `memory`
- `diagnostics`

The Cognitive Core does not use Surreal record IDs as cognitive identifiers.

## GitHub secrets

The `Canonical Surreal` workflow expects:

- `CANONICAL_SURREALDB_URI`
- `CANONICAL_SURREALDB_USERNAME`
- `CANONICAL_SURREALDB_PASSWORD`

The existing `CANONICAL_MONGODB_URI` secret is used only as the Atlas migration source.

The runtime uses `SURREALDB_AUTH_LEVEL=database` for the canonical deployment. A suitable
SurrealQL definition, after selecting the canonical namespace and database, is:

```sql
DEFINE USER cognitive_mind_service
ON DATABASE
PASSWORD 'REPLACE_WITH_A_STRONG_PASSWORD'
ROLES EDITOR;
```

Store the actual password only in the GitHub secret. Do not commit it to the repository.

## Read-only preflight

The `Canonical Surreal` workflow's `check` operation uses the existing Surreal
secret references. It authenticates an existing database-scoped system user and
issues only `INFO FOR DB` and aggregate `SELECT` queries over the eight known
application tables. HTTP namespace/database headers select the target. It never
calls `USE`, application initialization, the tenancy probe, or migration code;
some Surreal versions can create missing namespaces/databases through `USE`.

Output is limited to the endpoint hostname, namespace/database, connection
outcome, table and tenant counts, and conflict indicators. Account compatibility
counts identify missing legacy keys, missing tenant mappings and duplicate global
keys without returning account identifiers, hashes, credentials or record contents.
Unknown table names and schema definitions are not logged. A populated target or
legacy account state requires inspection before any migration; this preflight does
not compare Mongo history or establish which database is newer.

Requests retain TLS verification, reject redirects and embedded URL credentials,
and have per-request, whole-run and response-size bounds. Errors use fixed failure
categories; raw server responses and exception messages are suppressed. Missing
configuration or connection/query failure exits unsuccessfully without writes.
The check still reports the safe endpoint identity when credentials are missing,
without making a database request. The workflow's credential gate applies only to
migration; it must not prevent that diagnostic report.

Run only `operation=check` for diagnosis. The older `migrate-from-atlas` operation
below predates multi-mind operational state and is not a complete modern deployment
migration. Do not run it or switch providers without a reviewed preservation plan.

`operation=check-root` is a separate, explicitly authorized diagnostic. It permits
exactly one instance/root signin, without namespace/database signin fields or
headers, to the approved `mir-ai-06gmqbgl1duq581garj3eabaq4.aws-use1.surreal.cloud`
endpoint only (TLS, default port, `/rpc`). Its target is pinned to
`mir_ai / ai_cognitive_mind`. It first checks target membership with `INFO FOR ROOT`
and `INFO FOR NS`; missing targets stop the check without creating anything.
Only an existing target proceeds to the same read-only inventory queries. This
operation never falls back to another authentication scope or retries signin.
It preserves only allowlisted RPC error categories/codes, never server messages.
The default `check`, migration behavior and application authentication defaults
remain database-scoped. Root authentication requires separate approval before run.

## Legacy migration contract

`scripts/surreal_canonical.py migrate-from-atlas`:

1. Requires a remote TLS Surreal endpoint.
2. Requires an Atlas `mongodb+srv://` source.
3. Validates every source cognitive document through the domain model.
4. Refuses migration unless Atlas contains exactly one root Mind.
5. Refuses migration if any canonical Surreal cognitive table is nonempty.
6. Removes MongoDB physical `_id` metadata rather than importing it into cognition.
7. Writes validated cognitive documents into Surreal.
8. Reads the Surreal documents back and verifies domain-level parity.
9. Preserves a committed target for inspection if post-commit verification fails.

This is intentionally a one-home migration, not dual-write synchronization.

## Operational sequence

1. Create the persistent Surreal Cloud instance.
2. Configure namespace `mir_ai` and database `ai_cognitive_mind`.
3. Create a database-scoped system user for `mir_ai / ai_cognitive_mind`, preferably with the
   `EDITOR` role. The canonical workflow authenticates at database scope rather than root.
4. Add the three canonical Surreal GitHub secrets.
5. Run `Canonical Surreal → check`.
6. Run `Canonical Surreal → migrate-from-atlas`.
7. Verify the Surreal counts and identity.
8. Point runtime hosts only at canonical Surreal.
9. Retire Atlas from active Mind duty while retaining it as a historical backup until deliberately removed.
