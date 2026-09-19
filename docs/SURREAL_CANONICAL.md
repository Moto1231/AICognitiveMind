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

## Safe migration contract

`scripts/surreal_canonical.py migrate-from-atlas`:

1. Requires a remote TLS Surreal endpoint.
2. Requires an Atlas `mongodb+srv://` source.
3. Validates every source cognitive document through the domain model.
4. Refuses migration unless Atlas contains exactly one root Mind.
5. Refuses migration if any canonical Surreal cognitive table is nonempty.
6. Removes MongoDB physical `_id` metadata rather than importing it into cognition.
7. Writes validated cognitive documents into Surreal.
8. Reads the Surreal documents back and verifies domain-level parity.
9. Rolls the target cognitive tables back to empty if migration or verification fails.

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
