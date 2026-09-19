# Development Workflow

## Default operating model

Development is GitHub-first.

```text
change
  ↓
GitHub branch
  ↓
pull request
  ↓
GitHub Actions fresh Ubuntu machine
  ↓
unit + integration + MCP continuity validation
  ↓
merge to main
```

A Codespace is no longer the default development machine.

## Why

The repository already supports development through direct GitHub branch/file operations and validates
each pull request on a fresh GitHub-hosted runner.

This keeps ordinary development independent of Codespaces compute/storage allowance while preserving
the same tested merge discipline.

## Workstreams

Mind and Body remain parallel:

```text
Mind branches ─────┐
                   ├── main
Body branches ─────┘
```

Each change should normally use a focused branch and pull request.

Examples:

- `feature/mind-...`
- `feature/body-...`
- `fix/...`
- `docs/...`
- `ops/...`

## Validation machine

Pull requests targeting `main` run the project validation workflow on `ubuntu-latest`.

The workflow currently verifies:

- all Python unit tests;
- Mind behavior;
- Body behavior;
- storage adapters;
- portal behavior;
- MCP server import;
- MCP stdio continuity;
- MCP Streamable HTTP continuity;
- Mongo-backed integration behavior.

MongoDB is provided as a temporary service container for the job.

The runner and service disappear after the job finishes.

## Concurrency rule

Only the newest validation run for a pull request needs to finish.

The workflow uses GitHub Actions concurrency cancellation so a newer commit to the same PR cancels an
obsolete in-progress validation run.

## Codespaces policy

Use a Codespace only when the task genuinely needs an interactive Linux environment, such as:

- exploratory runtime debugging;
- interactive MCP host testing in VS Code;
- a demo that specifically depends on the Codespace environment;
- reproducing a Linux-only issue that CI logs cannot diagnose.

Do not create or keep Codespaces merely to perform routine edits, tests, or PR validation.

## Local Windows policy

The local Windows machine is the Body hardware laboratory.

Use it when development requires actual local devices:

- camera / eyes;
- microphone / ears;
- speakers / mouth;
- avatar/display rendering;
- operating-system audio/video APIs;
- latency and device-selection testing.

Pure Body-domain logic remains testable in GitHub Actions and should stay independent of hardware.

## Development ownership

GitHub is the durable source of truth.

The normal collaboration loop is:

1. create branch from current `main`;
2. make the smallest coherent change;
3. add or update tests;
4. open a draft PR;
5. let Actions validate on a fresh machine;
6. fix the same branch when validation exposes a problem;
7. mark ready and merge only after green validation;
8. start the next Mind or Body branch from updated `main`.

This lets multiple workstreams proceed without one long-lived development machine.

## Persistence caveat

GitHub Actions runners are intentionally disposable.

Do not depend on a runner for persistent Mind state. CI uses temporary test data.

Real persistent Mind state belongs in the configured durable storage environment, not on the Actions
runner filesystem.

## Cost-control rule

Prefer:

1. GitHub branch/file operations;
2. GitHub Actions validation;
3. local Windows hardware testing when required;
4. Codespaces only as an interactive exception.

Do not attempt to extend allowance by repeatedly creating replacement Codespaces; development should
not depend on that pattern.
