# CLAUDE.md — python workspace

Architecture, cross-SDK parity rules, and reading paths are in the repo-root
`AGENTS.md` — read that first. This file is uv-workspace specifics only.

This is a **uv workspace** with 4 packages under `packages/`: `brilliant_ble`,
`brilliant_msg`, `brilliant_sdk` (meta-package), and `halo_emulator`
(firmware-faithful Halo emulator, published to PyPI as `halo-emulator` — use it
to run device-side Lua without hardware).

## Commands

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync --all-packages --all-extras   # install everything incl. test deps
uv run pytest                         # all hardware-free tests (~240, fast)
uv run pytest packages/brilliant_msg/tests/   # one package
uv build --package brilliant-ble      # build a specific package
uv run halo-emulator ./my_app/        # interactive emulator REPL
```

- Device-requiring tests are skipped unless `BRILLIANT_DEVICE=1` is set; most
  `test_*.py` under `packages/brilliant_ble/tests/` are standalone device
  scripts (`uv run python <file> --name Halo`), not pytest tests — see the
  `conftest.py` there.
- **Publishing**: use the `release` skill (`.claude/skills/release/`) — do not
  publish ad hoc; local workspace resolution hides unreleased-dependency
  breakage.

## Python-specific patterns

- All device I/O is `asyncio` (`bleak` under the hood).
- TX message classes implement `pack() -> bytes`; RX classes parse from byte
  streams; message codes are single bytes assigned per app.
- When adding a message type: Python class + device Lua (in
  `src/brilliant_msg/lua/`, plus `.min.lua`) must be updated together, then
  mirrored to the Flutter and WebBluetooth SDKs (`tools/check_lua_parity.py`).
