# Everyday interaction, identity and evidence

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Talk to one integrated Mind

I speak as Axiom in first person. The current reasoning model, Memory Steward and Body are functions of the same system. Changing a model does not itself create a new identity or erase stored history.

You can ask for ordinary work directly: “Summarize this document,” “Help me understand this error,” or “Continue the project using the current source.” State important constraints and identify the source you want used. A prior conversation, a supplied document and a live observation are different kinds of evidence.

The lifecycle below describes the packaged protocol while enabled in effective configuration. An authenticated Administrator can change cognitive settings; host permissions, argument schemas and authentication remain enforced.

## What happens around a turn

> This lifecycle and The Breaker behavior were reviewed against `56dd9a5faefcc6adde578ed49a6aaad30e968153` on 2026-10-27. Other sections retain their stated review revisions. This is source review, not a live persistence-failure exercise.

| Stage | What it means for you |
| --- | --- |
| Begin | I submit your actual message and this conversation's working context. The Steward decides whether memory recall is needed. |
| Orientation | I read returned identity, state, effective instructions and any recalled material. |
| Work | I use the authorized tools and evidence needed for your request. |
| Completion | I submit the intended response and material evidence for Steward review and interaction commit, using the begin key. |
| Response | I present the answer without waiting for memory persistence. Ordinary persistence failures remain operational diagnostics unless The Breaker requires a report. |

“No recall needed” is a valid outcome. It does not mean that I ignored the current conversation. Conversely, a successful status read is not a substitute for begin/complete.

Each separate conversation starts with its own working context and receives its own interaction key. A key is retained for a retry of that same completion, not borrowed from another chat. If completion is uncertain, the packaged protocol allows one identical retry; it does not authorize repeating a completed external action.

## Presentation-first persistence and The Breaker

Presentation is the first priority. Text does not wait for memory persistence. During a voice turn, the one completion call may overlap speech playback, but the next turn waits until playback and completion settle.

The Mind-scoped persistence circuit is **The Breaker**. Packaged defaults open it after either five consecutive failed final interaction outcomes or 35 failed outcomes in the rolling last 100. A success resets the consecutive streak but remains part of the rolling window. The failure that reaches a threshold is still presented without a persistence warning. If a later recovery also fails while the circuit is open, the runtime reports the continuity problem.

An isolated persistence failure, a successful identical retry, a degraded Steward review, failure counts and the failure that opens The Breaker stay out of ordinary conversation. They remain available in typed diagnostics and Administration. This suppression covers interaction and memory persistence only; it does not hide authorization, security, corrupt response delivery or failure to establish the interaction.

An Administrator can change both thresholds, the rolling window, provider request timeout, Steward assessment deadline and rate-limit retry wait cap in **Administration → The Breaker**. Each interaction keeps the settings snapshot captured when it began.

## Working context versus durable memory

Working context tracks the active topic, participants, speaker, addressee and unresolved references for the conversation. Durable memory is separately curated by the Steward. The journal records experiences; it is not identical to either a chat transcript or the curated-memory list.

Useful requests include:

- “Use that only for this conversation.”
- “This corrects the earlier assumption; here is the evidence.”
- “Tell me which parts come from memory and which are inference.”
- “Check whether that was actually saved before relying on it.”

Do not assume that every sentence becomes a durable memory. Suggestions to remember something are inputs to Steward review, not direct proof of a committed record.

## Current state and uncertainty

The default Current State protocol preserves supported answers and explicit unknowns. A context-changing event invalidates affected fields, not the whole identity. A new host alone should not restart completed questions or erase valid context.

When who is speaking or where the interaction is taking place remains unresolved, I should check available context and ask a short grounding question. A general answer is enough; an address is unnecessary. You may defer or decline.

Example:

> “I'm Alex. I'm at my sister's apartment. That is my report; you haven't seen the room.”

This can establish a self-reported name and setting. It does not prove the sister is present, that Alex lives there, or that a camera independently confirmed the place.

If the setting later changes, say so. “I'm home now” should update the relevant location context while preserving earlier history.

## Evidence distinctions

| Evidence | Appropriate statement | Inappropriate promotion |
| --- | --- | --- |
| Direct user report | “You told me you are at an apartment.” | “I can see your apartment.” |
| Supplied image | “The image shows a table and doorway.” | Naming an unseen location from generic furniture |
| Audio transcription | “The transcription contains these words.” | Claiming a speaker's identity without support |
| Recalled record | “A prior record says…” | Treating historical presence as current presence |
| Provider configuration | “This model is selected.” | “Its quota and every capability work.” |
| Source or fixture test | “The handler implements this / the test passed.” | “Your authenticated phone workflow succeeded.” |

Preserved sensory evidence has its own capture time and integrity references. Reading an old artifact is not live sensing. If the original media is missing, the stored interpretation can still be discussed as a record, but it must not be presented as newly inspected media.

## Bounded questions and recovery

The default state protocol calls for a short context check and bounded retrieval. It does not require endless research to fill every unknown. An unsuccessful attempt can remain explicitly unresolved, with the reason and a useful condition for retry.

If required startup fails, I should state the specific failure and pause dependent work unless you explicitly authorize a fallback for that task. An exception in another project does not silently apply here.

If a response cannot be committed, preserve the actual external result and avoid recreating it merely to retry completion. Routine persistence trouble remains silent until The Breaker requires reporting; an explicit diagnostic request can still inspect it.

## A practical continuity check

1. Give a small non-sensitive preference in a working connected host.
2. Confirm the interaction completed.
3. Change the reasoning model while retaining the same authorized Mind connection.
4. Ask about that preference, with enough context to identify the topic.
5. Inspect the answer's grounding and memory/history if needed.

This is a procedure to perform, not a claim that every host/model combination has been tested. The host's context limits, tool availability and provider failures can still affect the experience.

## Source references

- [plugins/axiom-mind/skills/axiom/SKILL.md](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/plugins/axiom-mind/skills/axiom/SKILL.md)
- [plugins/axiom-mind/skills/axiom-continuity/SKILL.md](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/plugins/axiom-mind/skills/axiom-continuity/SKILL.md)
- [plugins/axiom-mind/skills/axiom-current-state/SKILL.md](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/plugins/axiom-mind/skills/axiom-current-state/SKILL.md)
- [src/aicognitive_mind/mcp_service.py](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/mcp_service.py)
- [src/aicognitive_mind/continuity_settings.py](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/continuity_settings.py)
- [src/aicognitive_mind/state_context.py](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/state_context.py)
- [src/aicognitive_mind/host_context.py](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/host_context.py)
