from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any, TypeVar

from pydantic import BaseModel
from pymongo import AsyncMongoClient

from aicognitive_mind.config import Settings, get_settings
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
)
from aicognitive_mind.surreal_storage import SurrealRuntime, _document, _records


COGNITIVE_TABLES = ("mind", "journal", "memory", "diagnostics")
T = TypeVar("T", bound=BaseModel)

MODEL_BY_TABLE: dict[str, type[BaseModel]] = {
    "mind": CognitiveMind,
    "journal": JournalEntry,
    "memory": DurableMemory,
    "diagnostics": DiagnosticObservation,
}


def _require_remote_surreal(settings: Settings) -> None:
    if not settings.surrealdb_uri.startswith(("wss://", "https://")):
        raise SystemExit(
            "Refusing canonical Surreal operation: SURREALDB_URI must be a remote TLS endpoint "
            "(wss:// or https://)."
        )


def _require_atlas(settings: Settings) -> None:
    if not settings.mongodb_uri.startswith("mongodb+srv://"):
        raise SystemExit(
            "Refusing Atlas migration source: MONGODB_URI must use mongodb+srv://"
        )


def _strip_mongo_id(document: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key != "_id"}


def _validated(
    table: str,
    documents: list[dict[str, Any]],
) -> list[BaseModel]:
    model = MODEL_BY_TABLE[table]
    return [model.model_validate(_strip_mongo_id(document)) for document in documents]


def _normalized(models: list[BaseModel]) -> list[str]:
    return sorted(
        json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        for model in models
    )


async def _surreal_counts(runtime: SurrealRuntime) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in COGNITIVE_TABLES:
        counts[table] = len(_records(await runtime.database.select(table)))
    return counts


async def _surreal_models(
    runtime: SurrealRuntime,
) -> dict[str, list[BaseModel]]:
    result: dict[str, list[BaseModel]] = {}
    for table in COGNITIVE_TABLES:
        records = _records(await runtime.database.select(table))
        model = MODEL_BY_TABLE[table]
        result[table] = [
            model.model_validate(_document(record))
            for record in records
        ]
    return result


async def _atlas_models(
    settings: Settings,
) -> dict[str, list[BaseModel]]:
    client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(settings.mongodb_uri)
    try:
        await client.admin.command("ping")
        database = client[settings.mongodb_database]
        result: dict[str, list[BaseModel]] = {}
        for table in COGNITIVE_TABLES:
            raw: list[dict[str, Any]] = []
            async for document in database[table].find({}):
                raw.append(document)
            result[table] = _validated(table, raw)
        return result
    finally:
        await client.close()


def _print_counts(label: str, counts: dict[str, int]) -> None:
    print(label)
    for table in COGNITIVE_TABLES:
        print(f"{table}: {counts[table]}")


async def _check(settings: Settings) -> None:
    runtime = SurrealRuntime(
        settings.surrealdb_uri,
        settings.surrealdb_namespace,
        settings.surrealdb_database,
        settings.surrealdb_username,
        settings.surrealdb_password,
    )
    await runtime.initialize()
    try:
        counts = await _surreal_counts(runtime)
        print("Surreal connection: OK")
        print(f"namespace: {settings.surrealdb_namespace}")
        print(f"database: {settings.surrealdb_database}")
        _print_counts("cognitive tables:", counts)
    finally:
        await runtime.close()


async def _rollback_surreal(runtime: SurrealRuntime) -> None:
    for table in COGNITIVE_TABLES:
        try:
            await runtime.database.delete(table)
        except Exception:
            pass


async def _migrate_from_atlas(settings: Settings) -> None:
    source = await _atlas_models(settings)
    if len(source["mind"]) != 1:
        raise SystemExit(
            "Migration refused: Atlas source must contain exactly one Mind; "
            f"found {len(source['mind'])}."
        )

    runtime = SurrealRuntime(
        settings.surrealdb_uri,
        settings.surrealdb_namespace,
        settings.surrealdb_database,
        settings.surrealdb_username,
        settings.surrealdb_password,
    )
    await runtime.initialize()

    try:
        target_counts = await _surreal_counts(runtime)
        nonempty = {name: count for name, count in target_counts.items() if count}
        if nonempty:
            details = ", ".join(f"{name}={count}" for name, count in nonempty.items())
            raise SystemExit(
                "Migration refused: canonical Surreal cognitive tables are not empty: "
                f"{details}"
            )

        print("Atlas source validated.")
        _print_counts(
            "Atlas cognitive documents:",
            {table: len(source[table]) for table in COGNITIVE_TABLES},
        )

        try:
            for table in COGNITIVE_TABLES:
                for model in source[table]:
                    await runtime.database.create(
                        table,
                        model.model_dump(mode="json"),
                    )

            target = await _surreal_models(runtime)
            for table in COGNITIVE_TABLES:
                if _normalized(source[table]) != _normalized(target[table]):
                    raise RuntimeError(
                        f"Verification mismatch after migrating table: {table}"
                    )
        except Exception:
            await _rollback_surreal(runtime)
            print("Migration failed; Surreal cognitive tables rolled back.")
            raise

        print("Canonical Surreal migration: COMPLETE")
        mind = source["mind"][0]
        assert isinstance(mind, CognitiveMind)
        print(f"self_name: {mind.identity.self_name}")
        print(f"developmental_state: {mind.developmental_state}")
        _print_counts(
            "Verified Surreal cognitive documents:",
            {table: len(target[table]) for table in COGNITIVE_TABLES},
        )
    finally:
        await runtime.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inspect or migrate the canonical persistent Surreal Cognitive Mind."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "check",
        help="Connect to canonical Surreal and report cognitive table counts.",
    )
    subparsers.add_parser(
        "migrate-from-atlas",
        help="Copy one validated Mind from canonical Atlas into an empty canonical Surreal target.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    _require_remote_surreal(settings)

    if args.command == "check":
        asyncio.run(_check(settings))
        return

    _require_atlas(settings)
    asyncio.run(_migrate_from_atlas(settings))


if __name__ == "__main__":
    main()
