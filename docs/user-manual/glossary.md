# Glossary

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

| Term | Meaning in this manual |
| --- | --- |
| Axiom / Mind | The integrated persistent identity and cognitive system |
| Reasoning host | The connected runtime/model currently performing reasoning |
| Body | Device/media interface for observation and expression |
| Memory Steward | Independent internal process governing recall and retention |
| Working context | Conversation-scoped topic, participants and unresolved references |
| Durable memory | Curated stored information, distinct from the journal |
| Journal | Recorded cognitive experiences and revisions |
| Current state | Ledger of supported current answers, provenance and unknowns |
| Grounding | Evidence supporting an assertion or record |
| Self-report | Information a person supplies, without implying independent observation |
| Inference | A conclusion drawn from evidence, whose uncertainty remains relevant |
| Sensory artifact | Exact preserved admitted media with integrity/capture references |
| Interpretation | What an observation is understood to mean; distinct from the media |
| Genesis | Initial developmental state; signup creates an unnamed Mind |
| Account scope / tenant | The Mind/resources selected by an authenticated account |
| Root / legacy scope | Deployment-level or historical scope, distinct from a new account's Mind |
| Administrator | Authority established by the implemented authentication checks |
| Foundation | General or task-specific cognitive instruction/identity configuration |
| Skill | A full instruction document with effective configuration flags |
| Required / Load at startup | Skill flag that includes full content at startup when enabled |
| Protected | Policy flag; not an Administrator lockout |
| Behavior | Named reusable instruction selected for task use |
| Task assignment | Provider/model pool, routing and behavior membership for a task |
| Endpoint | Saved model-provider connection and selected model |
| Model discovery | Retrieval of available model IDs and optional metadata |
| Capability label | Provider-reported or documented feature information, not a functional test |
| Probe | Narrow synthetic functional check, such as recall/review tool calling |
| MCP server | External server exposing callable tools |
| Tool | Named operation with arguments and possible external effects |
| Ordered fallback | Try the complete primary candidate, then alternates in order |
| Daily round-robin | Rotate the task pool's starting position by UTC date |
| Cooldown | Temporary exclusion of a failed configuration/model candidate |
| Draft | Unsaved form or repository skill content, depending on context |
| Revision conflict | A save cannot safely use an older loaded version |
| Idempotency key | Begin-issued key used to commit/retry one interaction without duplication |
| Checkpoint | Verified recovery assets; not merely an unverified copied ZIP |
| Source reviewed | Behavior checked against implementation at a recorded commit |
| Device verified | A specific actual hardware/browser workflow was successfully tested |

## Source references

- [src/aicognitive_mind/mcp_service.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/mcp_service.py)
- [src/aicognitive_mind/effective_skills.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/effective_skills.py)
- [src/aicognitive_mind/provider_routing.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/provider_routing.py)
- [src/aicognitive_mind/host_context.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/host_context.py)
