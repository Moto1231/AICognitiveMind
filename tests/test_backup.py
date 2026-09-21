# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

import base64
import io
import json
import unittest
import zipfile
from datetime import UTC, datetime

from aicognitive_mind.backup import BACKUP_FORMAT, BACKUP_VERSION, build_backup_archive
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
    SensoryEvidenceArtifact,
)


class PortableBackupTests(unittest.TestCase):
    def test_archive_contains_cognitive_state_and_exact_evidence(self) -> None:
        created_at = datetime(2026, 9, 21, 13, 30, tzinfo=UTC)
        evidence_bytes = b"exact sensory bytes"
        evidence = SensoryEvidenceArtifact(
            captured_at=created_at,
            modality="audio",
            source="unity-microphone",
            media_type="audio/wav",
            sha256=(
                "769f49a0ee447c7da382f521376f6d74"
                "6d62b6cb2010d7143b4c2f3aa7e8d5fc"
            ),
            byte_length=len(evidence_bytes),
            payload_base64=base64.b64encode(evidence_bytes).decode("ascii"),
        )
        mind = CognitiveMind(
            identity=MindIdentity(
                self_name="Axiom",
                foundational_values=("Preserve continuity of identity",),
            )
        )
        journal = [
            JournalEntry(
                kind=JournalKind.INTERACTION,
                occurred_at=created_at,
                experience={"input": {"content": "hello"}},
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

        payload = build_backup_archive(
            mind=mind,
            journal=journal,
            memory=memory,
            diagnostics=diagnostics,
            evidence=[evidence],
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

            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["format"], BACKUP_FORMAT)
            self.assertEqual(manifest["version"], BACKUP_VERSION)
            self.assertEqual(manifest["storage_provider"], "surreal")
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
            self.assertNotIn("payload_base64", evidence_index[0])
            media_path = evidence_index[0]["archive_path"]
            self.assertIn(media_path, names)
            self.assertEqual(archive.read(media_path), evidence_bytes)

            mind_document = json.loads(archive.read("mind.json"))
            self.assertEqual(
                mind_document["identity"]["self_name"],
                "Axiom",
            )

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


if __name__ == "__main__":
    unittest.main()
