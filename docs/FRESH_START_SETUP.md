# Clean-start setup: current implementation and local demonstration

The original setup demonstration used `main` commit `d24fa4241a470801ded4eae2425ae3f277367def`.
The signup/login repair described below was merged as `65157abe`.
The subsequent local table-bootstrap repair is application commit `79aa753`.
Publishing a repair is separate from deployment or a database switch.
This is a clean start: no identity, account, configuration, memory or journal import.
Existing Mongo and production settings remain untouched.

## What setup already exists

1. **Storage startup:** `create_storage(settings)` selects Surreal and calls
   `SurrealRuntime.initialize()`. It connects, selects namespace/database, signs
   in when credentials are supplied, pings, defines the eight missing default
   application tables with `IF NOT EXISTS`, and runs legacy-scope updates.
   Opening storage is therefore potentially mutating. Startup does not create a
   canonical Mind. The shared table bootstrap preserves existing definitions and
   records; it adds no indexes, account or Mind data.
2. **One-time Mind initialization:** the installed command
   `cognitive-mind-init --self-name "<new name>" --value "<new value>"`
   invokes `initialize_cli.initialize_once`. It atomically writes a Mind,
   initialization journal entry and revision state, then closes storage.
   API `POST /v1/mind/initialize` and MCP `initialize_mind` expose related
   initialization entry points. A second initialization is refused.
3. **Account signup:** `POST /v1/portal/signup` (also exposed through `/signup`)
   calls `AccountService.create`. It allocates a new `mind_<uuid>` tenant,
   initializes an unnamed Genesis Mind, then writes and reads back the account
   registry record. This is a different target from the CLI's configured root
   Mind; the two paths are not consecutive steps of a unified installer.
4. **Model setup:** fresh storage has no provider endpoints or selected
   Memory Recall provider/model. The production Memory Steward requires that
   task for both begin and completion. Initialization itself needs no model call.

The intended user sequence is the existing login page's **Create a new Axiom
account**, enter a new username/password, receive confirmation, then sign in.
The portal form posts JSON to `/v1/portal/signup`; the public entry's **Create
new account** link opens the HTML `/signup` form. Both use `AccountService.create`.
No new setup wizard is needed. After login, the persisted session selects the
account's Mind. Model task setup is a separate remaining step.

Source entry points:

- [Storage factory](../src/aicognitive_mind/persistence.py),
  [Surreal runtime](../src/aicognitive_mind/surreal_storage.py)
- [CLI](../src/aicognitive_mind/initialize_cli.py),
  [service initialization](../src/aicognitive_mind/mcp_service.py)
- [Account setup](../src/aicognitive_mind/accounts.py),
  [portal routes](../src/aicognitive_mind/deployment.py)

## SurrealDB 3.x fresh-start repair

SurrealDB 3.3.2 rejects reads, updates and deletes against undefined tables.
The old startup/probe relied on 2.x behavior and could fail before its first
write. The shared bootstrap now runs before normal runtime reads/updates and
before the bounded diagnostic's synthetic tenancy probe.

On actual disposable local SurrealDB 3.3.2, the original missing-table error
was reproduced. The repaired normal runtime, repeated startup, tenancy probe
and combined OAuth/MCP/web lifespan passed. Fresh startup created eight empty
tables without initializing a canonical Mind. Existing custom schema and a
synthetic record survived repeated bootstrap. Both local servers stopped.
The full local regression suite passed 566 tests with 7 skipped.

See [the runtime check](SURREAL_RUNTIME_CHECK.md) for the exact repaired source
pin, authenticated Cloud guard/cleanup plan and local evidence. Cloud execution
of this repair and production cutover remain separate, pending steps.

## Earlier setup demonstration (before explicit bootstrap)

The local harness uses a fresh SurrealKV directory, explicit init-only settings,
no `.env` or ambient credential sources, no cloud credentials, and synthetic data.
Each persistence phase runs in a separate Python process.

Reproduce in this workbench with the existing interpreter:

```powershell
& 'C:\Users\Mpls5\Documents\AICognitiveMind\.venv\Scripts\python.exe' -I -B `
  'C:\Users\Mpls5\Documents\Codex\2026-10-23\task\local_surreal_setup_probe.py'
```

The script is restricted to `task/local_setup_mind_*` paths. It creates a new
directory on every run; it does not clear or reuse a previous database. It loads
the existing repository source and `.test-deps`. The original initialization
demonstration used source identical to pinned main. The current working tree
also contains the local signup/login repair and its regression tests.

Actual results:

| Step | Observed result |
| --- | --- |
| Open fresh local storage before bootstrap repair | No tables, Mind or journal; revision 0 |
| Run existing initializer | `status=initialized` |
| Restart in another process | Mind/identity preserved; one initialization journal entry; revision 1 |
| Inspect lazy table bootstrap | `mind`, `journal`, `commit_state` created |
| Initialize again with a different identity | Refused; original identity, journal and revision unchanged |
| Use production-default begin/complete without a provider | Both stop with `Task 'memory_recall' has no complete provider/model assignment or fallback.`; state unchanged |
| Use deterministic local Steward adapter | Begin ready, completion committed; identical completion retry leaves state unchanged |
| Restart after that interaction | One initialization, one interaction and one current-state checkpoint remain; revision 3; `commit_receipts` also exists |

The deterministic adapter demonstrates storage/lifecycle/idempotency wiring. It
does not verify an external model, provider quota, HTTP OAuth, Body communication,
or Surreal Cloud write compatibility.

One-off probes and logs remain outside the repository in the original local
workbench: `local_surreal_setup_probe.py`, `local_surreal_setup_result.json`,
`local_surreal_account_probe.py`, `local_surreal_account_probe.before.json`,
`local_surreal_account_probe.result.json`, `local_surreal_query_matrix.result.json`,
`signup-account-tests.log`, `signup-portal-tests.log`, and `signup-full-tests.log`.
They are local diagnostic artifacts, not prerequisites for the committed tests.
Reproduce the committed signup/login regressions from the repository root with:

```shell
python -m unittest discover -s tests -p test_accounts.py -v
python -m unittest discover -s tests -p test_portal_accounts.py -v
```

## First-account repair and verified behavior

Before repair, the actual `AccountService.create` local test persisted an unnamed tenant Mind
and account record, but signup confirmation and login failed during registry
readback with the installed `surrealdb 2.0.0` embedded driver:

`CommitConflict: Versioned error: A deserialization error occured: Invalid revision 102 for type Value`

After closing and reopening storage, counts were: one Mind, one runtime account
record and one commit-state record; journal, memory, receipts, diagnostics and
evidence were empty. Do not blindly retry account creation: a failed response
can already have persisted the account/Mind.

Controlled tests isolated the driver failure to concurrent embedded SurrealKV
handles on the same path. After a second handle writes, the first can fail to
read later writes; single-handle KV and corresponding `mem://` cases pass.
Closing/reopening both handles restores readable records. Changing `query_raw`
to `query` or `select` does not fix the affected handle. The precise native
engine internals and Cloud behavior were not tested by these reproductions.

The local repair:

- Signup initializes its Surreal tenant through the registry's existing
  connection without opening or closing a second engine. Bound queries and
  normal remote SDK response handling remain unchanged.
- Account routing now uses explicit `account_mind_id`, separate from runtime
  storage's `mind_id` metadata. Signup readback and login preserve that selector.
- Supported historical generated tenant mappings remain readable. Old unscoped
  and root-scoped account records retain legacy selection. Multiple matching
  global account records fail closed; non-account scoping is unchanged.

The original reproduction now creates and reads back the account, authenticates
to its correct unnamed Genesis Mind, and preserves all three records after
reopening. Fourteen account regression tests and three HTTP-route tests pass:
two-account memory isolation, distinct sessions, restart/root-ID changes,
duplicate signup without another Mind or password replacement, wrong/inactive
credentials, legacy record shapes, explicit mapping precedence, and ambiguous
selectors failing closed. The HTTP tests use the real existing HTML/JSON routes
in process without starting MCP/Body lifespans or contacting a provider.
The full regression suite passes: **521 tests, 7 skipped**. The first isolated
runner omitted the repository root and could not import two existing scripts
test modules; correcting that import path resolved the discovery errors.

Historical normalization recognizes the generated tenant-ID format actually
produced by signup and excludes matching scoped-ID metadata. A canonical old
record whose migration-added root metadata itself has that exact generated
format is inherently ambiguous without other evidence. Login does not rewrite
or merge existing records.

## Remaining setup gaps

- Signup directly initializes its tenant Mind and does not append the
  initialization journal entry written by explicit service initialization.
- Portal provider/task setup uses root application registries; account tenant
  services use their own registries. Account-scoped configuration is unproved.
- ChatGPT MCP cognition uses the root lifespan service; OAuth-account subject to
  tenant cognition routing has not been demonstrated end to end.
- The cognitive API's `get_core` also returns root application state, despite
  middleware attaching tenant storage. Consistent account-scoped cognition is
  a remaining source-level routing gap, not part of this signup/login repair.

Accordingly, root initialization and signup/login work locally; complete
per-account model setup and account-scoped MCP cognition remain unproved.

## Smallest next setup slice

The dedicated database-scoped Editor `axiom_runtime` is now configured for the
bounded Cloud check; the separate reader remains unchanged. The two authorized
Cloud checks authenticated successfully but stopped at missing-table reads.
The next step is approval to publish/merge this local bootstrap repair and run
the [same bounded check](SURREAL_RUNTIME_CHECK.md) once against its exact repaired
source pin. No new user, permission expansion, import or reset is required.

Storage success does not resolve the routing/model gaps above. Subsequently prove
one account reaches its own initialized Mind and configured Memory Recall task
through begin/complete and restart, using synthetic isolated data. Stop on partial
signup, wrong-tenant routing, duplicate commits or missing provider configuration.
Full MCP startup includes a tenancy probe that writes and deletes synthetic
records; it must not be treated as a harmless read-only check.

Before cutover, rollback is simply stopping the test and retaining existing
Mongo/service settings. There is no migration to reverse. No existing local or
Cloud database was reset; automated tests clean up only their own temporary data.

## Why the workflow SHA changed

The successful reader preflight ran `d24fa424`, because it was dispatched with
`--ref main` after the owner added `skills/drafts/axiom/SKILL.md` at 13:42:40 UTC.
Its sole parent is `118464c`; the only change is that 62-line skill draft. No
initialization, storage, workflow or authentication code changed between them.
The draft and all unrelated work were preserved. The repair was tested locally;
its publication and merge retain `[skip render]`. No deployment or Cloud write
is part of this change.
