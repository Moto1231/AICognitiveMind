# Brilliant SDK

A multi-platform SDK for building applications that communicate with [Brilliant Labs](https://brilliant.xyz/) smart glasses — **Halo** and **Frame**.

Devices run user scripts in an on-device **Lua 5.4 VM** and expose the `frame.*` API for display, Bluetooth, IMU, audio, file I/O, and more. The SDK handles the host side: BLE transport, message framing, and rich data types (images, text, audio, sensor data).

---

## SDK Implementations

| Platform | Location | Packages |
|----------|----------|---------|
| **Python** | [`python/`](./python/) | `brilliant-ble`, `brilliant-msg`, `brilliant-sdk` |
| **Flutter** (Android / iOS) | [`flutter/`](./flutter/) | `brilliant_ble`, `brilliant_msg`, `brilliant_sdk`, `simple_brilliant_app` |
| **WebBluetooth** (TypeScript) | [`webbluetooth/`](./webbluetooth/) | `brilliant-ble`, `brilliant-msg`, `brilliant-sdk` |

Each implementation has its own README with installation, usage, and development instructions.

---

## Installation

**Python** — [PyPI](https://pypi.org/project/brilliant-sdk/)
```bash
pip install brilliant-sdk
# or: pip install brilliant-ble  /  pip install brilliant-msg
```

**Flutter** — [pub.dev](https://pub.dev/packages/brilliant_sdk)
```bash
flutter pub add brilliant_sdk
# or: flutter pub add brilliant_ble  /  flutter pub add brilliant_msg
```

**WebBluetooth** — [npm](https://www.npmjs.com/package/brilliant-sdk)
```bash
npm install brilliant-sdk
# or: npm install brilliant-ble  /  npm install brilliant-msg
```

---

## Architecture

All three SDKs share the same two-layer architecture:

```
┌──────────────────────────────────────────────────────────┐
│  Application (your code)                                 │
├──────────────────────────────────────────────────────────┤
│  brilliant_msg  — rich message types (sprites, text,     │
│               audio, IMU, photos, clicks …)              │
├──────────────────────────────────────────────────────────┤
│  brilliant_ble  — BLE transport (connect, scan, MTU-aware│
│               packet splitting, DFU)                     │
├──────────────────────────────────────────────────────────┤
│  Bluetooth LE                                            │
├──────────────────────────────────────────────────────────┤
│  Device (Halo / Frame)  —  Lua 5.4 VM + frame.* API      │
└──────────────────────────────────────────────────────────┘
```

**`brilliant_ble`** — Low-level BLE layer. Finds and connects to the device, negotiates MTU, splits large payloads into MTU-sized packets, and manages connection state.

**`brilliant_msg`** — Application-level messaging. Defines TX (host → device) and RX (device → host) message types for sprites, rasterized text, photos, audio, IMU data, taps, and click events. Each message type is paired with a corresponding Lua library that runs on the device.

**Lua on device** — Every message type has a matching `.lua` script (and minified `.min.lua`) that receives and renders the data on the device side.

---

## Develop Without Hardware

The [`halo-emulator`](./python/packages/halo_emulator/) package
([PyPI](https://pypi.org/project/halo-emulator/)) runs device-side Lua apps in
a firmware-faithful Halo emulator — Lua 5.4, real fonts and palette, IMU / tap
/ microphone event injection — so apps can be developed and tested with no
glasses attached:

```bash
pip install halo-emulator
halo-emulator ./my_app/   # interactive REPL + display window
```

The device-side Lua is identical across all three SDKs, so the emulator is
useful for validating the Lua half of Flutter and WebBluetooth apps too. See
its [README](./python/packages/halo_emulator/README.md) for the test-writing
API and the supported `frame.*` surface.

---

## Device Support

Both **Halo** and **Frame** are supported across all SDK implementations. Device type is detected automatically after connecting.

| Feature | Frame | Halo |
|---------|:-----:|:----:|
| Display (sprites, text, bitmaps) | ✓ | ✓ |
| Camera / photo capture | ✓ | ✓ |
| IMU (accelerometer, magnetometer) | ✓ | ✓ |
| Audio streaming | ✓ | ✓ |
| Tap events | ✓ | ✓ |
| Click events (single / double / long) | — | ✓ |
| Audio activity detection | — | ✓ |

---

## Documentation

- [Brilliant Labs developer docs](https://docs.brilliant.xyz/) — device docs,
  SDK guides, and the on-device Lua API references for
  [Halo](https://docs.brilliant.xyz/halo/halo-sdk-lua/) and
  [Frame](https://docs.brilliant.xyz/frame/frame-sdk-lua/)
- Python API reference: [brilliant-ble](https://brilliant-ble.readthedocs.io/)
  · [brilliant-msg](https://brilliant-msg.readthedocs.io/)
- [WebBluetooth examples + TypeDoc](https://brilliantlabsar.github.io/brilliant_sdk/)
- Example indexes: [Python msg](./python/packages/brilliant_msg/examples/EXAMPLES.md)
  · [Python ble](./python/packages/brilliant_ble/examples/EXAMPLES.md)
  · [Flutter apps](./flutter/packages/simple_brilliant_app/example/EXAMPLES.md)
  · [WebBluetooth](./webbluetooth/packages/brilliant-msg/example/EXAMPLES.md)
- AI coding agents: start at [`AGENTS.md`](./AGENTS.md)

---

## License

All packages in this repository are released under the [BSD 3-Clause License](./LICENSE).
