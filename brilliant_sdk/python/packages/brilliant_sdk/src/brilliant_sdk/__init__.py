"""
brilliant_sdk - Python SDK for Brilliant Labs Frame and Halo devices (https://brilliant.xyz/)
"""

from brilliant_ble import BrilliantBle, BrilliantDeviceType

from brilliant_msg import (
    BrilliantMsg,
    TxAutoExpSettings,
    TxCaptureSettings,
    TxCode,
    TxImageSpriteBlock,
    TxManualExpSettings,
    TxPlainText,
    TxSprite,
    TxSpriteCoords,
    TxTextSpriteBlock,
    RxAudio,
    RxAutoExpResult,
    RxIMU,
    RxMeteringData,
    RxPhoto,
    RxTap,
)

from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("brilliant-sdk")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"