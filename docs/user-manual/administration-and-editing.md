# Administration, permissions and editor behavior

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. Sections inherit this revision unless an explicit section review below overrides it. This is source review, not authenticated browser or physical-device certification.

## Enter Administration

1. Sign in to the intended account.
2. Choose **Administration**.
3. If prompted, enter the **Administrator PIN** supplied by the operator.
4. Wait for authorization and settings to load before editing.

The portal calls an Administrator status endpoint. When an Admin PIN is configured, the server checks the supplied PIN. When no PIN is configured, that extra PIN check is absent; the runtime access boundary still matters. This is not a documented invitation/role-management console.

A conversational claim such as “I am the administrator” does not grant API authority. The authenticated Administrator can edit cognitive settings, including protected or required settings. **Protected** does not mean immutable to that Administrator.

## Know which scope you are using

> This section was reviewed against `275e9202313b2ba41fe092e2be0da16186cb5ce2` on 2026-10-25. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

| Boundary | Current behavior |
| --- | --- |
| Portal login | Selects the Mind associated with the verified account/session |
| Cognitive configuration | Identity, skills, behaviors, endpoints and task settings bind to the request's authorized Mind |
| Administrator PIN | Additional check when configured; not a replacement for account/runtime authentication |
| Account-scoped Body access | Live and ordinary Body services bind to the verified Mind; provider configuration or a matching host is still needed |
| Account-scoped Voice Settings | Authorized reads and saves affect that account's own voice preferences |
| Account-scoped Realtime voice | Unavailable; startup checks capability before requesting the microphone |
| Deployment Body fallback setting | Root administration only; account sessions do not call its endpoint |
| Account-scoped GitHub skill drafts | Custom GitHub drafts are explicitly unavailable; Mind skill settings are separate |
| Account-scoped backup | Backup route returns an explicit 403 restriction |
| Deployment/root operations | Separate operator access; do not substitute it to bypass an account restriction |
| Host/tool permissions | Still apply when a skill or conversation requests an action |

An expired, unknown or ambiguous session is rejected rather than silently falling back to the root Mind. A static page loading is not proof that its protected data requests are authorized.

Administration entry and Refresh read current status before loading settings. Authorized account-scoped sessions now load and save their own Voice Settings; they skip the deployment-wide Body fallback endpoint. Speech controls enable only after a permitted settings read succeeds. This replaces the interim PR329 behavior that disabled Voice Settings for all account-scoped sessions.

Section sources: [account runtime and credentials](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L455-L514), [remaining scope guard](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L793-L832), [own voice settings](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L874-L927), [separate capabilities](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L1529-L1535), [portal gating](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/static/portal.js#L1426-L1524).

## Drafts are not saved configuration

> This section was reviewed against `56dd9a5faefcc6adde578ed49a6aaad30e968153` on 2026-10-27. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

Most editors begin read-only and create a draft on **Edit** or **Add**. **Save** commits that editor's payload. **Cancel** discards its draft. **Refresh** reloads data; it does not commit unsaved input.

The implementation is not uniform across every form. Use the following reference rather than assuming a global Save.

| Editor | Start/change | Commit | Cancel/refresh detail |
| --- | --- | --- | --- |
| Foundations: Identity | Open and read | No editing actions | Displays loaded identity; Refresh reads it again |
| Foundations: Startup | Edit | Save Startup | Revisioned draft for Base operating contract and Startup instructions; Cancel restores saved values |
| The Breaker | Edit | Save | Revisioned thresholds and wait limits; Cancel restores saved values |
| Mind skill | Select, Edit; or New Mind skill | Save Mind Skill | Own saved revision |
| GitHub skill draft | Select, Edit; or New GitHub draft | Save Draft to GitHub | Does not activate a Mind skill |
| Behavior catalog | Edit or Add Behavior | Save | Catalog draft; row Remove is staged |
| Task endpoint/behavior selection | Change choices directly | Either task assignment Save | Both assignment Saves call the same handler |
| Task Foundation | Edit | Foundation's own Save | Separate revisioned configuration |
| Endpoint and model | Add/Edit; discovery can enter Edit | Endpoint Save | Requires valid changed draft |
| MCP server and tools | Add/Edit; discovery can enter Edit | MCP Save | Separate from endpoint Save |
| Speech Settings | Change fields/sliders after a permitted settings read | Save | Account-owned preferences; no general Edit/Cancel workflow |
| Devices | Choose device in a browser-local draft | Save | Cancel restores saved choices; see [Devices](body.md#select-devices) |
| Memory inspector | Edit Memory | Save | Cancel exits memory editing |

Section sources: [Foundations and The Breaker forms](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/static/index.html), [current editor gating](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/static/portal.js), [The Breaker settings model](https://github.com/Moto1231/AICognitiveMind/blob/56dd9a5faefcc6adde578ed49a6aaad30e968153/src/aicognitive_mind/continuity_settings.py).

The endpoint Save handler also synchronizes task assignments that reference that endpoint. Changing its model may therefore affect several tasks. Endpoint removal removes those references. See [providers](providers-and-models.md).

## Why Save may be disabled

A disabled control can mean the editor is not in edit mode, nothing changed, a required field is missing, a save/discovery is running, or the initial revision failed to load.

For an endpoint, the UI requires name, provider name, an absolute HTTP(S) Base URL and Model ID. For a behavior, name and instruction must be nonblank and priority must be an integer from 0 through 10000. A task assignment Save becomes actionable after a change; clicking it can then explain an incomplete primary/fallback model.

Check the specific status message. Do not repeatedly change unrelated values to force a save.

## Configure The Breaker

Open **Administration → The Breaker** to read the current circuit status, consecutive and rolling counts, and last failure class. Choose **Edit** to change these parameters:

| Parameter | Packaged default |
| --- | ---: |
| Consecutive failure limit | 5 |
| Rolling failure limit | 35 |
| Rolling window size | 100 |
| Provider request timeout | 30 seconds |
| Steward assessment deadline | 60 seconds |
| Rate-limit retry wait cap | 45 seconds |

Save requires a changed, valid draft and the loaded revision. The rolling limit must be at least the consecutive limit and cannot exceed the rolling window. **Cancel** restores the saved values. A concurrent edit requires refresh before saving.

## Handle a stale revision

1. Read the conflict message and preserve the intended text privately if you still need it.
2. Cancel the stale draft.
3. Refresh and reopen the latest saved record.
4. Compare the newer values with your intended change.
5. Apply only the needed change and Save once.

Identity, cognitive configuration, skills, behavior catalog and endpoint edits have revision/concurrency checks in their relevant save paths. Do not assume every form has the same conflict protection. Avoid parallel editing of task assignments or MCP server lists in multiple tabs.

Active-draft refresh guards exist for several editors, but do not generalize that to all forms. Save or Cancel before changing task, navigating away or reloading the page. Leaving an active task discards its unsaved assignment changes.

## Destructive controls

**Clear Filters** and Live's **Clear conversation** are not memory deletion. **Remove** on a behavior stages a catalog change until Save. **Remove** on a saved endpoint or MCP server performs its removal request immediately; do not assume a second Save or confirmation will follow.

Sensory-media erasure has an explicit confirmation and leaves the journal audit entry. Only erase media intentionally, after considering whether a private backup is needed.

## Sensitive configuration

The API Key field is visually masked and has **Show API key / Hide API key**. This is display protection, not a claim that the value is unretrievable or encrypted. The Administrator endpoint response includes credential-bearing configuration for the editor. Treat browser developer tools, network captures and copied configuration as sensitive.

Never put actual keys, PINs, passwords, personal memories or private account data in GitHub documentation, issues, screenshots or examples.

## Source references

- [src/aicognitive_mind/api.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/api.py)
- [src/aicognitive_mind/deployment.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/deployment.py)
- [src/aicognitive_mind/admin_configuration.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/admin_configuration.py)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/static/index.html](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/index.html)
