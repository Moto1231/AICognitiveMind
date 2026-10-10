#!/usr/bin/env python3
"""Check that the device-side Lua libraries are identical across the three SDKs.

Each brilliant_msg package ships its own copy of the same Lua files, and all
three copies must stay byte-for-byte in sync (including the .min.lua siblings).
A feature or fix applied to one copy must be applied to all of them.

Exit status: 0 if all copies match, 1 otherwise.
"""

import hashlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

LUA_DIRS = {
    "python": REPO_ROOT / "python/packages/brilliant_msg/src/brilliant_msg/lua",
    "flutter": REPO_ROOT / "flutter/packages/brilliant_msg/lib/lua",
    "webbluetooth": REPO_ROOT / "webbluetooth/packages/brilliant-msg/src/lua",
}


def main() -> int:
    files_per_sdk = {
        sdk: {p.name for p in path.glob("*.lua")} for sdk, path in LUA_DIRS.items()
    }
    all_names = sorted(set().union(*files_per_sdk.values()))

    problems = []
    for name in all_names:
        missing = [sdk for sdk, names in files_per_sdk.items() if name not in names]
        if missing:
            problems.append(f"{name}: missing from {', '.join(missing)}")
            continue
        digests = {
            sdk: hashlib.sha256((path / name).read_bytes()).hexdigest()
            for sdk, path in LUA_DIRS.items()
        }
        if len(set(digests.values())) > 1:
            detail = ", ".join(f"{sdk}={d[:12]}" for sdk, d in digests.items())
            problems.append(f"{name}: content differs ({detail})")

    if problems:
        print("Device-side Lua libraries have drifted between SDKs:\n")
        for p in problems:
            print(f"  {p}")
        print(
            "\nThese files are triplicated by design and must be kept byte-for-byte"
            "\nidentical (both .lua and .min.lua). Apply the same change to:"
        )
        for sdk, path in LUA_DIRS.items():
            print(f"  {path.relative_to(REPO_ROOT)}  ({sdk})")
        return 1

    print(f"OK: {len(all_names)} Lua files identical across {len(LUA_DIRS)} SDKs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
