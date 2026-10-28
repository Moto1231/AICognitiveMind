# Model-backed Memory Steward

The MCP interaction lifecycle always consults a model-backed Memory Steward.
Consultation is mandatory; storage retrieval is the Steward's decision.
The deterministic selection in ADR 0003 remains an offline storage-rule test
adapter, not a production fallback when a model fails.

The server loads `skills/memory-steward/SKILL.md` from the installed Python
package on each assessment. It supplies the current message, Mind identity,
persisted state and explicit host working context. The Memory Recall task profile
supplies the provider/model, configured fallbacks and selected behavior layers.
The Steward does not inherit skills or context from the reasoning host implicitly.

At begin, the model first chooses whether retrieval would fill a material gap.
`no_recall_needed` performs no memory/journal search and returns no recalled records.
Targeted memory, journal or recent-history searches are available only after
the model requests them. The model selects returned sources and synthesizes a
brief. `no_relevant_memory` distinguishes an unsuccessful search from skipping one.
The host receives the brief and source metadata, not repeated raw memory records.

At complete, the model reviews the exact message, response, updated host context,
current evidence and optional host suggestions, including an empty suggestion list.
It may generate grounded learning, reject suggestions, or retain nothing. Quotes
must match supplied evidence; an answer alone cannot ground an external fact.
Only model-selected evidence and belief operations enter the existing storage
validation. Identity/value governance, evidence scope and atomic commit rules remain
enforced in code. The whole interaction is journaled even when no learning is saved.

The host waits for begin before dependent research, task tools or final reasoning.
Independent preparation may overlap only when the host supports it and it cannot
depend on missing context. Task-specific skills are loaded when their task applies.
The host freezes the exact intended response before complete. Presentation is
first-priority: text does not wait for memory persistence, and a voice turn may overlap
its single synchronous completion call with playback while keeping the microphone
closed. An identical uncertain retry reuses the same key, answer and receipt; it never
replays speech or external actions. The completion result's `presentation.allowed`
field is authoritative when the persistence circuit requires recovery.

Both recall and completion review use the saved Memory Recall provider pool.
Within an assessment, a successful provider continues handling its search and
finish decisions. A provider error or rejected decision advances to the next
eligible fallback; a rejected provider is not revisited later in that assessment.
Decision rejection includes invalid phase schemas, unsupported references and
memory grounding that fails the existing evidence checks. These checks are not
relaxed to make failover succeed. A single eligible provider retains one bounded
review-correction attempt. Candidate state belongs to the assessment, not the
shared dispatcher, and a new assessment starts with the configured priority and
existing provider cooldowns. Successful traffic is not rotated by this failover
mechanism; scheduled rotation remains a separate, explicitly selected option.

Each assessment permits at most three searches shared across provider changes,
bounded attempts for each eligible model, and sixty seconds overall. Search
rounds do not consume another model's opportunity to finish: once the search
budget is spent, remaining candidates receive the finish-only schema. Invalid
decisions and HTTP, transport or action-wrapper failures advance through the
finite eligible pool within the shared deadline. The normal skip path uses one
model decision and no search. Exhausting the eligible provider pool is distinct
from reaching the overall deadline before the chain completes. Both are explicit
errors; neither is reported as an intelligent no-recall or no-learning decision.
An exhausted or timed-out completion review atomically commits the interaction journal
and receipt with `memory_review.outcome=unavailable` and zero memory, evidence, belief,
or reframe writes. Retrying that committed degraded outcome reuses its receipt without
replaying providers. A pre-review transport/storage failure remains eligible for one
identical retry. Successful idempotency receipts continue to prevent duplicate commits.

The final persistence outcome is recorded separately in a content-free, Mind-scoped
runtime record. One interaction key contributes at most one outcome: a failed attempt
followed by a successful identical retry becomes success. The presentation circuit opens
at the revisioned, Mind-scoped thresholds managed on The Breaker's Administration form.
The packaged defaults are five consecutive failures or 35 failures in the rolling last
100 outcomes. The same form owns the provider-request timeout, total Steward-assessment
deadline and bounded rate-limit retry wait. An interaction uses the settings revision
captured when it began. The failure
that reaches a threshold remains presentable; a later failed recovery is withheld. A
success resets the consecutive streak but does not erase rolling history.

The presentation circuit is named **The Breaker**. It is also the user-facing persistence
error boundary. Below it, and on the threshold-reaching failure, normal responses remain
silent about persistence errors; typed details remain operational diagnostics. Completion
sets `presentation.report_persistence_error=true` only when a later recovery fails while
The Breaker was already open. Explicit diagnostic requests can still inspect the suppressed
details, and non-persistence safety, authorization, delivery and connection errors are never
hidden by this policy.

Configure a working Memory Recall endpoint in Task Profiles before use. Model tests
use scripted responses; the explicitly named `mcp_test_server.py` harness tests
transport/storage without consuming API quota and is not used by production.
