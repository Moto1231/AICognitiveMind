from __future__ import annotations

import argparse
import asyncio
import base64
from pathlib import Path

from aicognitive_mind.body.eyes import OpenCvVisionSensor


def _save_data_uri(content_ref: str, destination: Path) -> None:
    prefix = "data:image/jpeg;base64,"
    if not content_ref.startswith(prefix):
        raise RuntimeError("Eyes returned an unexpected visual content reference.")
    destination.write_bytes(base64.b64decode(content_ref.removeprefix(prefix)))


async def _run(args: argparse.Namespace) -> int:
    eyes = OpenCvVisionSensor(
        camera_index=args.camera,
        warmup_frames=args.warmup_frames,
        jpeg_quality=args.jpeg_quality,
    )
    status = await eyes.status()
    print(
        f"eyes: {'available' if status.available else 'unavailable'}"
        + (f" ({status.detail})" if status.detail else "")
    )
    if args.status_only or not status.available:
        return 0 if status.available else 1

    percept = await eyes.observe()
    width = percept.metadata.get("width")
    height = percept.metadata.get("height")
    print("Eyes V0.1 capture: OK")
    print(f"source: {percept.source}")
    print(f"observed_at: {percept.observed_at.isoformat()}")
    print(f"frame: {width}x{height}")
    print("storage: transient in-memory JPEG")

    if args.output is not None:
        destination = Path(args.output).expanduser().resolve()
        _save_data_uri(percept.content_ref or "", destination)
        print(f"explicit test copy: {destination}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test the Body Eyes V0.1 webcam adapter on the local machine."
    )
    parser.add_argument("--camera", type=int, default=0, help="Webcam index. Default: 0")
    parser.add_argument(
        "--warmup-frames",
        type=int,
        default=3,
        help="Frames discarded before the observation. Default: 3",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=90,
        help="In-memory JPEG quality from 1-100. Default: 90",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Check whether the camera can be opened without capturing a percept.",
    )
    parser.add_argument(
        "--output",
        help="Optional path for an explicit JPEG test copy. No file is written by default.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
