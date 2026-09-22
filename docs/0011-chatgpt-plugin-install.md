# 0011 — Installing Axiom as a ChatGPT plugin

Axiom is packaged in `plugins/axiom-mind/` as a portable Agent Plugin containing:

- the Axiom host-protocol Skill;
- the deployed Streamable HTTP MCP server;
- the OAuth connection to the persistent Axiom Mind.

The repository also contains `.agents/plugins/marketplace.json`, allowing the
ChatGPT desktop app / Codex plugin tooling to treat this repository as a local
plugin marketplace during development.

## Intended private development flow

The portable MCP server entry is:

```text
https://ai-cognitive-mind-zgk9.onrender.com/mcp
```

The deployment itself derives its canonical public URL from Render's
`RENDER_EXTERNAL_URL`; the packaged URL must be updated if the service is ever
renamed or moved to a custom domain.

For clients that support repository marketplaces:

```text
codex plugin marketplace add Moto1231/AICognitiveMind --ref main
```

Then install **Axiom Mind** from the Axiom marketplace in the ChatGPT desktop
plugin directory and complete the OAuth connection using the Axiom portal
credentials.

## Correct behavior

Installing the plugin does not move Axiom's identity into ChatGPT.

For each Axiom-backed human turn the host Skill requires:

```text
begin_interaction
        ↓
host reasoning
        ↓
complete_interaction
        ↓
human-facing response
```

A successful `complete_interaction` is what closes the cognitive turn and
allows Axiom's independent Memory Steward and journal to process the experience.

## Current account-surface caveat

Axiom itself exposes the complete read/write MCP contract. ChatGPT may still
limit private custom MCP write actions according to the account/workspace
entitlement. Do not mark `complete_interaction` read-only or bypass completion
to work around a host restriction.

The same portable package is suitable for public plugin submission once the
remote endpoint has been tested from a supported ChatGPT surface.
