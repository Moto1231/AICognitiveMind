from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("halo-emulator")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"

from halo_emulator.emulator import HaloEmulator
from halo_emulator.adapter import EmulatorBrilliantMsg
from halo_emulator.recorder import VideoRecorder

__all__ = ["HaloEmulator", "EmulatorBrilliantMsg", "VideoRecorder"]
