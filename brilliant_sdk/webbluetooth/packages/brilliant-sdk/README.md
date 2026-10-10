# brilliant-sdk

WebBluetooth SDK meta-package for [Brilliant Labs Frame and Halo](https://brilliant.xyz/) devices — installs both `brilliant-ble` and `brilliant-msg` with a single import.

[Frame SDK documentation](https://docs.brilliant.xyz/frame/frame-sdk/) | [GitHub Repo](https://github.com/brilliantlabsAR/brilliant_sdk/tree/main/webbluetooth/packages/brilliant-sdk)

## Installation

```bash
npm install brilliant-sdk
```

## Usage

```typescript
import { BrilliantBle, BrilliantMsg, BrilliantDeviceType, TxSprite, RxPhoto } from 'brilliant-sdk';
```

All exports from `brilliant-ble` and `brilliant-msg` are available directly from `brilliant-sdk`.

## Packages

- **[brilliant-ble](https://www.npmjs.com/package/brilliant-ble)** — low-level Bluetooth LE connection library
- **[brilliant-msg](https://www.npmjs.com/package/brilliant-msg)** — message types and protocol handlers
