# CLAUDE.md — flutter workspace

Architecture, cross-SDK parity rules, and reading paths are in the repo-root
`AGENTS.md` — read that first. This file is Melos-workspace specifics only.

This is a **Melos monorepo** with 4 packages under `packages/`:
`brilliant_ble` (uses `flutter_blue_plus`), `brilliant_msg`, `brilliant_sdk`
(meta-package), and `simple_brilliant_app` (high-level `SimpleFrameApp` /
`FrameVisionApp` framework, with 17 example apps under `example/` — see
`example/EXAMPLES.md`).

## Commands

Requires [Melos](https://melos.invertase.dev/) (`dart pub global activate melos`).

```bash
melos bootstrap   # flutter pub get in all packages (run after cloning)
melos analyze     # flutter analyze in all packages
melos format      # dart format . in all packages
melos test        # flutter test in all packages (no hardware needed)
cd packages/brilliant_msg && flutter test test/tx/code_test.dart  # single file
```

- **Publishing**: use the `release` skill (`.claude/skills/release/`) —
  `pubspec_overrides.yaml` points sibling packages at local source, so local
  tests prove nothing about a published package's dependencies.
- No hardware-free way to run device-side Lua here — validate the Lua half
  with the Python `halo-emulator` (`pip install halo-emulator`); the Lua files
  are identical across SDKs.

## Dart-specific patterns

- BLE state and RX data are exposed as Dart streams; TX classes implement
  `pack() -> Uint8List`.
- When adding a message type: Dart class + device Lua (in `lib/lua/`, plus
  `.min.lua`) must be updated together, then mirrored to the Python and
  WebBluetooth SDKs (`tools/check_lua_parity.py`).
- Lua files ship as Flutter assets — new `.lua` files must be listed under
  `assets:` in the consuming app's `pubspec.yaml`.
