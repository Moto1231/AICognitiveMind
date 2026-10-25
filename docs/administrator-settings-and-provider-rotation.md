# Administrator settings and provider rotation

The authenticated Administrator owns the Mind's cognitive configuration.
Packaged instructions are defaults. Saved text, including an explicit blank,
and saved enabled/required/protected flags take precedence on subsequent
interactions and fresh host instances. Package updates do not overwrite Mind
overrides. Authentication, tenant scope and tool argument schemas remain enforced
by the service.

## Edit and save cognitive settings

- **Administration → Foundations** edits identity (name, pronouns, values,
  commitments, relationships and developmental state) separately from the base
  cognitive contract and startup instructions. Each form has Edit, Save and
  Cancel. Identity changes are committed atomically with their journal entry.
- **Administration → Skills** edits effective Mind skill instructions and the
  enabled, required and protected flags, including Axiom Continuity, Axiom
  Current State and the internal Memory Steward. Saved configuration is distinct
  from a GitHub draft with the same name. Required and enabled skills are supplied
  in full at startup. A disabled internal Memory Steward skill removes its added
  instructions; the software still validates the phase request/response schema.
- **Administration → Behavior** edits the shared behavior catalog, including
  entries previously marked protected or required. Explicit task memberships and
  Administrator removals take precedence over factory membership defaults.
- **Administration → Task Profiles** edits each task's foundation, selected
  behaviors and provider routing. Blank saved foundations stay blank.

Settings forms retain isolated drafts until Save. Cancel discards the draft.
Revision checks reject stale identity, cognitive configuration and skill saves
and stale behavior catalog saves that supply an expected revision.

## Prepare the five additional connections

In **Administration → Endpoints, Servers & Tools → Endpoints**, choose
**Prepare five provider connections**, then Save the staged batch. Existing
connections and task assignments are preserved. A provider already present at
the same base URL is skipped. The new profiles have no invented key or model.

| Provider | API base | Provider documentation |
| --- | --- | --- |
| Cerebras | `https://api.cerebras.ai/v1` | [Compatibility](https://inference-docs.cerebras.ai/resources/openai) |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | [Compatibility and function calling](https://ai.google.dev/gemini-api/docs/openai) |
| Together AI | `https://api.together.ai/v1` | [Compatibility](https://docs.together.ai/docs/inference/openai-compatibility) and [function calling](https://docs.together.ai/docs/inference/function-calling/overview) |
| OpenRouter | `https://openrouter.ai/api/v1` | [Tool calling](https://openrouter.ai/docs/guides/features/tool-calling) |
| SambaNova | `https://api.sambanova.ai/v1` | [Function calling](https://docs.sambanova.ai/docs/en/features/function-calling) |

These five additions leave any existing Groq or Mistral connection in place.

For each connection, choose Edit, enter its own API key in Administration,
discover available models, select a model and choose **Test tool calling**.
The test sends up to two small synthetic requests using the same recall and
review function schemas as an interaction. It has a 20-second timeout per
request, no retries and makes no configuration or memory writes. It reports
failure without exposing a provider response body or credential. Save the
connection after choosing the model. Model discovery by itself does not verify
function calling. A successful sample does not guarantee future quota or uptime.

No account creation, trial allowance or provider billing is implied by preparing
a profile. Model availability and limits come from the individual provider.

## Enable daily round-robin and fallback

In **Task Profiles → Memory Recall**, select Groq and the completed additional
connections as the primary/fallback pool, choose **Daily round-robin**, and Save.
Daily rotation advances the first candidate once per UTC date, at midnight UTC.
The remaining candidates form the fallback order for that day. Other tasks keep
their existing ordered routing unless changed in Administration.

A rate-limited provider falls through immediately when alternatives are present.
Cooldowns persist per Mind, endpoint configuration and selected model, honor
provider Retry-After/reset hints up to 24 hours, and allow another attempt when
the cooldown expires. Authentication failures cool for five minutes; temporary
server or transport failures cool briefly. Changing a key, URL or model starts
a new availability episode. All-provider failure remains an explicit error.
The existing bounded single-provider Steward retry remains supported.

`mind_status` reports provider names, selected models, whether credentials are
configured, routing mode and cooldown status without returning keys or base URLs.
These are configuration/availability diagnostics, not proof of a successful live
interaction.
