# Reliability and external-host handoff

This change implements the September 21 code-review follow-up. Identity and memory remain provider-independent; runtime coordination data lives in separate storage records.

## Cognitive commits

Core interactions, MCP completions, initialization, governed self-name changes, and administrative memory revisions stage their cognitive writes. MongoDB commits them in one transaction; SurrealDB submits one checked transaction. A storage revision rejects concurrent cognitive commits based on stale context. A conflict means the host must begin again and reconsider the new state, rather than blindly replaying a stale proposal.

MongoDB must be a replica set or Atlas deployment. Standalone MongoDB cannot provide multi-document atomicity and is no longer a supported production runtime for these operations. CI starts a disposable replica set and exercises rollback, retry receipts, and snapshots.

`begin_interaction` returns an `idempotency_key`. Pass it to `complete_interaction` and reuse it with exactly the same input on retries. A committed receipt survives server restart and returns the original result. Reusing a key with different content is rejected. Legacy clients may omit the key, but then do not have retry deduplication. Receipts and transaction revisions are operational records, not attributes of the Mind.

The governance gate only accepts complete affirmative self-name commands, such as `Please choose a new name` or `I authorize you to choose your own name`. Questions, quoted commands, hypothetical requests, additional clauses, and negation fail closed. Naming still passes through the Governance Steward and preserves protected identity fields.

## External-host operation

Configure the API and MCP process to use the same persistent database. Separate `mem://` processes do not share state. An authenticated host performs this sequence:

1. Call `attach_reasoning_host(name, model)` and retain the private lease token.
2. Renew with `renew_reasoning_host` while working. The lease lasts 120 seconds.
3. Poll `next_body_interaction`. It returns a request identifier, the user message, and the same identity/memory context as `begin_interaction`.
4. Reason externally; inspect original media with `read_sensory_evidence` when its reference is present. The returned original media is hash-verified. Governed name proposals use `propose_self_name`.
5. Call `complete_body_interaction` with the request identifier, response, and memory proposals. This commits through the same Memory Steward and delivers the response back to the waiting Body. Retry unchanged input if delivery is interrupted.
6. Detach explicitly with `renew_reasoning_host(..., detach=true)` before another host attaches. An expired lease also permits handoff. Old tokens cannot complete requests after another host takes over.

A live host takes precedence over standalone reasoning. A timed-out host request is not silently sent to a second model. The API reports actual active-host metadata separately from the configured primary architecture. Hosts must implement this polling protocol; displaying `External Host` alone does not attach a model.

MCP HTTP binds to loopback by default. Set `MCP_ACCESS_TOKEN` to use a non-loopback bind, and send `Authorization: Bearer <token>`. Use TLS at the deployment boundary for remote traffic. Stdio does not use HTTP authentication. The application password for the browser portal is a separate setting.

## Optional fallback and quotas

`STANDALONE_REASONING_PROVIDER` accepts `disabled`, `echo`, `gemini`, or `openai`; it overrides the legacy `REASONING_PROVIDER`. The default is disabled. Existing explicit provider settings continue to work. Provider construction and Gemini discovery happen only when needed, so missing credentials do not block portal startup.

`STANDALONE_CALLS_PER_MINUTE` defaults to 6 SDK calls. The shared database budget includes tool rounds and evidence reinterpretation. `STANDALONE_QUOTA_COOLDOWN_SECONDS` defaults to 300 after a 429, and `REASONING_TIMEOUT_SECONDS` defaults to 120. These limits apply to Axiom's fallback; an external host controls its own inference budget. SDK-internal transport retries are separate from SDK-call accounting.

The browser filters unchanged visual samples and quiet audio before requesting inference. Unity only advances its visual baseline after a successful request, so a failed frame remains eligible after recovery. Body Model Policy stays separate from reasoning ownership.

## Body transport

Browser pages and Unity clients send an `X-Body-Session` header. Each session has bounded, storage-backed FIFO queues, so API workers share the same pending observations and output. Clients omitting the header use the compatibility `legacy` session and should be limited to one Body. Legacy output GETs retain destructive consumption so older clients do not repeat speech while waiting for acknowledgments they cannot send.

Output GETs return `X-Body-Delivery`. The client acknowledges that receipt through `/v1/body/{face|mouth}/ack?delivery_id=...` after receiving the payload. Unacknowledged output remains available. Acknowledgment means delivery to the client, not successful audio playback. Queue capacity is 32; full queues reject new entries rather than silently discarding existing output. Observation consumption remains destructive, and clients should not blindly replay uncertain observe/consume pairs.

Unity and browser HTTP requests have a 130-second deadline. This bounds blocked cognition gates even if the server never responds. The application does not claim cancellation of a provider call already accepted remotely.

## Retrieval and backup

Status uses database counts. Surreal portal paging filters and slices on the database. Recall ranks at most 256 database-selected candidates per collection, selecting matches across the stored history and using recent entries when there are no matches. This bounds transfer and ranking work; it is not a vector-search implementation, and broad searches with more than 256 matches favor recent matching candidates. Steward-wide belief comparisons still read the full memory collection to preserve their existing correctness semantics.

Portable API backups use a consistent database snapshot and reject oversized exports rather than exhausting memory. The bound is 20,000 rows and approximately 8 MiB per cognitive collection; larger deployments should use the database's native backup facility. Exact sensory media still transfers separately. Portable cognitive archives do not include runtime leases or retry receipts; a full operational restore requires the database backup as well.

Surreal migration imports in one transaction and no longer rolls back by deleting whole tables. Failed transactions preserve unrelated state; post-commit verification mismatches leave the target intact for inspection.

## Validation

Regression coverage includes failed commits, concurrent revisions, idempotent retries, negative naming requests, authenticated HTTP dispatch, isolated Body queues, delivery acknowledgments, provider cooldown, and disk-backed restart continuity. `scripts/mcp_handoff_smoke.py` creates two independent MCP host sessions and server processes against temporary persistent storage. It verifies identity, relationships, memory, retry receipts, and subsequent writes after restart without calling paid models.

Unity batch compilation is checked locally with the installed 6000.0.65f1 editor. Camera/microphone/audio hardware behavior and a live handoff between two real model vendors remain manual acceptance checks. Neither requires resetting or reinitializing Axiom's existing Mind.
