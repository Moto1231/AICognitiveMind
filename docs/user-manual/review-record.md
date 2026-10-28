# Review record and documentation gaps

[Manual index](README.md)

## Baseline and evidence standard

Initial review date: **2026-10-25**. Live GitHub main was read at **`57f38db876e63d45e37f58f57768e25396a75a8d`**, including PR322 and PR323. The repository tree contained no `AGENTS.md`, contribution instruction file or PR template. The reviewed development convention is [branch → draft PR → Actions → ready/merge after green checks](../DEVELOPMENT_WORKFLOW.md).

All sections in each chapter inherit the revision/date in its opening review block unless a later section explicitly overrides them. The source revision records implementation review, not deployment state. The authoring chat uses a separate Axiom interaction key from the originating product chat.

| Chapter | Reviewed source groups | Review revision |
| --- | --- | --- |
| [Getting started](getting-started.md) | deployment, accounts, API middleware, fresh-start notes, plugin protocol | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Navigation](navigation.md) | index.html, portal.js, button_icons.js | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Interaction](interaction-and-continuity.md) | plugin skills, mcp_service, state_context, host_context | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Administration](administration-and-editing.md) | API authorization/scope, deployment, admin_configuration, portal editors | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Foundations/Skills/Behaviors](foundations-skills-and-behaviors.md) | admin_configuration, cognitive_configuration, effective_skills, task_behaviors, domain, portal editors | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Providers](providers-and-models.md) | provider_endpoints, provider_probe, model_capability_catalog, task_dispatcher, API/UI | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Tasks/routing](tasks-and-routing.md) | task_model_assignments, task_behaviors, task_dispatcher, provider_routing, UI | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [MCP tools](mcp-servers-and-tools.md) | portal tool editor/runner, API call/discovery handlers | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Body](body.md) | live_body.html, voice_settings, body_sessions, API scope/speech/evidence, Body notes | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Recovery](recovery.md) | portal saves, accounts/API, provider cooldowns, backup script and notes | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Operations](operations.md) | render.yaml, Project validation workflow, development/setup/backup notes | `57f38db876e63d45e37f58f57768e25396a75a8d` |
| [Glossary](glossary.md) | lifecycle, effective skills, routing, working-context types | `57f38db876e63d45e37f58f57768e25396a75a8d` |

The index and this record retain that initial baseline; focused later updates are recorded below. Chapter source links are commit-pinned; relative links to repository reference documents follow the branch being viewed.

## What was and was not verified

- **Verified by source review:** labels, editor handlers, request boundaries, configured defaults, routing algorithm, explicit restrictions and backup-script workflow described here.
- **Documentation validation:** local relative targets and pinned repository source paths are checked against the retrieved tree plus new manual files; code-fence balance and synthetic JSON examples are checked before commit.
- **GitHub checks:** use the attached PR's actual results; this file does not predeclare a pass.
- **Not performed for this manual:** live settings changes, account creation/login exercise, provider probe calls, sensory capture, physical-device testing, backup/restore drill or manual Render deploy.
- **Not asserted:** current provider prices/free quotas, provider-account entitlement, universal host plugin compatibility or exact live deployed revision.
- **Supplied screenshots:** four original JPEGs are reproduced unchanged in the [screenshot reference](screenshots.md). They show different interface versions and have unknown capture dates. They are not new authenticated-browser verification of the reviewed revision.

## Supplied screenshot update

Documentation update date: **2026-10-25**. Four user-supplied JPEGs were added as visual examples for Main, Behavior authoring, memory filtering and Audio/Transcription configuration. The [screenshot reference](screenshots.md) records their original filenames, limitations and links to current workflow chapters. Copies preserve the supplied image bytes; their local paths and copy hashes were checked during this update.

The visual-reference page and chapter links do not change the implementation-review baseline above. The Main, Behavior and task images show older navigation and editor layouts; the supplied memory image shows icon navigation, with its deployed revision unknown. Visible counts, memory records, behavior text and provider/model selections are capture content; they do not establish current account state, policy, supported model capabilities or recommended configuration. No new login exercise, provider test or full chapter source review was performed for this image update.

## Naming milestone clarification

Focused source review on **2026-10-25** at **`dbbc246860115153f3c11d05b505014cfcb874b8`** added [Naming milestone and current limits](foundations-skills-and-behaviors.md#naming-milestone-and-current-limits), with a link from Getting started. Only that subsection uses this later baseline. The status response marks naming eligible at 1,000 journal experiences and required at 2,000, excluding current-state ledger checkpoints. This is distinct from the explicit-command self-name write path, which does not enforce that count. Automatic name-and-gender selection is not implemented; the current schema has pronouns and no separate gender field. The subsection links its exact implementation sources. No live identity or configuration was changed, and no milestone transition was exercised in a live account.

## Devices and Behavior workflow refresh

Focused source review on **2026-10-25** at **`29e11c94af84e07b278c4aae6fd650cd92e6a428`** updated only [Select devices](body.md#select-devices) and [Create a reusable Behavior](foundations-skills-and-behaviors.md#create-a-reusable-behavior). Their section review blocks and implementation links identify the newer revision; the other chapter sections and initial review table retain their stated baselines.

Devices now uses a browser-local draft with explicit Save/Cancel, a separate saved-preference summary, navigation rollback, refresh/stale-response protection and storage/conflict status. The Behavior library now searches and selects one editor while retaining the complete revisioned catalog draft across selections. Its top Edit/Save/Cancel controls save or discard the whole draft, and validation includes hidden entries. The Task Foundation button-size correction changes presentation without changing its documented editing workflow.

This maintenance pass reviewed the changed source and documentation links. It does not establish a new authenticated-browser, provider or physical-device test, nor does it close UM-01, UM-02, UM-03 or UM-09. Product PRs [327](https://github.com/Moto1231/AICognitiveMind/pull/327) and [328](https://github.com/Moto1231/AICognitiveMind/pull/328) record their separate implementation validation and delivery evidence. Existing screenshot provenance and limitations remain in force.

## Foundations display and scope-safe Admin refresh

Focused source review on **2026-10-25** at **`80a3a4105379bb6c95afb6c71483c8d556a0ccc3`** covers merged [PR329](https://github.com/Moto1231/AICognitiveMind/pull/329). Updated sections are [Read loaded Identity](foundations-skills-and-behaviors.md#read-loaded-identity), [Startup configuration](foundations-skills-and-behaviors.md#edit-startup-configuration), [Behavior authoring](foundations-skills-and-behaviors.md#create-a-reusable-behavior), [scope and editor reference](administration-and-editing.md), [navigation and System Overview](navigation.md), [Devices](body.md#select-devices), and [Speech Settings](body.md#configure-speech-settings). Their explicit section blocks override the opening chapter baseline only for those sections.

Foundations now displays the loaded identity as text, retains **Identity loaded.**, and has no identity or Startup editing actions. Its refresh only reads identity. Authorized identity and cognitive-configuration API endpoints remain implemented. Behavior and Devices forms omit the redundant action/helper sentences; draft/error status remains.

That Startup statement records PR329's interim behavior and is superseded by the current refresh below.

Administration entry and Refresh read status before requesting Body settings. The new capability makes account-scoped sessions skip deployment-wide Voice and Body fallback settings. Their voice form is unavailable, clears old values, ignores an earlier voice response and blocks Save; other supported Administration data continues refreshing. At this interim revision, the change did **not** implement account-scoped Body access. The later [account Body review](#account-scoped-body-and-voice-settings) supersedes its account Voice Settings restriction in the current workflow sections.

[PR329](https://github.com/Moto1231/AICognitiveMind/pull/329) records its product-test evidence: 81 Node editor/device tests, 13 Python portal tests, 2 sensory-administration tests and 12 HTTP account-routing tests, plus JavaScript syntax and diff checks. This documentation pass reviewed the pinned implementation and corresponding regression sources; it did not rerun product tests or establish a signed-in-browser or physical-device result. Sources: [Foundations/voice UI regressions](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/tests/portal_editors.test.cjs#L1359-L1708), [account capability and scope regression](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/tests/test_http_account_routing.py#L152-L192). UM-01, UM-02, UM-03 and UM-09 remain open or restricted as recorded below.

## Account-scoped Body and Voice Settings

Focused source review on **2026-10-25** at **`275e9202313b2ba41fe092e2be0da16186cb5ce2`**, the merge source for [PR330](https://github.com/Moto1231/AICognitiveMind/pull/330), updates [Body access](body.md#check-access-before-hardware), [Speech Settings](body.md#configure-speech-settings), the [Administration scope/editor reference](administration-and-editing.md) [navigation map](navigation.md#current-menu-map), [Before opening Live](getting-started.md#before-opening-live) and the [recovery symptom table](recovery.md#start-with-the-smallest-failing-boundary). Foundations and the other chapter sections retain their own earlier pins.

Account Live and ordinary Body routes now use the verified Mind's runtime, queues, evidence, host/camera requests, presence scope and voice settings. Session output notifications are separated by Mind. Account reasoning and interpretation use account task endpoints or a host attached to that Mind; deployment OpenAI/Gemini/Fish credentials are removed from the account fallback configuration.

This supersedes the interim PR329 Voice Settings restriction: authorized account sessions now load and save their own preferences. The deployment Body fallback switch remains root-only and is skipped during account Refresh. An account's own saved Fish key can serve its speech path; missing account task/credential configuration remains an error.

Realtime voice remains unavailable for account-scoped sessions. Capability preflight prevents microphone capture/session creation when unavailable; the session route independently refuses the account before deployment credentials or token minting. This is not documentation of completed account Realtime support.

Reviewed regression sources cover [Body/account isolation and credential boundaries](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/tests/test_http_account_routing.py#L354-L558), [Realtime preflight](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/tests/live_body_realtime.test.cjs#L52-L89) and [Realtime route isolation](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/tests/test_deployment_mcp.py#L107-L148). [PR330](https://github.com/Moto1231/AICognitiveMind/pull/330) records its product test/CI and merge evidence. This documentation pass reviews the merged source; it does not establish deployment, signed-in-browser, hardware, real provider or host-handoff verification. UM-01, UM-03 and UM-09 remain open; UM-02 now records the narrower remaining restriction.

## Continuity, Administration and Body recovery refresh

Focused source review on **2026-10-27** at **`56dd9a5faefcc6adde578ed49a6aaad30e968153`** updates the current interaction lifecycle, Administration editor map, Foundations/Startup workflow, navigation, validation wording and browser Body recovery. The first-person current-state rules are merged in [PR345](https://github.com/Moto1231/AICognitiveMind/pull/345); the still-relevant browser-suspension recovery from old draft PR294 was adapted to current source and merged in [PR349](https://github.com/Moto1231/AICognitiveMind/pull/349).

Presentation no longer waits for memory persistence. **The Breaker** suppresses isolated persistence failures and opens at either configured threshold; only a later failed recovery is reported in ordinary interaction. Administration exposes revisioned consecutive/rolling thresholds, the rolling window and three wait limits. Packaged defaults are 5 consecutive, 35 of 100 rolling, 30-second provider timeout, 60-second Steward deadline and 45-second rate-limit wait cap.

Foundations keeps identity read-only and restores a separate revisioned Startup editor. Current navigation uses inline transparent SVG icons and consistent button/input sizing, with labels available through titles and accessible names. The primary validation job is Surreal-backed; the Mongo retrieval job is secondary legacy-compatibility coverage. Live Body now re-registers, reopens Mouth events and drains queued speech after foreground/page restoration without enabling Voice Off or duplicating simultaneous recovery.

This was source and automated-test review. It does not establish a new authenticated-browser, physical-device, provider-quota or restore-drill result. Existing screenshot limitations and open verification gaps remain.

## Gaps and follow-up register

| ID | Status | Gap / next evidence needed |
| --- | --- | --- |
| UM-01 | Open verification | Walk through signup/login and authorized Administration in a real browser using a deliberately authorized test account; record deployment/browser revision without credentials. |
| UM-02 | Partially resolved; remaining restrictions documented | Reviewed account Body code binds Live and ordinary Body services/voice preferences to the verified Mind. Account Realtime, deployment fallback administration and backup remain restricted. This source update does not close live account/Body verification gaps. |
| UM-03 | Open verification | Physical camera/microphone/speaker workflow on supported devices; distinguish local preview/meter from actual interpreted/synthesized results. |
| UM-04 | Open verification | Current checkpoint recovery/restore drill for the actual Surreal backend. Existing Mongo restore instructions are not a substitute. |
| UM-05 | Open reconciliation | Historical root README sections still describe a four-tool MCP server and older one-instance/storage assumptions. The new manual link establishes the current workflow entry point; broader historical prose needs a separate careful reconciliation. |
| UM-06 | Open reconciliation | Older plugin-install notes describe one skill and host-specific installation steps. This manual documents the companion protocols but does not certify current third-party host UI. |
| UM-07 | Implemented distinction documented | Task Profiles menu versus Task Configuration heading; update exact navigation if either changes. |
| UM-08 | Implemented limitation documented | GitHub skill drafts are unavailable to account-scoped sessions; effective Mind skills remain separate. |
| UM-09 | Open verification | End-to-end Body/host handoff and speech paths under actual permissions/provider quotas. Realtime code and status indicators alone do not prove success. |
| UM-10 | Planned, not delivered here | Portable backup encryption is identified as a later increment in BACKUPS.md. Do not claim checkpoint encryption. |
| UM-11 | Open reconciliation | Older Body storage/transience notes contain historical implementation claims. Prefer current handlers and preserve evidence versus interpretation distinctions. |
| UM-12 | Open verification | Third-party provider documentation URLs and current capability/price changes are not freshly internet-verified by this source-authoring pass; repository labels are documented as repository claims. |
| UM-13 | Open visual refresh | Replace or supplement the clearly labeled earlier-interface captures with authorized captures of the reviewed/current interface, recording the deployment revision and capture date. The supplied screenshots do not close UM-01 or provider/device verification gaps. |
| UM-14 | Open implementation reconciliation | The reported 1,000/2,000 naming milestones are status metadata; the name-write path requires an explicit current naming command and has no count gate. Automatic milestone name/gender selection and a gender field are not implemented in the reviewed revision. Reconcile intended behavior before presenting it as an available feature. |

These are documentation/verification gaps, not authorization to change live settings or application behavior.

## Maintenance handoff

Use the [maintenance procedure](operations.md). Compare current main to the recorded source baseline before editing. Update only affected chapter pins after review, and retain explicit unverified claims. Keep product work in its separate chat. The user supplies this chat's daily schedule; do not create a duplicate.

A no-change run should remain quiet unless it completes open writing/verification work or encounters a meaningful failure. Report an actual PR/commit or a precise blocker, not a promise that publication happened.
