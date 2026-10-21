# Interaction latency diagnostics

Interaction timing is enabled by default and writes `timing ...` lines to the
server's stderr. Set `AXIOM_TIMING=0` before starting the process to disable it.
The timing lines contain operation and phase names, durations, row/token counts,
and exception class names. They do not contain message text, response text,
recall tokens, idempotency keys, host leases, or exception messages. The existing
interaction transport trace remains a separate diagnostic record with its
existing payload and access behavior.

## Reading a slow begin or complete

Three nested timers separate time in recall from time in transaction and MCP
work. Their totals overlap; do not add the nested totals together.

| Timer | Work measured |
| --- | --- |
| `begin_interaction` / `complete_interaction` | Core service phases, including recall, state, and Steward work. |
| `commit.atomic method=...` | Receipt lookup, revision lookup, staging, the service method, result serialization, transaction commit, and recovery receipt lookup when needed. |
| `mcp.begin_interaction` | Full MCP tool body: context preparation, atomic service call, Body queue snapshot, active host lookup, queue summary, and trace write. |
| `mcp.complete_interaction` | Full MCP tool body: context preparation, request trace, atomic service call, response trace, or error trace on failure. |

For example, a short core `begin_interaction` followed by a slow
`commit.atomic ... commit=...` identifies work after recall but before the
atomic service returns. A slow `mcp.begin_interaction ... body_queue=...` or
`active_host=...` identifies Body status reads after that return. The `trace`
phase includes building and writing the begin trace. Completion reports
`trace_request`, `trace_response`, and, on service failure, `trace_error`.

The outer atomic and MCP timers log from `finally` blocks, so completed phases
remain visible when a later phase raises. Failure lines record only the
exception class. The existing exception, retry receipt rules, transaction
semantics, and tool result are preserved. A matching receipt returns the prior
result without rerunning or recommitting the service method.

These timers start inside the server tool body. Authentication, transport
dispatch before invocation, response encoding after return, and client/network
time are outside that boundary. Measure those separately if client elapsed time
substantially exceeds the outer MCP total. Each timer computes its total before
writing its own log line.

## Recall candidate retrieval

Plugin/app mentions and skill links are removed from recall tokenization; the
original user input remains available to the interaction brief and journal.
Ordinary Markdown links contribute their visible label. When association expansion
does not add any retrieval tokens, recall reuses the first candidate result
instead of issuing the same query twice.

Mongo journal and memory stores provide `query_candidates(tokens, limit=256)`.
Each collection has a `recall_text_v1` compound index with `mind_id` followed by
a wildcard text field. The index uses `default_language="none"`, a reserved
language override field, and simple collation. Mongo indexes string content in
existing documents when it builds the index and maintains it on subsequent
direct or transactional writes. Cognitive documents do not require rewriting.

Candidate retrieval searches indexed words across the authenticated Mind's
history and bounds the result to at most 1,000 rows. It accepts up to 64
normalized search words, stripping user-supplied phrase and negation operators.
For dot/hyphen compounds such as `gpt-6`, the first four safe compound tokens in
alphabetical order use separate native quoted-phrase queries. Their component
words are excluded from the general OR query so newer `gpt`-only records cannot
crowd out an older `gpt-6` match or other independent search terms. Remaining
compounds beyond that cap use the general native word query.

Candidate retrieval runs at most five indexed queries in parallel: up to four
compound queries and one general word query. Each query orders its matches
newest first. With mixed search terms, each compound contributes at most 64
protected candidates; a sole compound can use the entire requested bounded
limit. Protected candidates precede the general candidates, records are
deduplicated by storage ID, and the merged page retains the requested limit.
Each database query has a five-second `maxTimeMS` limit. A genuine zero-match result
falls back to a bounded recent-history query; empty tokens use recent history
directly. The candidate path performs no total-count query. A missing index or
query error is surfaced instead of being reported as an empty result.

Mongo's native text tokenizer matches words. Portal searches retain their
existing literal, case-insensitive substring behavior. A partial substring
visible in a portal search can therefore produce different recall candidates.
The index has no language stemming or stop-word removal.

The first startup after this change can take longer while Mongo builds both
indexes over existing history. Index maintenance also adds storage and write
work. Mongo allows one text index per collection; an incompatible existing text
index causes startup to fail visibly instead of being dropped automatically.
Check startup logs and readiness separately from steady-state interaction
latency when deploying this change.

## Focused verification

`tests/test_interaction_timing.py` uses a deterministic clock to attribute
receipt, revision, commit, queue, host, and trace delays. It also checks failure
logging, receipt retries, uncertain-commit recovery, and absence of payloads and
exception messages in timing logs. Existing MCP surface and reliability suites
exercise tool delegation, rollback, receipts, concurrency, and restart behavior.
`tests/test_mongo_retrieval.py` checks scoped native queries and their bounds,
error propagation, and portal search compatibility. Its optional MongoDB tests
insert old-format records before index creation, find records beyond a recent
window, inspect the native text query plan, and exercise compound and independent
word matches without allowing newer partial terms to crowd them out. They also
verify that startup preserves an incompatible existing text index and fails.
The dedicated `mongo-retrieval` CI job runs these tests against MongoDB 8.0.
These checks establish local database and service behavior; deployed latency and
the production query plan require a separate live measurement.
