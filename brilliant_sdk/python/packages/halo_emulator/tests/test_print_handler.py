"""The print_handler contract: it is always called with a single str."""
from __future__ import annotations

import time
from pathlib import Path

from halo_emulator import HaloEmulator


def test_print_receives_str_for_all_lua_types(tmp_path: Path):
    lines: list = []
    emu = HaloEmulator(sandbox_dir=tmp_path, print_handler=lines.append)
    emu.connect()
    emu.execute_lua("print('hello')")
    emu.execute_lua("print(42, true, nil, {1, 2}, 'multi')")

    assert all(isinstance(line, str) for line in lines)
    assert lines[0] == "hello"
    # Lua print semantics: tostring each argument, tab-joined
    parts = lines[1].split("\t")
    assert parts[0] == "42"
    assert parts[1] == "true"
    assert parts[2] == "nil"
    assert parts[4] == "multi"


def test_print_of_caught_stop_exception_is_str(tmp_path: Path):
    # An app's pcall catches the injected stop exception and prints it —
    # the handler must still receive a str, not an exception object.
    (tmp_path / "main.lua").write_text(
        """
        while true do
            local rc, err = pcall(function() frame.sleep(0.05) end)
            if rc == false then
                print(err)
                break
            end
        end
        """
    )
    lines: list = []
    emu = HaloEmulator(sandbox_dir=tmp_path, print_handler=lines.append)
    emu.start("main.lua")
    time.sleep(0.15)
    emu.stop()

    assert lines, "expected the caught stop exception to be printed"
    assert all(isinstance(line, str) for line in lines)
