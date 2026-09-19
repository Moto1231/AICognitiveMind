from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from typing import Any

from pymongo import MongoClient

COGNITIVE_COLLECTIONS = ("mind", "journal", "memory", "diagnostics")


def _collection_count(database: Any, name: str) -> int:
    return int(database[name].count_documents({}))


def validate_source(database: Any) -> dict[str, int]:
    counts = {name: _collection_count(database, name) for name in COGNITIVE_COLLECTIONS}
    if counts["mind"] != 1:
        raise RuntimeError(
            "Source must contain exactly one Mind document; "
            f"found {counts['mind']}."
        )
    return counts


def validate_empty_target(database: Any) -> None:
    occupied = {
        name: _collection_count(database, name)
        for name in COGNITIVE_COLLECTIONS
        if _collection_count(database, name)
    }
    if occupied:
        details = ", ".join(f"{name}={count}" for name, count in occupied.items())
        raise RuntimeError(
            "Target is not empty; refusing to merge two cognitive histories. "
            f"Existing documents: {details}"
        )


def copy_collection(source: Any, target: Any, name: str) -> int:
    documents = list(source[name].find({}))
    if documents:
        target[name].insert_many(documents, ordered=True)
    return len(documents)


def migrate(source: Any, target: Any) -> dict[str, int]:
    counts = validate_source(source)
    validate_empty_target(target)
    copied = {
        name: copy_collection(source, target, name)
        for name in COGNITIVE_COLLECTIONS
    }
    if copied != counts:
        raise RuntimeError(
            f"Migration verification failed: source={counts}, copied={copied}"
        )
    return copied


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Move the one canonical Cognitive Mind between MongoDB databases "
            "without reinitializing identity."
        )
    )
    parser.add_argument(
        "--source-uri",
        default=os.environ.get("SOURCE_MONGODB_URI"),
        help="Source MongoDB URI (or SOURCE_MONGODB_URI).",
    )
    parser.add_argument(
        "--source-database",
        default=os.environ.get("SOURCE_MONGODB_DATABASE", "ai_cognitive_mind"),
        help="Source database name.",
    )
    parser.add_argument(
        "--target-uri",
        default=os.environ.get("TARGET_MONGODB_URI"),
        help="Target MongoDB URI (or TARGET_MONGODB_URI).",
    )
    parser.add_argument(
        "--target-database",
        default=os.environ.get("TARGET_MONGODB_DATABASE", "ai_cognitive_mind"),
        help="Target database name.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.source_uri:
        raise SystemExit("SOURCE_MONGODB_URI or --source-uri is required")
    if not args.target_uri:
        raise SystemExit("TARGET_MONGODB_URI or --target-uri is required")

    source_client = MongoClient(args.source_uri)
    target_client = MongoClient(args.target_uri)
    try:
        source_client.admin.command("ping")
        target_client.admin.command("ping")
        copied = migrate(
            source_client[args.source_database],
            target_client[args.target_database],
        )
    finally:
        source_client.close()
        target_client.close()

    print("Canonical Mind migration complete.")
    for name in COGNITIVE_COLLECTIONS:
        print(f"{name}: {copied[name]}")


if __name__ == "__main__":
    main()
