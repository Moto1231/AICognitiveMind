# Foundations, Skills and Behaviors

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. Sections inherit this revision unless an explicit section review below overrides it. This is source review, not authenticated browser or physical-device certification.

## Choose the correct configuration layer

| Layer | Use it for | Example |
| --- | --- | --- |
| Identity | Persistent self-name, pronouns, values, commitments, relationships and developmental state | A carefully reviewed commitment |
| Base operating contract | The Mind's general cognitive instructions | How to distinguish evidence from inference |
| Startup instructions | Orientation at interaction startup | Read current state before relying on it |
| Mind skills | Reusable instruction documents and startup flags | Axiom Continuity |
| Task Foundation | Instructions specific to a task | Preserve uncertainty during transcription |
| Behavior catalog | Named, reusable behavior instructions | Keep answers concise |
| Task behavior selection | Explicit membership for a task | Apply concise answers to Reasoning |

Packaged defaults supply unset settings. Saved Administrator overrides take precedence, including explicit blank text where the configuration accepts it. Updating a package does not automatically overwrite saved Mind edits.

## Edit Identity

1. Open **Administration → Foundations**.
2. In **Identity**, choose **Edit**.
3. Review **Self-name**, **Pronouns**, **Developmental state**, **Foundational values**, **Commitments** and **Relationships**.
4. Enter one value or commitment per line.
5. Keep Relationships as a JSON array of records.
6. Choose **Save Identity** and wait for confirmation.

An empty Self-name becomes an unset name. Pronouns and developmental state must be nonblank. Identity changes and their identity-revision journal entry are committed atomically.

For a synthetic relationship-format example:

```json
[
  {
    "name": "Example project team",
    "relationship": "collaborators",
    "grounding": "Explicit project agreement"
  }
]
```

These object fields are illustrative human-readable data, not a promise of special relationship-field behavior. The editor requires an array of objects. Preserve established records and their evidence rather than replacing them with this example.

Choosing or changing my name in conversation follows its own governance protocol. An Administrator identity edit is a distinct, authenticated operation. An unset name does not authorize an automatic rename.

## Naming milestone and current limits

> This section was reviewed against `dbbc246860115153f3c11d05b505014cfcb874b8` on 2026-10-25. Sections without another explicit review block retain the opening baseline.

The status response reports a naming milestone based on the journal experience count. Current-state ledger checkpoints do not advance that count.

| Journal experience count | Reported naming status |
| --- | --- |
| Below 1,000 | Prohibited |
| 1,000–1,999 | Eligible |
| 2,000 or more | Required |

These are reported status labels. Reaching a threshold does **not** automatically choose or save a name. The current Governance Steward accepts a self-name proposal only after an explicit naming command in the current human interaction. Its name-write path does not itself check the experience threshold; the reported milestone and write enforcement are separate.

Automatic name-and-gender selection at the milestone is not implemented in this revision. The identity schema has a **Pronouns** field, defaulting to `she/her`, and no separate gender field. Pronouns are not a gender selection. The self-name action preserves pronouns; an authenticated Administrator can edit them through Identity.

Section sources: [reported milestone and count](https://github.com/Moto1231/AICognitiveMind/blob/dbbc246860115153f3c11d05b505014cfcb874b8/src/aicognitive_mind/mcp_service.py#L128-L147), [self-name authorization and protected fields](https://github.com/Moto1231/AICognitiveMind/blob/dbbc246860115153f3c11d05b505014cfcb874b8/src/aicognitive_mind/governance_steward.py#L88-L143), [identity fields and defaults](https://github.com/Moto1231/AICognitiveMind/blob/dbbc246860115153f3c11d05b505014cfcb874b8/src/aicognitive_mind/domain.py#L55-L60).

## Edit Startup

1. Stay in **Foundations**, then locate **Startup**.
2. Choose its **Edit** control.
3. Review the **Base operating contract** and **Startup instructions** separately.
4. Make the intended change.
5. Choose **Save Startup**.

This Save does not save Identity. A deliberately blank saved contract/startup field remains blank instead of silently restoring a factory value. Blank is therefore a meaningful configuration choice, not a reset button.

After changing startup settings, use a subsequent interaction to verify that the effective configuration is being supplied. A successful Save confirms persistence, not that every connected host has refreshed its cached plugin files.

## Edit an effective Mind skill

1. Open **Administration → Skills**.
2. In **Available skills**, choose the entry marked **· Mind**.
3. Read the source/status text and choose **Edit**.
4. Update Display name, full **SKILL.md** content and flags as needed.
5. Choose **Check** for document validation when useful.
6. Choose **Save Mind Skill** and wait for the saved confirmation.

| Skill control | Meaning |
| --- | --- |
| Enabled | Whether the effective skill is active |
| Load at startup | The UI name for the `required` flag |
| Protected | Saved policy metadata; does not prevent authenticated Administrator edits |
| Enabled + Load at startup | Full content is included in the startup skill contract |
| Skill ID | Stable slug; existing selections keep their ID read-only |
| Display name | Human-readable name, distinct from the slug |

The two packaged default startup skills are **Axiom Continuity** and **Axiom Current State**. Their effective saved flags and content govern whether/how those protocols apply. A disabled skill is not made active merely by leaving Load at startup checked.

The internal **Memory Steward** skill is also configurable. Disabling its added instructions does not remove the software's phase schemas or turn off the independent Steward lifecycle.

## Add a skill or work on a draft

Choose **New Mind skill** to create an effective Mind configuration entry. Use a lowercase ID starting with a letter or digit and containing only lowercase letters, digits and hyphens, up to 64 characters. Supply a display name and deliberate instruction text.

Choose **New GitHub draft** only when authoring a repository draft. Entries marked **· GitHub draft** are different from effective Mind settings, even if their names resemble a Mind skill.

Example draft document:

```markdown
---
name: concise-project-notes
description: Keep project notes short and evidence-based.
---

# Instructions

State the verified result, any unresolved limitation, and the next useful step.
```

**Save Draft to GitHub** writes a draft; it does not activate it for this Mind or publish it to ChatGPT. **Prepare Release** validates the document and downloads a `<slug>-SKILL.md` file for manual installation/update. It is not automatic plugin publication.

Account-scoped sessions are explicitly denied custom GitHub draft access because those repository credentials/resources are deployment-wide. Effective Mind skill editing remains a separate capability. When GitHub draft access is unavailable, read the status message. Do not assume Mind skill editing and GitHub draft availability are the same capability.

## Create a reusable Behavior

> This section was reviewed against `29e11c94af84e07b278c4aae6fd650cd92e6a428` on 2026-10-25. Other sections keep their stated review revisions.

The library shows one selected behavior editor. **Search behaviors** matches the name or instruction; the **Behavior** selector chooses among matching entries. Clear the search to browse the complete library. The count/status line reports the library size, matching entries and whether changes are unsaved.

To create an entry:

1. Open **Administration → Behavior**.
2. Choose **Add Behavior**; this starts a catalog draft if necessary, clears the search and selects the new entry.
3. Replace **New Behavior** and **Describe the behavior.**
4. Set Priority and Enabled; review Required and Protected deliberately.
5. Choose **Save** above the editor and wait for confirmation.
6. Open the desired task in **Task Configuration**, select that behavior and save the task assignment.

To change an existing entry, search or select it, choose **Edit**, then make the change. You can search or select another behavior while editing: changes remain in the same library draft. **Save applies all behavior changes in that draft**, including edits to entries currently hidden by the search. A blank name/instruction or invalid priority anywhere in the draft keeps Save disabled; use the selector or clear the search to find the unfinished entry.

**Cancel restores the saved library and discards all draft edits**, additions and removals. A failed Save keeps the draft available; read the error before retrying. The search, selector and editing controls are locked while Save is pending. Edit, Save and Cancel sit above the selected editor and share the compact action-button sizing used elsewhere in Administration.

Example instruction:

> “For routine progress reports, state the result and one next step. Expand when the user asks for detail.”

Editing the library and selecting membership are separate steps. A selected behavior marked **Disabled in library** is not an active enabled behavior merely because its task checkbox is checked.

An Administrator may edit or remove entries previously marked required/protected. Explicit saved task membership and Administrator removals take precedence over factory membership defaults. See [task configuration](tasks-and-routing.md) for the separate task foundation.

The [supplied earlier-interface behavior capture](screenshots.md#behavior-authoring) illustrates the fields; it predates this single-editor navigation. Follow the workflow above for the reviewed controls and saving behavior.

Section sources: [Behavior form and navigation](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/index.html#L206-L227), [selected editor and catalog Save/Cancel](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/portal.js#L377-L581), [search and selector handlers](https://github.com/Moto1231/AICognitiveMind/blob/29e11c94af84e07b278c4aae6fd650cd92e6a428/src/aicognitive_mind/static/portal.js#L2430-L2443).

## Source references

- [src/aicognitive_mind/admin_configuration.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/admin_configuration.py)
- [src/aicognitive_mind/cognitive_configuration.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/cognitive_configuration.py)
- [src/aicognitive_mind/effective_skills.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/effective_skills.py)
- [src/aicognitive_mind/task_behaviors.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/task_behaviors.py)
- [src/aicognitive_mind/domain.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/domain.py)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
