# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

import io
import json
import unittest
import zipfile
from datetime import UTC, datetime

from aicognitive_mind.backup import (
    BACKUP_FORMAT,
    BACKUP_VERSION,
    build_backup_archive,
    evidence_references_from_journal,
)
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
    SensoryEvidenceReference,
)


class PortableBackupTests(unittest.TestCase):
    def test_archive_contains_cognitive_state_and_evidence_index(self) -> None:
        created_at = datetime(2026, 9, 21, 13, 30, tzinfo=UTC)
        evidence = SensoryEvidenceReference(
            captured_at=created_at,
            modality="audio",
            source="unity-microphone",
            media_type="audio/wav",
            sha256=(
                "769f49a0ee447c7da382f521376f6d74"
                "6d62b6cb2010d7143b4c2f3aa7e8d5fc"
            ),
            byte_length=1234,
        )
        mind = CognitiveMind(
            identity=MindIdentity(
                self_name="Axiom",
                foundational_values=("Preserve continuity of identity",),
            )
        )
        journal = [
            JournalEntry(
                kind=JournalKind.SENSORY_EVIDENCE,
                occurred_at=created_at,
                experience={
                    "status": "admitted",
                    "source": "body:audio",
                    "evidence": evidence.model_dump(mode="python"),
                },
            )
        ]
        memory = [
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                formed_at=created_at,
                content="A durable fact.",
                grounding=("test",),
            )
        ]
        diagnostics = [
            DiagnosticObservation(
                observed_at=created_at,
                component="test",
                operation="backup",
                implementation={"name": "unit-test"},
            )
        ]

        references = evidence_references_from_journal(journal)
        self.assertEqual(references, [evidence])

        payload = build_backup_archive(
            mind=mind,
            journal=journal,
            memory=memory,
            diagnostics=diagnostics,
            evidence=references,
            storage_provider="surreal",
            created_at=created_at,
        )

        with zipfile.ZipFile(io.BytesIO(payload), "r") as archive:
            names = set(archive.namelist())
            self.assertIn("manifest.json", names)
            self.assertIn("mind.json", names)
            self.assertIn("journal.json", names)
            self.assertIn("memory.json", names)
            self.assertIn("diagnostics.json", names)
            self.assertIn("evidence/index.json", names)
            self.assertIn("RESTORE.txt", names)
            self.assertFalse(
                any(name.startswith("evidence/media/") for name in names)
            )

            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["format"], BACKUP_FORMAT)
            self.assertEqual(manifest["version"], BACKUP_VERSION)
            self.assertEqual(manifest["storage_provider"], "surreal")
            self.assertEqual(
                manifest["evidence_media_transfer"],
                "separate_verified_download",
            )
            self.assertFalse(manifest["contains_secrets"])
            self.assertEqual(
                manifest["counts"],
                {
                    "mind": 1,
                    "journal": 1,
                    "memory": 1,
                    "diagnostics": 1,
                    "evidence": 1,
                },
            )

            evidence_index = json.loads(
                archive.read("evidence/index.json")
            )
            self.assertEqual(len(evidence_index), 1)
            self.assertEqual(
                evidence_index[0]["sha256"],
                evidence.sha256,
            )
            self.assertEqual(
                evidence_index[0]["byte_length"],
                evidence.byte_length,
            )
            self.assertTrue(
                evidence_index[0]["archive_path"].startswith("media/")
            )

            mind_document = json.loads(archive.read("mind.json"))
            self.assertEqual(
                mind_document["identity"]["self_name"],
                "Axiom",
            )

    def test_evidence_index_deduplicates_repeated_journal_reference(self) -> None:
        captured_at = datetime(2026, 9, 21, 13, 30, tzinfo=UTC)
        reference = SensoryEvidenceReference(
            captured_at=captured_at,
            modality="vision",
            source="unity-camera",
            media_type="image/jpeg",
            sha256="a" * 64,
            byte_length=42,
        )
        entries = [
            JournalEntry(
                kind=JournalKind.SENSORY_EVIDENCE,
                occurred_at=captured_at,
                experience={
                    "evidence": reference.model_dump(mode="python")
                },
            ),
            JournalEntry(
                kind=JournalKind.SENSORY_EVIDENCE,
                occurred_at=captured_at,
                experience={
                    "evidence": reference.model_dump(mode="python")
                },
            ),
        ]

        self.assertEqual(
            evidence_references_from_journal(entries),
            [reference],
        )

    def test_admin_backup_endpoint_is_governed_and_does_not_bulk_read_media(self) -> None:
        api = open(
            "src/aicognitive_mind/api.py",
            encoding="utf-8",
        ).read()
        route_start = api.index('@app.get("/v1/admin/backup"')
        route_end = api.index('@app.get("/v1/admin/status"', route_start)
        route = api[route_start:route_end]

        self.assertIn("require_admin(request)", route)
        self.assertIn("build_backup_archive", route)
        self.assertIn("evidence_references_from_journal", route)
        self.assertNotIn("evidence_store.read()", route)
        self.assertIn('"Cache-Control": "private, no-store"', route)

    def test_archive_does_not_contain_provider_credentials(self) -> None:
        payload = build_backup_archive(
            mind=None,
            journal=[],
            memory=[],
            diagnostics=[],
            evidence=[],
            storage_provider="surreal",
            created_at=datetime(2026, 9, 21, 13, 30, tzinfo=UTC),
        )

        text = payload.decode("latin-1")
        self.assertNotIn("SURREALDB_PASSWORD", text)
        self.assertNotIn("GEMINI_API_KEY", text)
        self.assertNotIn("APP_ACCESS_PASSWORD", text)

    def test_windows_script_verifies_each_evidence_artifact(self) -> None:
        script = open(
            "scripts/backup-axiom.ps1",
            encoding="utf-8",
        ).read()

        self.assertIn("Downloading sensory evidence one artifact at a time", script)
        self.assertIn("/v1/evidence/", script)
        self.assertIn("byte-length verification failed", script)
        self.assertIn("SHA-256 verification failed", script)
        self.assertIn("axiom-evidence.zip", script)


if __name__ == "__main__":
    unittest.main()
