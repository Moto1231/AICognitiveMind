# Autonomous Development Loop

## Purpose

This loop lets a human define desired Cognitive Mind behavior while implementation and verification
can proceed through GitHub without requiring the human to copy terminal output between the developer
and the Codespace.

The human remains the architectural authority. Automation has delegated implementation authority,
not unlimited authority to change the Mind's architecture.

## Development cycle

A single implementation cycle is:

```text
Behavioral requirement
        ↓
Code change committed to GitHub
        ↓
Codespace safely fast-forwards to the commit
        ↓
Uvicorn reloads the runtime
        ↓
GitHub Actions verifies the loaded commit
        ↓
Static + unit checks
        ↓
Live behavioral acceptance test
        ↓
Pass / Fail
```

Behavioral acceptance cases live in `acceptance/cases.json` and are executed by
`scripts/run_acceptance.py` against the live API.

The live runner verifies `/debug/revision` before testing. It will not grade a stale runtime.

## Mandatory human checkpoints

Automation stops and reports to the human when any of the following occurs:

1. **Three consecutive failed implementation/test cycles.** Report what was attempted, what was
   learned, and the unresolved obstacle before another implementation attempt.
2. **Architectural boundary change.** Stop before changing persistence design, cognitive boundaries,
   governance, security model, or externally visible API semantics merely to satisfy a test.
3. **Environmental failure.** If the failure is infrastructure, networking, Codespace, MongoDB,
   model-runtime, or GitHub-related rather than product behavior, stop rather than masking it with a
   code workaround.
4. **Principle conflict.** If requested behavior conflicts with an accepted architectural principle or
   ADR, bring the conflict to the human instead of silently choosing one side.
5. **Acceptance achieved.** Stop when the requested behavior passes and summarize the implementation.

Passing a behavioral test is not permission to violate architectural integrity. Hard-coding a test
answer, bypassing stewardship, weakening governance, or otherwise making the system less correct is
not an acceptable implementation even if the test becomes green.

## Safe Codespace synchronization

`scripts/dev_sync.sh` watches the selected remote branch and performs only fast-forward updates.

It refuses to synchronize when:

- the Codespace is on a different branch;
- the working tree contains local changes; or
- the remote history is not a fast-forward from the local checkout.

This deliberately favors stopping for human review over overwriting local work.

## Acceptance contract

Each case currently supports:

- `name` — stable behavior name;
- `message` — the human message submitted to `/v1/mind/interactions`;
- `must_contain` — case-insensitive text fragments that must appear in the response; and
- `must_not_contain` — case-insensitive text fragments that must not appear.

The contract should remain behavioral rather than wording-exact. A valid Cognitive Mind response
should not fail merely because the model chose different conversational phrasing.

More sophisticated semantic evaluation can replace or extend these primitives later without changing
the development protocol.

## One-time operator setup

The live Codespace must:

1. run the Cognitive Mind API with Uvicorn reload enabled;
2. expose the API port to GitHub Actions for the duration of autonomous testing;
3. configure repository secret or variable `COGNITIVE_MIND_TEST_URL` with the public API base URL;
4. run `bash scripts/dev_sync.sh codex/autonomous-acceptance-loop` in a separate terminal.

Administrative foundation endpoints remain protected by `ADMIN_TOKEN`. The acceptance runner uses only
normal interaction, health, and revision endpoints.
