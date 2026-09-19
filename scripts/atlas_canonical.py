from __future__ import annotations

import argparse
import asyncio
from typing import Any

from pymongo import AsyncMongoClient

from aicognitive_mind.config import Settings, get_settings
from aicognitive_mind.initialize_cli import initialize_once


COGNITIVE_COLLECTIONS = ("mind", "journal", "memory", "diagnostics")


def _require_atlas(settings: Settings) -> None:
    if not settings.mongodb_uri.startswith("mongodb+srv://"):
        raise SystemExit(
            "Refusing canonical Atlas operation: MONGODB_URI must use mongodb+srv://"
        )


async def _collection_counts(settings: Settings) -> dict[str, int]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(settings.mongodb_uri)
    try:
        await client.admin.command("ping")
        database = client[settings.mongodb_database]
        counts: dict[str, int] = {}
        for name in COGNITIVE_COLLECTIONS:
            counts[name] = await database[name].count_documents({})
        return counts
    finally:
        await client.close()


def _print_status(settings: Settings, counts: dict[str, int]) -> None:
    print("Atlas connection: OK")
    print(f"database: {settings.mongodb_database}")
    for name in COGNITIVE_COLLECTIONS:
        print(f"{name}: {counts[name]}")


async def _check(settings: Settings) -> None:
    counts = await _collection_counts(settings)
    _print_status(settings, counts)


async def _genesis(
    settings: Settings,
    self_name: str,
    foundational_values: tuple[str, ...],
) -> None:
    counts = await _collection_counts(settings)
    _print_status(settings, counts)

    nonempty = {name: count for name, count in counts.items() if count != 0}
    if nonempty:
        details = ", ".join(f"{name}={count}" for name, count in nonempty.items())
        raise SystemExit(
            "Genesis refused: canonical Atlas cognitive collections are not empty: "
            f"{details}"
        )

    result = await initialize_once(settings, self_name, foundational_values)
    mind = result["mind"]
    identity = mind["identity"]

    print("Canonical Atlas genesis: COMPLETE")
    print(f"self_name: {identity['self_name']}")
    print(f"developmental_state: {mind['developmental_state']}")
    print(f"foundational_values: {len(identity['foundational_values'])}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Safely inspect or initialize the canonical Atlas Cognitive Mind."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser(
        "check",
        help="Ping Atlas and report cognitive collection document counts without initializing.",
    )

    genesis = subparsers.add_parser(
        "genesis",
        help="Initialize one fresh Mind only when all cognitive collections are empty.",
    )
    genesis.add_argument("--self-name", required=True)
    genesis.add_argument(
        "--value",
        action="append",
        default=[],
        dest="values",
        help="Foundational value. Repeat for additional values.",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    _require_atlas(settings)

    if args.command == "check":
        asyncio.run(_check(settings))
        return

    asyncio.run(_genesis(settings, args.self_name, tuple(args.values)))


if __name__ == "__main__":
    main()
