## 1.1.0

* New `drainPrintChannel(quietMs = 250, maxTotalMs = 1500)` — discards unsolicited print output already arriving on the channel (such as the `interrupted`/reboot banner produced by a break or reset) so the next awaited response is clean rather than the stray banner. Bounded so it never hangs: resolves after `quietMs` of silence, or `maxTotalMs` at the latest

Added to the source during the Halo firmware 0.8.8 work but shipped without a version bump. `brilliant-msg` bundles `brilliant-ble` into its own output, so no released `brilliant-msg` was affected; this release brings the standalone package back in step with the source.

## 1.0.1

* Fixed `uploadFileFromString()` failing on Lua files containing non-ASCII characters (e.g. `°`): chunks are now sized by UTF-8 byte length rather than string length, so multi-byte characters can no longer push a packet over the MTU. Multi-byte characters and escape sequences are never split across chunks
* New `chunkLuaString()` function exposing the byte-accurate chunking, exported from package

## 0.4.0

* Added Halo device support
* `BrilliantDeviceType` enum (`FRAME`, `HALO`, `UNKNOWN`) exported from package
* `FrameBle.type` getter — device type is detected automatically at connection time by probing for the Halo audio TX characteristic
* `sendAudio(data, awaitBtResponse?)` — writes to the Halo audio characteristic (UUID `7a230005-...`), write-without-response by default, silently drops oversized packets
* `sendRemoveSignal()` — sends `0x05` signal byte to remove `main.lua` from Halo
* `sendData()` and `sendMessage()` — new `awaitBtResponse` option to control BLE write-with/without-response
* `transmit()` internally uses `writeValueWithResponse` or `writeValueWithoutResponse` based on `awaitBtResponse`
* Disconnect and failed connection attempts now reset `audioTxCharacteristic` and `deviceType`

## 0.3.1

* Improved TypeDoc comments for API reference

## 0.3.0

* connect() returns device name in preference to device id
* examples: print console log messages to example web page in addition to console log (helpful for mobile browsers with no dev tools/console)

## 0.2.2

* Republished with dist files generated

## 0.2.1

* Republished with package lock updated

## 0.2.0

* Added retry logic to `connect()` call for specific intermittent connection errors

## 0.1.0

* Initial version ported from Python
