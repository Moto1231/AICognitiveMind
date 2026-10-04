# CLAUDE.md — webbluetooth workspace

Architecture, cross-SDK parity rules, and reading paths are in the repo-root
`AGENTS.md` — read that first. This file is npm-workspace specifics only.

This is an **npm workspace** (TypeScript, browser WebBluetooth) with 3
packages under `packages/`: `brilliant-ble`, `brilliant-msg`, and
`brilliant-sdk` (re-exports both). Examples live in each package's `example/`
directory; `packages/brilliant-msg/example/EXAMPLES.md` indexes them with full
source inline.

## Commands

```bash
npm install        # from workspace root or a package dir
npm run build      # build dist/ (run from a package directory)
npm run dev        # Vite dev server for the example app
npm run docs:api   # generate TypeDoc API docs
```

- **`dist/` is committed** and must be rebuilt before publishing.
- **Publishing**: use the `release` skill (`.claude/skills/release/`).
- There is no test suite here — `npm run build` per package is the minimum
  check. Validate device-side Lua with the Python `halo-emulator`
  (`pip install halo-emulator`); the Lua files are identical across SDKs.

## TypeScript-specific patterns

- Vite builds ESM (`*.es.js`) and UMD (`*.umd.js`) bundles plus `.d.ts` files
  into `dist/`.
- TX classes serialize to `Uint8Array`; all device I/O is Promise/async.
- When adding a message type: TS class + device Lua (in `src/lua/`, plus
  `.min.lua`) must be updated together, then mirrored to the Python and
  Flutter SDKs (`tools/check_lua_parity.py`).
