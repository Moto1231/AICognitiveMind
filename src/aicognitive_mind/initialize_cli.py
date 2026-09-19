from __future__ import annotations

import argparse
import asyncio
from typing import Any

from aicognitive_mind.config import Settings, get_settings
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.storage import MindAlreadyInitializedError


async def initialize_once(
    settings: Settings,
    self_name: str,
    foundational_values: tuple[str, ...],
) -> dict[str, Any]:
    storage = await create_storage(settings)
    try:
        service = CognitiveMcpService(
            mind=storage.mind,
            journal=storage.journal,
            memory=storage.memory,
        )
        return await service.initialize(self_name, foundational_values)
    finally:
        await storage.runtime.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Initialize one fresh Cognitive Mind in the configured persistent storage."
    )
    parser.add_argument("--self-name", required=True, help="The Mind's self-name.")
    parser.add_argument(
        "--value",
        action="append",
        default=[],
        dest="values",
        help="Foundational value. Repeat --value for additional values.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    try:
        result = asyncio.run(
            initialize_once(settings, args.self_name, tuple(args.values))
        )
    except MindAlreadyInitializedError as exc:
        raise SystemExit(
            "Initialization refused: the configured storage already contains a Mind."
        ) from exc

    mind = result["mind"]
    identity = mind["identity"]
    print("Mind initialized.")
    print(f"self_name: {identity['self_name']}")
    print(f"developmental_state: {mind['developmental_state']}")
    print(f"foundational_values: {len(identity['foundational_values'])}")


if __name__ == "__main__":
    main()
