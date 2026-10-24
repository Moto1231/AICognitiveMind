# Bounded Surreal runtime storage check

This manual diagnostic tests application commit
`65157abe34b659b0da2c6c162fa51ee8fff5de6d` against only
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

Only then it constructs the existing application stores on that SDK connection
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

## Local validation and remaining startup difference

Twenty-one focused tests cover configuration/source/target guards, database
Editor-only role parsing, schema and nonempty-target refusals, privacy, timeouts,
partial failures and independently verified cleanup. Real isolated `mem://`
tests exercise the existing probe and cleanup after an injected mid-probe failure;
authentication/role metadata in those fixtures is synthetic, not a Cloud test.
The complete local regression suite also passes: **542 tests, 7 skipped**
(163.109 seconds). An earlier run hit its 180-second diagnostic runner limit
inside an existing provider-factory test; the bounded rerun with named-test
progress completed without an assertion failure.

A separate disposable local SurrealKV check also exercised the unchanged
`65157abe` combined OAuth/MCP/web lifespan with init-only synthetic settings and
ambient credentials removed. It entered and closed successfully, `/health`
returned 200, the canonical Mind remained absent, and all eight tables had zero
records afterward. Its local result is retained as
`surreal-local-deployment-startup.log` in the original workbench, outside this repository.

Untouched production startup still executes legacy-scope UPDATE queries and a
conditional legacy commit-state copy; the remote diagnostic does neither. With
a freshly verified empty database, those startup statements have no existing
records to migrate or copy. The local result supports that empty-start path,
but authenticated Cloud startup, connection ordering and server permissions
remain unproved until the authorized remote checks run. Recheck emptiness before
cutover; stop if data or custom schema appears. No model/cognition readiness is
implied by storage startup or an HTTP health response.
