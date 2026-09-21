# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from __future__ import annotations

import base64
import binascii
import io
import json
import zipfile
from datetime import UTC, datetime
from typing import Any

from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    SensoryEvidenceArtifact,
)


BACKUP_FORMAT = "aicognitive-mind-backup"
BACKUP_VERSION = 1


def build_backup_archive(
    *,
    mind: CognitiveMind | None,
    journal: list[JournalEntry],
    memory: list[DurableMemory],
    diagnostics: list[DiagnosticObservation],
    evidence: list[SensoryEvidenceArtifact],
    storage_provider: str,
    created_at: datetime | None = None,
) -> bytes:
    timestamp = created_at or datetime.now(UTC)
    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": timestamp.isoformat(),
        "storage_provider": storage_provider,
        "contains_secrets": False,
        "counts": {
            "mind": 1 if mind is not None else 0,
            "journal": len(journal),
            "memory": len(memory),
            "diagnostics": len(diagnostics),
            "evidence": len(evidence),
        },
    }

    evidence_index: list[dict[str, Any]] = []
    buffer = io.BytesIO()

    with zipfile.ZipFile(
        buffer,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=6,
    ) as archive:
        _write_json(archive, "manifest.json", manifest)
        _write_json(
            archive,
            "mind.json",
            mind.model_dump(mode="json") if mind is not None else None,
        )
        _write_json(
            archive,
            "journal.json",
            [entry.model_dump(mode="json") for entry in journal],
        )
        _write_json(
            archive,
            "memory.json",
            [item.model_dump(mode="json") for item in memory],
        )
        _write_json(
            archive,
            "diagnostics.json",
            [item.model_dump(mode="json") for item in diagnostics],
        )

        for artifact in evidence:
            try:
                payload = base64.b64decode(
                    artifact.payload_base64,
                    validate=True,
                )
            except (binascii.Error, ValueError) as exc:
                raise ValueError(
                    "Sensory evidence payload is not valid base64: "
                    f"{artifact.sha256}"
                ) from exc

            extension = _extension_for_media_type(artifact.media_type)
            captured = artifact.captured_at.astimezone(UTC).strftime(
                "%Y%m%dT%H%M%S.%fZ"
            )
            filename = (
                f"evidence/media/{captured}_{artifact.sha256}.{extension}"
            )
            archive.writestr(filename, payload)

            document = artifact.model_dump(
                mode="json",
                exclude={"payload_base64"},
            )
            document["archive_path"] = filename
            evidence_index.append(document)

        _write_json(
            archive,
            "evidence/index.json",
            evidence_index,
        )
        archive.writestr(
            "RESTORE.txt",
            (
                "AICognitiveMind portable backup archive.\n"
                "This archive contains Mind identity, journal, durable memory, "
                "diagnostics, and exact sensory evidence media.\n"
                "It contains no application, database, or provider credentials.\n"
                "Do not place this archive in the public source repository.\n"
            ),
        )

    return buffer.getvalue()


def backup_filename(created_at: datetime | None = None) -> str:
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    return "axiom-mind-" + timestamp.strftime("%Y%m%dT%H%M%SZ") + ".zip"


def _write_json(
    archive: zipfile.ZipFile,
    path: str,
    value: Any,
) -> None:
    archive.writestr(
        path,
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ).encode("utf-8"),
    )


def _extension_for_media_type(media_type: str) -> str:
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
        "audio/mpeg": "mp3",
        "audio/mp4": "m4a",
    }.get(media_type.lower(), "bin")
