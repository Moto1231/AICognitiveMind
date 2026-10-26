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
The exact intended response is committed by complete before it is presented to the
human. Retrying complete with the same key and unchanged input reuses its receipt.

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

Each assessment is limited to four returned model decisions and sixty seconds.
Invalid decisions consume that same decision budget. HTTP, transport and action
wrapper failures advance through the finite eligible pool within the shared time
limit. The normal skip path uses one model decision and no search. Provider
exhaustion, invalid JSON, invented references, missing grounding and exhausted
budgets are explicit errors; none is reported as an intelligent no-recall or
no-learning decision. An exhausted review does not commit memories or the
interaction journal.

Configure a working Memory Recall endpoint in Task Profiles before use. Model tests
use scripted responses; the explicitly named `mcp_test_server.py` harness tests
transport/storage without consuming API quota and is not used by production.
