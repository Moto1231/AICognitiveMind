# Endpoints and Models

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Endpoints are model connections

Open **Administration → Endpoints, Servers & Tools → Endpoints**. An endpoint stores a provider connection and selected model. Its **Models** subsection belongs to that endpoint.

**MCP Servers → Tools** on the same page configures external callable tools. A model endpoint is not an MCP server; discovering models is not discovering tools.

## Add a provider connection

1. Choose **Add**.
2. In **Start from**, keep **Blank endpoint** or copy an existing endpoint as a starting point.
3. Enter **Endpoint Name** and **Provider Name**.
4. Enter the provider's API **Base URL**, not its account/dashboard webpage.
5. Enter the provider's key in **API Key** when required.
6. Choose **Discover Models**.
7. Select a **Discovered Model**, or enter the provider's exact **Model ID**.
8. If this connection will serve the Memory Steward, choose **Test tool calling**.
9. Choose the endpoint **Save**, then check the saved model and status.
10. Assign the saved endpoint to a task separately.

The Add workflow can copy existing configuration; inspect the URL, model and credential before saving under a new name. It is not a provider-account creation flow.

The key starts visually hidden. **Show API key** reveals the field; hide it again before screen sharing. This UI uses a masked text input, not a guarantee that browser extensions, developer tools or authenticated configuration responses cannot read it.

## Prepare the five built-in connections

**Prepare five provider connections** stages profiles for these repository presets:

| Provider | Base URL in this revision |
| --- | --- |
| Cerebras | `https://api.cerebras.ai/v1` |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| OpenRouter | `https://openrouter.ai/api/v1` |
| SambaNova | `https://api.sambanova.ai/v1` |
| Together AI | `https://api.together.ai/v1` |

1. Choose **Prepare five provider connections**.
2. Review the **New connection profiles** list.
3. Choose that panel's **Save**, or **Cancel** to discard the batch.
4. Select each saved profile, Edit it, add its own credential, discover/select a model and test the required operation.
5. Save the completed endpoint before assigning it.

Existing same-base-URL connections are skipped, and the batch preserves existing connections and task assignments. The prepared profiles intentionally have no invented key or selected model. Their batch Save is distinct from completing a normal endpoint editor, whose Save requires a model.

These are source-defined presets, not a claim about current pricing, free allowance, regional access or your account's quota. Check provider documentation and account access before relying on a service.

## Discovery, labels and tests mean different things

| Result | What it establishes | What remains unverified |
| --- | --- | --- |
| Discover Models | The listing operation returned model IDs | Inference access, quota and task compatibility |
| Provider metadata | The listing reports capability information | Actual successful requests in this integration |
| Documented capabilities (not tested) | A finite repository catalog supplies labels for an exact official endpoint/model | Your key's access and actual functional behavior |
| Provider metadata + documented capabilities | Both sources contribute labels | Still not a live inference test |
| Tool calling verified in current test | Synthetic recall and review function responses passed for the tested configuration | Vision, transcription, speech, future quota/uptime |
| Real task success | That specific operation succeeded at that time | Universal capability or future reliability |

Explicit provider restrictions take precedence over catalog supplements. Similar names and compatible proxy URLs do not automatically inherit another provider's documented capabilities. Missing labels mean compatibility is unverified, not necessarily unsupported.

**Test tool calling** sends at most two small synthetic requests, one for recall and one for review. It uses a 20-second timeout per request and no retries, and performs no configuration or memory writes. It is still a real provider request that can consume quota. The check requires a key and model.

The displayed probe result is held in the page's current test state; changing the draft clears it. It is not a permanent certification badge. A passing sample does not prove an authenticated browser workflow or a physical device worked.

## Edit or replace a model

1. Select the existing endpoint and choose **Edit**.
2. Discover again if needed; discovery on a saved endpoint can enter edit mode automatically.
3. Select the intended exact Model ID.
4. Test the relevant capability.
5. Save and inspect tasks that reference the endpoint.

Endpoint Save also updates matching task assignment/model references. If only one task should use a different model, create a separate endpoint profile rather than changing a shared one casually.

The endpoint save and assignment synchronization are separate requests. If an error appears after saving, re-read both the endpoint and its referencing tasks; do not assume the entire operation rolled back.

## Common setup problems

- **No models:** verify Base URL, provider key, listing support and access. A provider may allow inference without a useful listing; the Model ID field allows an exact documented ID.
- **Save disabled:** confirm Edit mode, changed values, provider/name, valid HTTP(S) URL and model.
- **401/403 from provider:** check that provider's key and model entitlement; portal login is a separate credential.
- **429:** quota/rate limit; use configured fallbacks and cooldown diagnostics.
- **Tools label but probe fails:** labels are not tests. Try a model that actually returns the required function response.
- **Localhost preset fails on a hosted runtime:** provider calls originate from the application runtime. Its localhost is not your laptop.

Do not expose keys in troubleshooting output. Record provider name, model, operation, HTTP status and sanitized message instead.

## Source references

- [src/aicognitive_mind/static/index.html](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/index.html)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/provider_endpoints.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/provider_endpoints.py)
- [src/aicognitive_mind/provider_probe.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/provider_probe.py)
- [src/aicognitive_mind/model_capability_catalog.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/model_capability_catalog.py)
- [src/aicognitive_mind/task_dispatcher.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/task_dispatcher.py)
- [src/aicognitive_mind/api.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/api.py)
