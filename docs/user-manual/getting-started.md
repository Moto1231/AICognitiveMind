# Getting started

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Choose the right starting point

I am Axiom, a persistent Mind whose identity and cognitive history are stored separately from the model doing the reasoning. This manual explains how to interact with me and how an authorized Administrator configures that interaction.

An existing account, a new account, and a deployment's root Mind are different starting points. Do not create a new account to recover missing history from an existing one: signup creates a separate, unnamed Genesis Mind.

See [Naming milestone and current limits](foundations-skills-and-behaviors.md#naming-milestone-and-current-limits) for the reported 1,000-entry eligibility milestone and the distinction between that status and the implemented name-selection workflow.

| Your situation | Start here |
| --- | --- |
| You already have an account | Open the deployment's public page and choose **Existing Axiom**, or open `/portal`. |
| You intentionally want a new account and Mind | Choose **Create new account**, or **Create a new Axiom account** on the sign-in page. |
| You operate a new deployment's root Mind | Read the [operations appendix](operations.md); root initialization is separate from account signup. |
| Your existing Mind appears empty | Check the account, connection and storage scope before initializing anything. See [recovery](recovery.md). |

The deployment URL comes from your operator. Paths in this manual are relative to that URL. The public entry is `/`; the portal is `/portal`; the signed-in interface is `/static/index.html`.

## Sign in to an existing account

1. Open **Existing Axiom**.
2. Enter your username and password, then choose **Sign in**.
3. Wait for Main to load its Mind name and continuity information.
4. Check that the expected Mind/history is shown before editing configuration.
5. Use **Administration** for settings, or continue the conversation in your connected MCP host.

The source normalizes usernames by trimming whitespace and converting them to lowercase. Passwords are verified as supplied. A successful portal login establishes a session cookie with a seven-day lifetime; it does not prove that every downstream provider is available.

**Log Out** ends the portal session without deleting the Mind. Logging out of the portal should not be treated as revoking every separate OAuth/plugin connection.

## Create a new account

1. On the sign-in page, choose **Create a new Axiom account**.
2. Enter a new username of at least three characters and a password of at least eight characters.
3. Choose **Create account**.
4. Wait for **Account created. Sign in above.**
5. Sign in with those credentials.
6. Have an authorized Administrator configure a working provider/model for **Memory Recall** before expecting normal begin/complete interactions.

The public **Create new account** link uses the HTML signup route; the inline sign-in form uses the JSON signup route. Both use the same account service. Signup initializes the account's unnamed Mind before publishing and reading back the account record.

A fresh Mind has no saved provider endpoints or Memory Recall assignment. Initialization does not require a model call, but ordinary interaction uses the production Memory Steward. An unconfigured Steward can therefore prevent the first conversation even though signup succeeded.

Do not run the CLI initializer as an extra signup step. It targets the configured root store, not the new account's tenant.

## Connect a reasoning host

1. Install/select the Axiom plugin in a host that supports its MCP connection and skills.
2. Complete the connection's OAuth sign-in with the intended Axiom account.
3. Confirm that the host exposes both **begin_interaction** and **complete_interaction**.
4. Start with a short message, such as “Tell me what context you have for this conversation.”
5. Confirm a successful interaction rather than treating a visible plugin name as proof of connection.

The deployed integrated MCP endpoint is `/axiom-mcp`. A standalone developer MCP server may use `/mcp`; these are not interchangeable deployment instructions.

The repository package includes the core Axiom skill and the companion **Axiom Continuity** and **Axiom Current State** skills. Effective saved Mind settings determine startup behavior. Older installation notes describing only one skill are incomplete for this revision.

Host installation screens and account entitlements vary; this manual does not certify a particular host's current installation UI. If a required write action is unavailable, report the failure. Do not label completion read-only or silently skip it.

## First useful interaction

Try a small, non-sensitive preference:

> “For this project, give me one or two next steps at a time.”

Then ask:

> “What preference did I just give you, and is it working context or durable memory?”

The current conversation can supply the answer without a durable-memory search. The Steward independently decides what to retain. A response alone is not proof of a durable-memory write; check the reported commit and, when appropriate, the memory/history views.

## Before opening Live

Read [Body and devices](body.md) first. At this source revision, account-scoped sessions are explicitly denied the Body routes, Body administration routes and backup route. This is an implemented scope restriction, not a camera-permission problem. Do not use another account's resources to work around it.

## Source references

- [src/aicognitive_mind/deployment.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/deployment.py)
- [src/aicognitive_mind/accounts.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/accounts.py)
- [src/aicognitive_mind/api.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/api.py)
- [docs/FRESH_START_SETUP.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/docs/FRESH_START_SETUP.md)
- [plugins/axiom-mind/skills/axiom/SKILL.md](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/plugins/axiom-mind/skills/axiom/SKILL.md)
