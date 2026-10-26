# Axiom User Manual

I am Axiom. This manual explains how to work with me, inspect continuity and evidence, and configure the system as an authorized Administrator.

**Source review baseline:** [`57f38db876e63d45e37f58f57768e25396a75a8d`](https://github.com/Moto1231/AICognitiveMind/commit/57f38db876e63d45e37f58f57768e25396a75a8d), reviewed 2026-10-25. This includes PR322 and PR323. Each chapter records its own review revision and links its implementation sources. Focused later updates cover [PR329's Foundations display](review-record.md#foundations-display-and-scope-safe-admin-refresh) and [account-scoped Body access](review-record.md#account-scoped-body-and-voice-settings).

This is a substantial first edition based on repository source, not a certification of a live deployment, authenticated browser session or physical device. [Known gaps and verification limits](review-record.md) are explicit. Text examples are synthetic. The [screenshot reference](screenshots.md) separately identifies user-supplied captures from different interface versions and their example settings; credentials must not be included in documentation.

## Start with your goal

| I want to… | Read |
| --- | --- |
| Sign in, create a new Mind, or connect a host | [Getting started](getting-started.md) |
| Find the exact menu or inspect memories/history | [Navigation](navigation.md) |
| See supplied examples of the overview, behaviors, memory filters and task configuration | [Screenshot reference](screenshots.md) |
| Understand identity, continuity and uncertain context | [Everyday interaction](interaction-and-continuity.md) |
| Edit safely and understand Administrator authority | [Administration and editing](administration-and-editing.md) |
| Read loaded identity or configure skills and behaviors | [Foundations, Skills and Behaviors](foundations-skills-and-behaviors.md) |
| Add a provider, discover models or interpret capability labels | [Endpoints and Models](providers-and-models.md) |
| Assign tasks, order fallbacks or rotate providers daily | [Task Configuration and routing](tasks-and-routing.md) |
| Connect an external tool server | [MCP Servers and Tools](mcp-servers-and-tools.md) |
| Use camera, microphone, speech or preserved evidence | [Body and devices](body.md) |
| Diagnose a failure or plan recovery | [Recovery and FAQ](recovery.md) |
| Operate backups or maintain this documentation | [Operations appendix](operations.md) |
| Look up a term | [Glossary](glossary.md) |

## Read the current labels literally

The Administration menu says **Task Profiles**; its page heading is **Task Configuration**. Its task buttons are inside the **Task selection** panel. **Behavior** opens **Behaviors**, **Memories** opens **Durable Memory**, and **Journals** opens **History**.

**Endpoints → Models** and **MCP Servers → Tools** are separate sections under **Endpoints, Servers & Tools**. A model list, a capability label, a passing tool-call probe and a successful real task establish different things.

## Important access limits

New account signup creates a separate account-scoped Mind. The [reviewed account Body update](body.md#check-access-before-hardware) binds Live and ordinary Body services to that Mind. Realtime voice remains unavailable to account-scoped sessions; deployment fallback administration, backup and custom GitHub skill drafts retain separate restrictions. Body reasoning and provider operations require suitable task configuration or a host attached to the same Mind. Read the relevant chapter before assuming a visible control is ready to use.

Saved Mind skills and GitHub skill drafts are different. A draft Save does not activate a skill or publish a plugin. Protected settings remain editable by the authenticated Administrator.

## Manual status

The first edition covers the ordinary-user and Administrator workflows requested for this project. The [review record](review-record.md) maps chapters to sources and tracks remaining verification and historical-document reconciliation work. No daily schedule or deployment is created by this manual.
