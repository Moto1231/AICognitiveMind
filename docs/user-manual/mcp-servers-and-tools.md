# MCP Servers and Tools

[Manual index](README.md) · [Review record](review-record.md)

> Reviewed against source revision `57f38db876e63d45e37f58f57768e25396a75a8d` on 2026-10-25. All sections on this page share this review revision. This is source review, not authenticated browser or physical-device certification.

## Configure a tool server

Open **Administration → Endpoints, Servers & Tools → MCP Servers**. This section is separate from the model-provider Endpoints section above it.

1. Choose **Add**.
2. Enter a **Server name** and absolute **Streamable HTTP URL**.
3. Enter a **Bearer token (optional)** only if that server requires it.
4. Review **Enable this server**.
5. Choose **Discover Tools**.
6. Review the returned tools and enable the ones intended for use.
7. Choose the MCP server **Save**.

Discovery on an existing saved server enters edit mode so the returned tool list can be saved. The discovery success message explicitly asks you to Save. Discovery itself is not persistence.

The form supports a bearer token; do not assume it performs an arbitrary external service's interactive OAuth flow. Keep server credentials out of public documentation.

## Edit the allowed tools

1. Select the saved server.
2. Choose **Edit**.
3. Change server fields or tool enablement.
4. Save the server/tool configuration together.

**Cancel** discards the draft. **Remove** on a saved server submits removal immediately. It does not require a later Save.

An enabled server and tool are configuration prerequisites, not evidence that the remote server will authorize the operation or that the host may perform it under its own permission rules.

## Run a deliberate test

The **Tools → Test a Tool** area calls a real saved, enabled tool.

1. Save the server and leave edit mode.
2. Select an **Enabled tool**.
3. Read its expected arguments and effects.
4. Enter an **Arguments (JSON object)** value.
5. Choose **Run Tool** only for an operation you intend to execute.
6. Read the returned result or error.

```json
{}
```

An empty object is valid JSON, but only suitable for a tool that accepts no required arguments. A JSON array, bare string or malformed object is not accepted by the UI.

A tool named “send,” “delete,” or “create” may actually change the remote system. This tester is not a dry-run sandbox. Prefer a documented read/status operation for a first connection check.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Discover Tools disabled | Server name, valid URL, active operation and draft state |
| Discovery succeeds but list disappears after reload | Save the discovered configuration |
| Run Tool unavailable | Save/exit editing, select an enabled saved server/tool |
| Invalid tool arguments | JSON must be an object; satisfy the specific tool schema |
| Tool not found | Server catalog may have changed; rediscover and review |
| Authentication error | That server's token/access, separately from the portal session |
| Model discovered but no tools here | Model discovery and MCP tool discovery are different workflows |

The Administrator server registry is also distinct from the tools a chat host exposes through its installed plugins. Saving an MCP server here does not prove a separate chat host refreshed its own catalog.

## Source references

- [src/aicognitive_mind/static/index.html](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/index.html)
- [src/aicognitive_mind/static/portal.js](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/static/portal.js)
- [src/aicognitive_mind/api.py](https://github.com/Moto1231/AICognitiveMind/blob/57f38db876e63d45e37f58f57768e25396a75a8d/src/aicognitive_mind/api.py)
