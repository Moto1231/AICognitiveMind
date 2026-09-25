# 0010 — ChatGPT as an Axiom reasoning host

## Decision

Axiom exposes a dedicated remote MCP surface for ChatGPT while remaining the owner of identity,
memory, continuity, journal, governance, and sensory evidence.

ChatGPT is a replaceable reasoning host. It does not become Axiom and does not own Axiom's
durable state.

The canonical turn is:

1. `begin_interaction(user_message)`
2. host reasoning using returned Mind context
3. `complete_interaction(user_message, response_text, idempotency_key, proposed_memories)`
4. present the committed response

The ChatGPT-facing MCP server deliberately exposes a smaller surface than the administrative
MCP server.

## Deployment

The existing Render web service now starts:

```text
uvicorn aicognitive_mind.deployment:app --host 0.0.0.0 --port $PORT
```

The same hostname serves:

- the existing Axiom portal and REST API;
- OAuth discovery/authorization endpoints;
- the protected Streamable HTTP endpoint at `/mcp`.

No second hosting service is required.

Render normally supplies the public hostname. `AXIOM_PUBLIC_URL` can override the detected
public origin when needed.

## Authentication

The MCP endpoint is not anonymous.

Axiom co-hosts an OAuth 2.1 authorization-code flow with PKCE/DCR support from the MCP SDK.
The interactive authorization page uses the same `APP_ACCESS_USERNAME` and
`APP_ACCESS_PASSWORD` configured for the Axiom portal.

OAuth clients, access tokens, refresh tokens, and pending grants are operational state rather
than Mind state. They are stored in the existing `runtime_records` persistence so the free Render
service can restart without discarding ChatGPT's registration or refresh-token state. This does
not make OAuth credentials part of Axiom's identity or cognitive memory.

## ChatGPT connection

After the branch is merged and Render reports a healthy deployment:

1. Obtain the existing Render HTTPS hostname.
2. The MCP URL is:
   ```text
   https://<axiom-render-host>/mcp
   ```
3. In a ChatGPT account/workspace that exposes custom MCP developer mode, create a new
   developer-mode plugin/app and use that URL.
4. ChatGPT should discover OAuth from Axiom's protected-resource metadata and open the Axiom
   authorization page.
5. Sign in with the Axiom portal credentials.
6. Review the discovered tools:
   - `mind_status`
   - `begin_interaction`
   - `complete_interaction`
   - `read_sensory_evidence`
7. Install/select **Axiom**.
8. Test a normal question, not only `mind_status`. Verify that the journal records the
   interaction and any accepted durable-memory proposal.

## Host behavior

The MCP server instructions and `plugins/axiom-mind/skills/axiom/SKILL.md` define the
same invariant:

- begin before reasoning;
- complete before presenting the answer;
- the host model supplies inference;
- Axiom supplies continuity;
- memory proposals are conservative and still pass through the Memory Steward;
- retries reuse the same idempotency key and unchanged completion payload.

## Current ChatGPT product gate

The Axiom integration itself is plan-independent MCP/OAuth infrastructure.

As of September 2026, OpenAI documents full custom MCP support including write/modify actions
for Business and Enterprise/Edu workspaces. Axiom requires a write-capable completion call to
journal the interaction and run Memory Steward review. If a ChatGPT account does not expose
that capability, the server may be fully ready while the ChatGPT host surface remains unavailable.

Do not redesign Axiom as a read-only memory lookup to work around that host limitation.

## Acceptance criteria

A ChatGPT-hosted turn is considered operational only when all of the following succeed:

1. ChatGPT authenticates to `/mcp`.
2. `begin_interaction` returns the canonical Mind and recalled context.
3. ChatGPT reasons using that context.
4. `complete_interaction` commits the same response through Axiom.
5. Axiom's journal continuity increments.
6. A later interaction can recall accepted durable memory independently of the ChatGPT model
   used for the earlier turn.
