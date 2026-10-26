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

The index and this record use the same baseline. Chapter source links are commit-pinned; relative links to repository reference documents follow the branch being viewed.

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

## Gaps and follow-up register

| ID | Status | Gap / next evidence needed |
| --- | --- | --- |
| UM-01 | Open verification | Walk through signup/login and authorized Administration in a real browser using a deliberately authorized test account; record deployment/browser revision without credentials. |
| UM-02 | Implemented limitation documented | Account-scoped Body, Body administration and backup routes return 403. Revise affected chapters only when scoped implementations change. |
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
