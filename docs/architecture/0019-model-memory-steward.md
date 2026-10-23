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

Each assessment is limited to four model rounds and sixty seconds. The normal
skip path uses one model round and no search. Provider failures, invalid JSON,
invented references, missing grounding and exhausted budgets are explicit errors;
none is reported as an intelligent no-recall or no-learning decision.

Configure a working Memory Recall endpoint in Task Profiles before use. Model tests
use scripted responses; the explicitly named `mcp_test_server.py` harness tests
transport/storage without consuming API quota and is not used by production.
