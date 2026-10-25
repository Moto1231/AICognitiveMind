# Task Configuration and provider routing

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Open a task

Choose **Administration → Task Profiles**. The page heading is **Task Configuration**. Choose a task button in its internal **Task selection** panel.

| Visible task | Configuration purpose |
| --- | --- |
| Reasoning | Connected-host reasoning or configured reasoning assignment |
| Vision | Visual interpretation |
| Audio/Transcription | Audio input/transcription |
| Audio/Voice | Speech output, including voice-reference configuration |
| Coding | Coding task instructions/assignment |
| Drawing & Image Generation | Image-generation task instructions/assignment |
| Summarizing | Summary task instructions/assignment |
| Memory Recall | Provider used by the independent Memory Steward for recall and review |
| Web Research | Research task instructions/assignment |
| Structured Extraction | Structured-data extraction instructions/assignment |

A task appearing in this list does not guarantee that every provider supports its payload or that the current host exposes an action to execute it.

## Assign a primary endpoint and fallbacks

1. First complete and save the endpoint's model in [Endpoints → Models](providers-and-models.md).
2. Open the desired task.
3. Choose the primary endpoint.
4. Choose **Add fallback** for each alternate.
5. Select a saved endpoint in each numbered fallback row.
6. Remove unfinished rows.
7. Choose the assignment **Save**.

The selected endpoint supplies its saved model. The standard model selector inside the task form is hidden in this revision; model choice belongs to the endpoint editor.

Reasoning can use **Connected reasoning host**. Selecting provider endpoints for other tasks does not change which model the external chat host selected for itself.

The task's endpoint-area Save and lower Save use the same assignment-save handler. They save endpoint choices, fallback list, routing mode and selected behavior IDs together. They do not save the separate Task Foundation editor or an unsaved shared Behavior catalog draft.

## Select behaviors

1. Add/edit and save a reusable behavior in the shared **Behavior** catalog.
2. Open the task's **Behaviors** section.
3. Check the intended behaviors.
4. Save the task assignment.

**Select behaviors** focuses the selection area; it does not create a new library behavior. A library-disabled behavior is labeled accordingly. Explicit selections control membership; do not assume every library entry applies to every task.

## Edit the Task Foundation

1. In the task, locate **Task Foundation**.
2. Choose its **Edit** control.
3. Change the instruction text.
4. Choose the foundation's own **Save**.
5. Read its confirmation separately from the assignment Save.

This editor loads the current cognitive-configuration revision before editing. **Cancel** restores its original text. A saved blank remains blank. Switching tasks cancels an unsaved foundation draft and discards unsaved task assignment changes.

## Ordered routing

With **Provider order → Primary, then fallbacks** (ordered routing), the complete primary candidate is tried first, followed by the configured fallbacks in list order. Duplicate endpoint/model candidates are deduplicated. Candidates in active cooldown are skipped.

Example pool:

| Order | Example endpoint |
| --- | --- |
| Primary | Provider A — model selected |
| Fallback 1 | Provider B — model selected |
| Fallback 2 | Provider C — model selected |

If A is unavailable and B succeeds, C is not needed for that request. Fallback does not repair an invalid response already presented to the user; it is part of the task dispatch process.

If every candidate fails or all are cooling down, the task reports an explicit error. Configuring many fallbacks does not guarantee service availability.

## Optional daily UTC rotation

Choose **Daily round-robin** in the task's routing selector, then Save. It rotates the starting position of the same primary/fallback pool once per UTC date. This is per task, not a global switch.

The current algorithm uses the UTC date's ordinal modulo the pool size. Consequently, enabling it does not guarantee the first day begins with the entry labeled primary. For a pool A/B/C, a day might start B → C → A; the next starts C → A → B.

All requests on the same UTC date use the same starting position, including after a restart. Cooldown filtering happens after rotation; unavailable entries retain their pool positions for later use. It is not per-request load balancing, and it does not rotate at your browser's local midnight.

## Cooldown reference

| Failure | Current cooldown behavior |
| --- | --- |
| HTTP 429 | Honor Retry-After/reset hints, bounded to 1 second through 24 hours; default 60 seconds if no usable hint |
| HTTP 401 or 403 | Five minutes |
| HTTP 408, 500, 502, 503, 504 | 30 seconds |
| Transport failure | 30 seconds |
| Other HTTP status | No generic cooldown added by this registry |

Cooldowns persist per Mind and endpoint configuration/model. A changed URL, key or model starts a new availability episode. This is not advice to rotate credentials to evade limits.

With alternatives, a rate-limited candidate falls through; cooldown recording does not sleep for the provider's entire reset interval. The bounded single-provider Steward retry is a separate mechanism.

Use redacted routing/status diagnostics to distinguish **configured**, **cooling down**, and **successfully executed**. Provider names, selected models and credential-present indicators are not evidence of usable quota.

## Practical Memory Steward setup

1. Configure a model endpoint with a passing recall/review tool-calling test.
2. Select it in **Memory Recall**.
3. Add only tested, complete alternates.
4. Keep **Primary, then fallbacks** initially unless daily rotation is intentional.
5. Save.
6. Run a short interaction and verify both begin and completion.

Do not assume the connected chat model automatically substitutes for an unconfigured Memory Recall provider.

## Source references

- [src/aicognitive_mind/static/index.html](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/index.html)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/task_model_assignments.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/task_model_assignments.py)
- [src/aicognitive_mind/task_behaviors.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/task_behaviors.py)
- [src/aicognitive_mind/task_dispatcher.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/task_dispatcher.py)
- [src/aicognitive_mind/provider_routing.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/provider_routing.py)
