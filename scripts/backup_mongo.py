from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from bson.json_util import CANONICAL_JSON_OPTIONS, dumps, loads
from pymongo import MongoClient

if __package__:
    from .migrate_mongo import (
        COGNITIVE_COLLECTIONS,
        validate_empty_target,
        validate_source,
    )
else:
    from migrate_mongo import (  # type: ignore[no-redef]
        COGNITIVE_COLLECTIONS,
        validate_empty_target,
        validate_source,
    )

BACKUP_FORMAT = "aicognitive-mind-mongo-backup"
BACKUP_VERSION = 1
MANIFEST_PATH = "manifest.json"

DocumentsByCollection = dict[str, list[dict[str, Any]]]


def _collection_path(name: str) -> str:
    return f"collections/{name}.json"


def _canonical_documents(documents: list[dict[str, Any]]) -> bytes:
    return dumps(
        documents,
        json_options=CANONICAL_JSON_OPTIONS,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _utc_timestamp(value: datetime | None = None) -> str:
    timestamp = value or datetime.now(timezone.utc)
    if timestamp.tzinfo is None:
        raise ValueError("Backup timestamps must include a timezone.")
    return timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _source_database_name(database: Any) -> str:
    name = getattr(database, "name", None)
    if not isinstance(name, str) or not name:
        raise RuntimeError("Source database name is unavailable.")
    return name


def _capture_documents(database: Any) -> tuple[dict[str, int], DocumentsByCollection]:
    before = validate_source(database)
    documents = {
        name: list(database[name].find({}))
        for name in COGNITIVE_COLLECTIONS
    }
    captured = {name: len(items) for name, items in documents.items()}
    after = validate_source(database)
    if captured != before or after != before:
        raise RuntimeError(
            "Source changed while the backup was being captured; stop writers and retry."
        )
    for name, items in documents.items():
        if any("_id" not in document for document in items):
            raise RuntimeError(f"Collection {name!r} contains a document without MongoDB _id.")
    return captured, documents


def create_backup(
    database: Any,
    output_path: str | Path,
    *,
    created_at: datetime | None = None,
    overwrite: bool = False,
) -> dict[str, int]:
    output = Path(output_path)
    if output.exists() and not overwrite:
        raise FileExistsError(f"Backup already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)

    counts, documents = _capture_documents(database)
    payloads = {
        name: _canonical_documents(documents[name])
        for name in COGNITIVE_COLLECTIONS
    }
    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": _utc_timestamp(created_at),
        "source_database": _source_database_name(database),
        "collections": {
            name: {
                "path": _collection_path(name),
                "count": counts[name],
                "sha256": _sha256(payloads[name]),
            }
            for name in COGNITIVE_COLLECTIONS
        },
    }
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output.name}.",
        suffix=".tmp",
        dir=output.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr(MANIFEST_PATH, manifest_bytes)
            for name in COGNITIVE_COLLECTIONS:
                archive.writestr(_collection_path(name), payloads[name])
        verify_backup(temporary)
        os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(temporary, output)
    finally:
        temporary.unlink(missing_ok=True)
    return counts


def _read_backup(path: str | Path) -> tuple[dict[str, Any], DocumentsByCollection]:
    backup = Path(path)
    try:
        with ZipFile(backup, "r") as archive:
            names = archive.namelist()
            expected_names = {MANIFEST_PATH} | {
                _collection_path(name) for name in COGNITIVE_COLLECTIONS
            }
            if len(names) != len(set(names)) or set(names) != expected_names:
                raise RuntimeError("Backup archive has missing, extra, or duplicate files.")

            manifest = json.loads(archive.read(MANIFEST_PATH).decode("utf-8"))
            if not isinstance(manifest, dict):
                raise RuntimeError("Backup manifest must be a JSON object.")
            if manifest.get("format") != BACKUP_FORMAT:
                raise RuntimeError("Backup format is not recognized.")
            if manifest.get("version") != BACKUP_VERSION:
                raise RuntimeError("Backup version is not supported.")
            if not isinstance(manifest.get("created_at"), str):
                raise RuntimeError("Backup manifest is missing created_at.")
            if not isinstance(manifest.get("source_database"), str):
                raise RuntimeError("Backup manifest is missing source_database.")

            collection_specs = manifest.get("collections")
            if not isinstance(collection_specs, dict) or set(collection_specs) != set(
                COGNITIVE_COLLECTIONS
            ):
                raise RuntimeError("Backup manifest does not contain the cognitive collections.")

            documents: DocumentsByCollection = {}
            for name in COGNITIVE_COLLECTIONS:
                spec = collection_specs[name]
                expected_path = _collection_path(name)
                if not isinstance(spec, dict) or spec.get("path") != expected_path:
                    raise RuntimeError(f"Backup manifest path is invalid for {name!r}.")
                expected_count = spec.get("count")
                expected_hash = spec.get("sha256")
                if (
                    not isinstance(expected_count, int)
                    or isinstance(expected_count, bool)
                    or expected_count < 0
                ):
                    raise RuntimeError(f"Backup manifest count is invalid for {name!r}.")
                if not isinstance(expected_hash, str) or len(expected_hash) != 64:
                    raise RuntimeError(f"Backup manifest checksum is invalid for {name!r}.")

                payload = archive.read(expected_path)
                if not hmac.compare_digest(_sha256(payload), expected_hash):
                    raise RuntimeError(f"Backup checksum mismatch for {name!r}.")
                decoded = loads(payload.decode("utf-8"))
                if not isinstance(decoded, list) or any(
                    not isinstance(document, dict) for document in decoded
                ):
                    raise RuntimeError(f"Backup collection {name!r} is not a document list.")
                if len(decoded) != expected_count:
                    raise RuntimeError(f"Backup document count mismatch for {name!r}.")
                if any("_id" not in document for document in decoded):
                    raise RuntimeError(
                        f"Backup collection {name!r} contains a document without _id."
                    )
                documents[name] = decoded
    except (BadZipFile, KeyError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("Backup archive is unreadable or malformed.") from error

    if len(documents["mind"]) != 1:
        raise RuntimeError(
            "Backup must contain exactly one Mind document; "
            f"found {len(documents['mind'])}."
        )
    return manifest, documents


def verify_backup(path: str | Path) -> dict[str, int]:
    _manifest, documents = _read_backup(path)
    return {name: len(documents[name]) for name in COGNITIVE_COLLECTIONS}


def restore_backup(path: str | Path, target: Any) -> dict[str, int]:
    _manifest, documents = _read_backup(path)
    validate_empty_target(target)
    expected = {name: len(documents[name]) for name in COGNITIVE_COLLECTIONS}
    planned_ids = {
        name: [document["_id"] for document in documents[name]]
        for name in COGNITIVE_COLLECTIONS
    }

    try:
        for name in COGNITIVE_COLLECTIONS:
            if documents[name]:
                target[name].insert_many(documents[name], ordered=True)
        restored = {
            name: int(target[name].count_documents({}))
            for name in COGNITIVE_COLLECTIONS
        }
        if restored != expected:
            raise RuntimeError(
                f"Backup restore verification failed: expected={expected}, restored={restored}"
            )
    except Exception as error:
        rollback_errors: list[str] = []
        for name in COGNITIVE_COLLECTIONS:
            try:
                if planned_ids[name]:
                    target[name].delete_many({"_id": {"$in": planned_ids[name]}})
            except Exception as rollback_error:  # pragma: no cover - defensive database boundary
                rollback_errors.append(f"{name}: {rollback_error}")
        if rollback_errors:
            details = "; ".join(rollback_errors)
            raise RuntimeError(
                "Backup restore failed and rollback was incomplete; "
                f"inspect the target before retrying: {details}"
            ) from error
        raise
    return expected


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export, verify, or restore one canonical Cognitive Mind."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    export_parser = commands.add_parser("export", help="Create a portable backup archive.")
    export_parser.add_argument(
        "--uri",
        default=os.environ.get("SOURCE_MONGODB_URI") or os.environ.get("MONGODB_URI"),
        help="Source MongoDB URI (or SOURCE_MONGODB_URI / MONGODB_URI).",
    )
    export_parser.add_argument(
        "--database",
        default=(
            os.environ.get("SOURCE_MONGODB_DATABASE")
            or os.environ.get("MONGODB_DATABASE", "ai_cognitive_mind")
        ),
        help="Source database name.",
    )
    export_parser.add_argument("--output", required=True, help="Backup archive path.")
    export_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing backup at the output path.",
    )

    verify_parser = commands.add_parser("verify", help="Verify a backup without restoring it.")
    verify_parser.add_argument("--input", required=True, help="Backup archive path.")

    restore_parser = commands.add_parser("restore", help="Restore into an empty target database.")
    restore_parser.add_argument(
        "--uri",
        default=os.environ.get("TARGET_MONGODB_URI"),
        help="Target MongoDB URI (or TARGET_MONGODB_URI).",
    )
    restore_parser.add_argument(
        "--database",
        default=os.environ.get("TARGET_MONGODB_DATABASE", "ai_cognitive_mind"),
        help="Target database name.",
    )
    restore_parser.add_argument("--input", required=True, help="Backup archive path.")
    return parser


def _print_counts(label: str, counts: dict[str, int]) -> None:
    print(label)
    for name in COGNITIVE_COLLECTIONS:
        print(f"{name}: {counts[name]}")


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "verify":
        _print_counts("Canonical Mind backup verified.", verify_backup(args.input))
        return

    if not args.uri:
        variable = "SOURCE_MONGODB_URI" if args.command == "export" else "TARGET_MONGODB_URI"
        raise SystemExit(f"{variable} or --uri is required")

    client = MongoClient(args.uri)
    try:
        client.admin.command("ping")
        database = client[args.database]
        if args.command == "export":
            counts = create_backup(
                database,
                args.output,
                overwrite=args.overwrite,
            )
            _print_counts(f"Canonical Mind backup created: {args.output}", counts)
        else:
            counts = restore_backup(args.input, database)
            _print_counts("Canonical Mind backup restored.", counts)
    finally:
        client.close()


if __name__ == "__main__":
    main()
