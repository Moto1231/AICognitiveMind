from __future__ import annotations

import unittest
from datetime import UTC, datetime
from pathlib import Path

from aicognitive_mind.api import app
from aicognitive_mind.domain import SensoryEvidenceArtifact
from aicognitive_mind.storage import InMemoryEvidenceStore


class SensoryEvidenceAdministrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_exact_artifact_can_be_erased_without_touching_other_artifacts(self) -> None:
        store = InMemoryEvidenceStore()
        captured_at = datetime(2026, 10, 11, 18, 4, 45, tzinfo=UTC)
        first = SensoryEvidenceArtifact(
            captured_at=captured_at,
            modality="audio",
            source="browser-microphone",
            media_type="audio/webm",
            sha256="a" * 64,
            byte_length=4,
            payload_base64="dGVzdA==",
        )
        second = first.model_copy(update={"sha256": "b" * 64})
        await store.preserve(first)
        await store.preserve(second)

        self.assertTrue(await store.delete_exact(sha256=first.sha256, captured_at=captured_at))
        self.assertFalse(await store.delete_exact(sha256=first.sha256, captured_at=captured_at))
        remaining = await store.read()
        self.assertEqual([artifact.sha256 for artifact in remaining], [second.sha256])

    async def test_admin_evidence_routes_and_viewer_are_present(self) -> None:
        paths = {
            (getattr(route, "path", None), method)
            for route in app.routes
            for method in getattr(route, "methods", set())
        }
        self.assertIn(("/v1/portal/evidence", "GET"), paths)
        self.assertIn(("/v1/portal/evidence/{sha256}", "DELETE"), paths)

        markup = Path("src/aicognitive_mind/static/index.html").read_text(encoding="utf-8")
        script = Path("src/aicognitive_mind/static/portal.js").read_text(encoding="utf-8")
        self.assertNotIn('data-admin-section="evidence"', markup)
        self.assertNotIn('id="evidenceList"', markup)
        self.assertIn('id="journalEvidenceDetail"', markup)
        self.assertIn('id="deviceInventoryList"', markup)
        self.assertIn('data-admin-section="devices"', markup)
        self.assertIn("audio.controls = true", script)
        self.assertIn("preview.src = mediaUrl", script)
        self.assertIn("Erase Evidence", script)
        self.assertIn("Permanently erase the media bytes for this journal record?", script)
        self.assertIn("navigator.mediaDevices.enumerateDevices()", script)
        self.assertIn('el.taskProfileOverview.classList.add("hidden")', script)
        self.assertIn('el.taskProfileOverview.classList.remove("hidden")', script)


if __name__ == "__main__":
    unittest.main()
