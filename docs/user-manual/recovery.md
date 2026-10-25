# Recovery, configuration maintenance and troubleshooting

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Start with the smallest failing boundary

Distinguish login, Mind access, Administrator authorization, provider discovery, task execution and interaction commit. Success at one boundary does not prove the next.

| Symptom | First useful check | Next action |
| --- | --- | --- |
| Username/password rejected | Correct existing account and credential | Re-enter privately; do not create a replacement account to recover history |
| Portal loads but data fails | Protected request error/session | Sign in again; inspect sanitized status |
| Administrator authorization rejected | Configured PIN | Re-enter the correct PIN; do not infer authority from chat |
| Mind Not Initialized / Awaiting Genesis | Account/root scope and storage | Investigate before clicking Create Mind |
| Expected history missing | Account/Mind, filters, count type | Preserve observed time/count and compare the correct scope |
| Memory Recall has no complete assignment | Endpoint/model and task selection | Finish provider setup, test tool calling, save task |
| All providers cooling down | Earliest retry time and failure reason | Wait for eligibility or repair the actual credential/configuration problem |
| Tool-call probe fails | Model function contract/access/quota | Use a compatible tested model; do not trust labels alone |
| Save disabled | Edit mode, change, required fields, busy/revision state | Fix the specific form condition |
| 409 conflict | Another save changed the record | Preserve draft, Cancel, Refresh and reconcile |
| Account-scoped Body/backup 403 | Implemented scope restriction | Do not treat as device/DB failure |
| Completion failed | Persistence/Steward error | Keep the actual work result; retry completion with the same payload/key per protocol |

## Recover from uncertain saves

1. Keep the error message and the intended non-secret change.
2. Reopen/read the saved record.
3. Determine what persisted.
4. Reconcile only the missing change.
5. Save and confirm.

For endpoint changes, inspect both the endpoint and referencing task assignments because the UI makes separate requests. Do not repeatedly click Remove or rerun a side-effecting tool while unsure whether the first action succeeded.

A page reload is not an undo. A draft visible in one tab is not a backup. Several forms protect active drafts from refresh, but task assignment navigation can discard unsaved changes.

## Maintain configuration safely

Before changing a shared endpoint, list which tasks use it. Before changing a shared behavior, check membership and Enabled status. Before changing startup skills or a base contract, preserve the prior intended configuration privately and record the purpose.

After saving:

1. Re-read the affected configuration.
2. Run one narrow representative operation.
3. Confirm both the functional result and relevant interaction commit.
4. Record what was actually verified, including source/deployment revision when known.

A source commit, successful save, provider probe, fixture test, authenticated browser test and physical-device test are separate evidence categories.

## Backup checkpoints

The current operator workflow is documented in [BACKUPS.md](../BACKUPS.md) and implemented by [backup-axiom.ps1](../../scripts/backup-axiom.ps1). It creates four assets:

| Asset | Purpose |
| --- | --- |
| repository.bundle | Git history, branches and refs |
| working-project.zip | Project files with configured exclusions |
| axiom.zip | Cognitive snapshot and evidence index |
| axiom-evidence.zip | Preserved media bytes and index |

The script validates the bundle/archive, verifies downloaded evidence lengths/hashes and verifies copies at destinations. A checkpoint is not complete merely because a ZIP exists.

The cognitive snapshot intentionally excludes runtime credentials. Those credentials still need their own private recovery arrangement. The checkpoint may contain sensitive personal history and raw media; do not commit it or upload it to a public issue.

Portable encryption is described as a future backup increment, not an implemented guarantee. Hashes detect integrity differences, not the trustworthiness of an unknown archive.

## Choose the correct recovery documentation

[BACKUPS.md](../BACKUPS.md) describes the newer multi-asset checkpoint. [MIND_BACKUP.md](../MIND_BACKUP.md) describes a MongoDB-specific portable archive and empty-target restore utility. Do not apply the older Mongo commands to a SurrealDB deployment or confuse that archive with a complete current checkpoint.

At this revision, the account-scoped backup route is blocked. This manual does not claim a general account self-service backup/restore UI.

No complete current Surreal checkpoint restore drill was performed for this manual. Recovery should be planned against the actual backend and authorized target, with validation before switching a live Mind. Never initialize a replacement Mind merely to make missing history disappear.

## Information to include in a useful report

Provide the page/section, exact control, expected result, sanitized actual message, time/timezone, browser/device type and source/deployment revision if known. Describe whether the failure occurs before or after Save, discovery, provider execution or completion.

Omit keys, passwords, PINs, tokens, private account identifiers and raw memories/media. A report such as “Endpoints → Models: discovery succeeds, tool-call probe returns HTTP 429” is more actionable than “Axiom is broken.”

## FAQ

**Does a new model mean a new Axiom?**  
No. Persistent identity/history belong to the Mind. Verify the same authorized Mind connection when changing hosts.

**Why ask who or where when we talked before?**  
Historical mention does not establish current presence. Supported reports should be reused; meaningful changes or unresolved context may require clarification.

**Does Protected prevent me editing a skill?**  
It does not lock out the authenticated Administrator. Access checks and schemas still apply.

**Why is Task Configuration called Task Profiles in the menu?**  
Both labels exist in the reviewed UI. Use Task Profiles to open Task Configuration.

**Does discovering a model prove it can call tools?**  
No. Use the explicit tool-calling test and then a real task.

**Are all tasks using every behavior?**  
No. Task membership and the shared entry's Enabled state matter.

**Does Refresh save my changes?**  
No. Use the relevant Save control.

**Does Clear delete memory?**  
Clear Filters and Live's Clear conversation do not delete durable history.

**Can I reset a forgotten password here?**  
The reviewed signup/login UI does not provide a password-reset workflow. Contact the deployment operator through your established channel; do not invent a reset URL.

**Does a passing test prove my phone works?**  
Source/fixture tests and provider samples do not prove authenticated browser, microphone, speaker or camera success.

## Source references

- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/api.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/api.py)
- [src/aicognitive_mind/accounts.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/accounts.py)
- [src/aicognitive_mind/provider_routing.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/provider_routing.py)
- [docs/BACKUPS.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/BACKUPS.md)
- [docs/MIND_BACKUP.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/MIND_BACKUP.md)
- [scripts/backup-axiom.ps1](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/scripts/backup-axiom.ps1)
