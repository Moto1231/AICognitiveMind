# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from __future__ import annotations

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
    JournalKind,
    SensoryEvidenceReference,
)


BACKUP_FORMAT = "aicognitive-mind-backup"
BACKUP_VERSION = 2


def evidence_references_from_journal(
    journal: list[JournalEntry],
) -> list[SensoryEvidenceReference]:
    """Return admitted sensory evidence references without loading media bytes."""

    unique: dict[tuple[str, datetime], SensoryEvidenceReference] = {}
    for entry in journal:
        if entry.kind != JournalKind.SENSORY_EVIDENCE:
            continue
        document = entry.experience.get("evidence")
        if not isinstance(document, dict):
            continue
        reference = SensoryEvidenceReference.model_validate(document)
        unique[(reference.sha256, reference.captured_at)] = reference

    return sorted(
        unique.values(),
        key=lambda reference: reference.captured_at,
    )


def build_backup_archive(
    *,
    mind: CognitiveMind | None,
    journal: list[JournalEntry],
    memory: list[DurableMemory],
    diagnostics: list[DiagnosticObservation],
    evidence: list[SensoryEvidenceReference],
    storage_provider: str,
    created_at: datetime | None = None,
) -> bytes:
    """Build the small cognitive/index portion of a portable backup.

    Exact sensory media is deliberately transferred separately, one artifact at
    a time, so the running Mind never has to materialize every image/audio
    payload in Render memory at once.
    """

    timestamp = created_at or datetime.now(UTC)
    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": timestamp.isoformat(),
        "storage_provider": storage_provider,
        "contains_secrets": False,
        "evidence_media_transfer": "separate_verified_download",
        "counts": {
            "mind": 1 if mind is not None else 0,
            "journal": len(journal),
            "memory": len(memory),
            "diagnostics": len(diagnostics),
            "evidence": len(evidence),
        },
    }

    evidence_index: list[dict[str, Any]] = []
    for reference in evidence:
        captured = reference.captured_at.astimezone(UTC).strftime(
            "%Y%m%dT%H%M%S.%fZ"
        )
        extension = _extension_for_media_type(reference.media_type)
        document = reference.model_dump(mode="json")
        document["archive_path"] = (
            f"media/{captured}_{reference.sha256}.{extension}"
        )
        evidence_index.append(document)

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
        _write_json(
            archive,
            "evidence/index.json",
            evidence_index,
        )
        archive.writestr(
            "RESTORE.txt",
            (
                "Axiom portable backup cognitive snapshot.\n"
                "This archive contains Mind identity, journal, durable memory, "
                "diagnostics, and the sensory-evidence index.\n"
                "Exact evidence media is stored in the companion "
                "axiom-evidence.zip created by the backup script.\n"
                "No application, database, or provider credentials are included.\n"
                "Do not place backup archives in the public source repository.\n"
            ),
        )

    return buffer.getvalue()


def backup_filename(created_at: datetime | None = None) -> str:
    timestamp = (created_at or datetime.now(UTC)).astimezone(UTC)
    return "axiom-" + timestamp.strftime("%Y%m%dT%H%M%SZ") + ".zip"


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
