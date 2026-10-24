# Bounded Surreal runtime storage check

This manual diagnostic tests application commit
`79aa753a2ab8f395473857d0b54408a490b65808` against only
`mir-ai-06gmqbgl1duq581garj3eabaq4.aws-use1.surreal.cloud`, namespace `mir_ai`,
database `ai_cognitive_mind`, with database user `axiom_runtime`, role EDITOR only.
It is not a migration or production switch. It does not initialize the canonical
Mind, create accounts, register OAuth clients, configure models or call lifecycle tools.

## Secure owner entry

Create/update only these repository Actions secrets at
<https://github.com/Moto1231/AICognitiveMind/settings/secrets/actions>:

- `AXIOM_RUNTIME_SURREALDB_USERNAME`: `axiom_runtime`.
- `AXIOM_RUNTIME_SURREALDB_PASSWORD`: the dedicated runtime user's password.

Enter the password directly in GitHub, never in chat or command arguments.
The endpoint and target are pinned literals, so no additional URI secret is needed.
Keep all `CANONICAL_SURREALDB_*` reader secrets unchanged. Owner confirmation that
the user exists is not confirmation that these two secrets have been entered.

## What runs

The manual **Surreal runtime storage write check** workflow checks out and installs
the exact application SHA above. It uses the diagnostic script from the selected
workflow revision, with isolated Python import handling and read-only repository permissions.
There are no push/PR/schedule triggers, root login attempts, auth fallbacks or automatic retries.

The script signs in with explicit database scope, selects that existing target,
pings the server, inspects only metadata and aggregate counts, and requires:

- The selected database defines `axiom_runtime` with EDITOR as its only role.
- All eight known application tables have zero records; no unknown tables exist.
- No custom database resources, table fields, indexes or events are present.
- Any existing table has only its default schemaless definition, without a view,
  relation type, changefeed or other custom table-level behavior.

Only then it calls the application's shared `bootstrap_tables` helper. Eight
individual `DEFINE TABLE IF NOT EXISTS ... SCHEMALESS PERMISSIONS NONE` statements
create missing application tables without overwriting definitions or records.
It then constructs the existing application stores on that SDK connection
and runs the unchanged `verify_live_tenancy` synthetic probe. The probe writes a
new generated scope, checks isolation, and deletes only its own scoped records.
The diagnostic independently checks all eight aggregate counts afterward.
Empty schemaless tables can remain; they are not dropped.

Normal `create_storage()` initialization is deliberately not called: it performs
legacy-scope updates/copying, which this approval excludes. This checks authenticated
runtime CRUD/isolation capability rather than every step of untouched service startup.

Reports contain only the pinned source/host/target, stage/outcome, role, aggregate
counts and cleanup result. Transport logs, exceptions, schema definitions, tokens,
passwords, generated identifiers and message contents are suppressed.

## Stop conditions

Stop before writes on missing secrets, wrong username/source, failed authentication,
unverified/wrong role, nonempty target, unknown tables or custom schema. Stop on any
probe, timeout, cleanup or connection-close failure. Do not escalate permissions,
reset tables, rerun blindly or delete remaining data. A failed probe can have partial
writes; inspect its safe cleanup result before deciding what to do next.

A passing result is permission evidence for the separately approved conditional
Render recovery, not proof of canonical Mind/model setup or working cognition.
The workflow itself does not change Render, Mongo, reader credentials or GitHub settings.

## Bootstrap repair and local validation

Normal `SurrealRuntime.initialize()` now calls the same helper after connection,
selection, authentication and ping, before its first legacy UPDATE or state read.
Each statement is checked separately. Existing tables, including custom schema,
remain unchanged. A bootstrap error closes the owned connection and propagates;
partial empty table definitions are retained rather than removed. Mongo startup
does not call this helper.

The full regression suite passes: **566 tests, 7 skipped** (100.718 seconds).
Schema tests cover fresh and repeated startup, existing definitions/data,
partial failure, connection cleanup and the Mongo boundary. Startup diagnostic
tests cover guard ordering, partial bootstrap, privacy and independent cleanup.

Actual local **SurrealDB 3.3.2**, downloaded from the official release and verified
against its SHA256, reproduced `read_primary_mind` and `cleanup_mind`
`NotFound/Table` before the repair. On the same disposable loopback memory server,
the shared bootstrap followed by the unchanged tenancy probe passed; all eight
record counts were zero afterward. Repeated bootstrap retained definitions and
an existing custom table's fields, index and synthetic record.

Normal runtime startup and repeated startup also passed on 3.3.2 with a synthetic
database Editor. A separate fresh database passed the combined OAuth/MCP/web
lifespan: `/health` returned 200, all eight tables remained empty, the canonical
Mind remained absent, and shutdown completed. No model, interaction, Body or
Cloud calls were made; both local servers were stopped. Metadata-only local
artifacts are `local_surreal3_bootstrap_result.json` and
`local_surreal3_combined_startup_result.json` in the workbench outside the repository.

The remote diagnostic still skips normal startup's legacy-scope UPDATEs and
conditional commit-state copy. Actual 3.3.2 local startup covers those statements
on empty synthetic storage; it does not establish Cloud deployment, account
routing, model setup or cognition readiness. Recheck target emptiness before
any cutover and stop if data or custom schema appears.

## Failure trace and SurrealDB 3.x compatibility

The first authorized Cloud run, Actions `40126780923`, authenticated successfully
and verified database Editor-only metadata. Before/after counts were zero, but
the probe stopped with only `operation_failed`. That report does not establish
that any write succeeded, nor identify the failing operation. The existing
`write_attempted` flag means the probe was entered, not that its first write ran.

The diagnostic wraps bootstrap and probe SDK calls. The trace performs no
additional database I/O and preserves their original arguments, results and
exceptions. Its `probe_diagnostics` contains fixed operation labels, the last
successful label, and separate first SDK failure and cleanup failure metadata. Raw
transaction failures may include a bounded statement ordinal. Only allowlisted
exception categories, server-kind path components and JSON-RPC codes are copied;
messages, traceback text, SQL, field values, identifiers and error details are
never emitted. If cleanup masks an earlier Python/model error, a separate fixed
classification of that exception context is retained; its exact Python operation
is not inferred from the last SDK call. Advertised server and SDK versions are
reduced to numeric versions.
The normal independent cleanup inventory is unchanged.

A verified version difference explains why embedded success is insufficient:
the installed Python SDK is 2.0.0, while its wheel SBOM identifies the embedded
core as 2.3.10. Its local `version()` response is the binding's hardcoded version,
not that core version. Cloud Studio reported 3.3.2. SurrealDB's
[statement reference](https://surrealdb.com/docs/reference/query-language/statements/overview#output-when-resource-not-defined)
and [2.x-to-3.x guide](https://surrealdb.com/docs/build/migrating/from-old-surrealdb-versions/2x-to-3x#19-schema-strictness-changes)
document that 3.x errors on SELECT/UPDATE/DELETE against undefined tables.

The second authorized Cloud run, Actions `40128420307`, reported server 3.3.2,
SDK 2.0.0, and `NotFound/Table` at `read_primary_mind`, followed by the same
classification at `cleanup_mind`. Authentication and Editor-only verification
passed; all before/after counts were zero. No create operation was reached.
That confirmed the missing-table gap now repaired locally.

## Next bounded Cloud check

After publication and execution approval, publish/merge with `[skip render]`
and run this manual workflow once. It must install the pinned repaired application
SHA above, retain the same host/namespace/database, Editor credentials, empty/default
schema guards and synthetic-scope cleanup. Require `schema_bootstrap=complete`,
`status=passed`, `cleanup=empty` and zero counts for all eight tables. The separate
`write_attempted` flag still means entry into the probe, not successful first DML.

On a bootstrap failure the report identifies the fixed table operation, skips
the probe and checks record counts independently. Partial empty tables remain;
there is no schema rollback or deletion. Stop on unexpected data/schema, denied
permissions, unverified cleanup or any other failure; inspect the result before
another attempt. No additional Cloud run, publication or production change was
made while preparing this local repair.
