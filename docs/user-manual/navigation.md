# Navigation and reading your information

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. Sections inherit this revision unless an explicit section review below overrides it. This is source review, not authenticated browser or physical-device certification.

## Current menu map

> This section was reviewed against `275e9202313b2ba41fe092e2be0da16186cb5ce2` on 2026-10-25. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

Use this table when a heading differs from its navigation button. Button icons may replace visible text; hover or keyboard focus exposes labels/tooltips, and accessible labels identify the action.

| Location | Navigation label | Page or purpose |
| --- | --- | --- |
| Top bar | Main | Mind name, continuity, durable-memory count and history count |
| Top bar | Administration | Authorized settings and inspection views |
| Top bar | Live | Browser Body at `/body/live`, scoped to the signed-in Mind |
| Top bar | Return | Browser back when history exists; otherwise the public entry link |
| Top bar | Log Out | End the portal session |
| Administration | System Overview | Mind Details, Cognitive State, Current State Context, API Activity |
| Administration | Foundations | Loaded identity as text; no identity or Startup editor |
| Administration | Behavior | **Behaviors** shared catalog |
| Administration | Devices | **Device Inventory** |
| Administration | Speech Settings | Speech sliders and browser voice name for the authorized Mind |
| Administration | Task Profiles | **Task Configuration**, then an individual task |
| Administration | Endpoints, Servers & Tools | **Endpoints → Models** and **MCP Servers → Tools** |
| Administration | Skills | Mind skills, GitHub drafts and release-file preparation |
| Administration | Memories | **Durable Memory** |
| Administration | Journals | **History** |
| Administration | Refresh | Reload supported views/configuration; not Save |

**Task Profiles** remains the navigation label in the HTML. **Task Configuration** is the page heading. Its task buttons are inside the internal **Task selection** panel, as changed in PR323. Do not look for separate task buttons on the outer Administration menu.

Section **Back** controls return to System Overview. Inside an individual task, the task-list return control takes you back to Task Configuration. Save drafts before changing sections; draft protection differs by editor.

The Main HTML also contains hidden identity and memory panels. Their existence in source does not make them visible Main workflows. Use the Administration **Memories** and **Journals** sections for the documented inspectors.

For a visual example, see the [supplied earlier-interface Main overview capture](screenshots.md#main-overview). Its counts are historical; use the menu map above for current navigation.

Account-scoped Live access uses its own Mind's services. Realtime voice remains unavailable for those accounts; see [Body access and limits](body.md#check-access-before-hardware).

Section sources: [Administration views](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/static/index.html#L168-L220), [Speech Settings](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/static/index.html#L527-L551), [account runtime binding](https://github.com/Moto1231/AICognitiveMind/blob/275e9202313b2ba41fe092e2be0da16186cb5ce2/src/aicognitive_mind/api.py#L455-L514).

## Read System Overview

> This section was reviewed against `80a3a4105379bb6c95afb6c71483c8d556a0ccc3` on 2026-10-25. Other sections retain their stated review revisions. This is source review, not authenticated-browser or physical-device certification.

1. Open **Administration → System Overview**.
2. Review **Mind Details**: Mind, creation time, Durable Memories and Journal Experiences.
3. Read **Cognitive State**, which asks who I am, my mood, where I am, who is present, who is speaking and the current context.
4. Inspect **Current State Context** when you need the stored field value, source, status or timestamp.
5. Choose **Refresh** if the displayed information needs reloading.

“Self-name not set” does not mean that identity or history is absent. **Unknown** is an honest missing answer, not a request to invent one. The state view is read-only; use conversation to supply context. **Foundations** separately displays the loaded identity and has no editing controls.

Section sources for this distinction: [Foundations identity display](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/src/aicognitive_mind/static/index.html#L168-L183), [safe identity rendering and refresh](https://github.com/Moto1231/AICognitiveMind/blob/80a3a4105379bb6c95afb6c71483c8d556a0ccc3/src/aicognitive_mind/static/portal.js#L3357-L3403).

**API Activity** contains the latest 200 completed HTTP requests in the process. Use **Filter calls → Errors** to narrow it. Expand an entry for route/operation, status, duration and trace information. It does **not** measure pending/running queue counts; a low average HTTP duration is not a complete conversation-latency measurement.

## Find and inspect a memory

1. Open **Administration → Memories**.
2. Enter search text, or filter by **Memory Class**, **Association**, **Grounding**, **Formed From** and **Formed Through**.
3. Choose **Newest First** or **Oldest First**.
4. Choose 10, 25, 50 or 100 results per page; use **Get More** when available.
5. Open a result to inspect its exact content, class, formation time, grounding, associations and Steward artifacts.
6. Close the inspector when finished.

**Clear Filters** clears the search/filter form; it does not erase memories. Filtered result counts and the total stored-memory count answer different questions.

The [supplied memory-filter capture](screenshots.md#memory-filtering) shows these filter groups and example result cards with icon navigation. Its deployed revision is unknown; the visible records and totals are capture content, not current state.

An authorized Administrator can choose **Edit Memory**, change content/class/associations/grounding, and **Save**. Associations and grounding use one entry per line. **Cancel** leaves the persisted record unchanged. Do not remove evidence or uncertainty merely to make a memory read more confidently.

## Inspect history and evidence

1. Open **Administration → Journals**; the page heading is **History**.
2. Search input, response, revision or identity text.
3. Optionally filter by **Kind**, occurrence dates and sort order.
4. Open an experience to read its structured detail and exact record.
5. If it references preserved sensory artifacts, inspect the **Sensory Evidence** area in that journal detail.

History is read-only. An evidence-erasure action removes media bytes only after confirmation; it does not erase the journal audit entry. Missing or erased media must not be described as newly viewed evidence.

Displayed portal date/times are formatted in the browser's local timezone. Provider daily rotation uses UTC independently.

## Example: investigate an unexpectedly low count

Clear filters and confirm the Mind/account first. Compare the count type: curated memories are not the same as journal experiences, and internal current-state checkpoints are excluded from the normal journal count. Record the account/scope privately and the observed count/time before assuming records were deleted. Continue with [recovery](recovery.md).

## Source references

- [src/aicognitive_mind/static/index.html](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/index.html)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/static/button_icons.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/button_icons.js)
