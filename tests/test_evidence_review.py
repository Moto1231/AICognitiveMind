import base64
import hashlib
import unittest
from datetime import UTC, datetime

from aicognitive_mind.domain import (
    CognitiveMind,
    JournalEntry,
    JournalKind,
    MindIdentity,
    SensoryEvidenceArtifact,
)
from aicognitive_mind.evidence_review import SensoryEvidenceReviewTool
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.storage import (
    InMemoryEvidenceStore,
    InMemoryJournalStore,
    InMemoryMemoryStore,
)


class FocusedInterpreter:
    def __init__(self) -> None:
        self.calls = []

    async def interpret(self, percept, *, focus=None):
        self.calls.append((percept, focus))
        return f"Reviewed for {focus}: original media re-examined."


class SensoryEvidenceReviewV01Tests(unittest.IsolatedAsyncioTestCase):
    async def test_review_reopens_exact_artifact_and_journals_new_interpretation(self) -> None:
        evidence = InMemoryEvidenceStore()
        journal = InMemoryJournalStore()
        interpreter = FocusedInterpreter()
        captured_at = datetime(2026, 9, 20, 3, 45, tzinfo=UTC)
        payload = b"visual-evidence"
        sha256 = hashlib.sha256(payload).hexdigest()
        artifact = SensoryEvidenceArtifact(
            captured_at=captured_at,
            modality="vision",
            source="browser-camera",
            media_type="image/jpeg",
            sha256=sha256,
            byte_length=len(payload),
            payload_base64=base64.b64encode(payload).decode("ascii"),
            metadata={"width": 640, "height": 480},
        )
        await evidence.preserve(artifact)
        tool = SensoryEvidenceReviewTool(
            evidence=evidence,
            journal=journal,
            interpreter=interpreter,
        )

        result = await tool.invoke(
            {
                "sha256": sha256,
                "captured_at": captured_at.isoformat(),
                "focus": "Read the date on the sign.",
            }
        )

        self.assertTrue(result["found"])
        self.assertTrue(result["integrity_verified"])
        self.assertEqual(result["evidence"]["sha256"], sha256)
        self.assertIn("Read the date on the sign.", result["interpretation"])

        self.assertEqual(len(interpreter.calls), 1)
        percept, focus = interpreter.calls[0]
        self.assertEqual(focus, "Read the date on the sign.")
        self.assertEqual(percept.observed_at, captured_at)
        self.assertEqual(percept.source, "browser-camera")
        self.assertEqual(percept.content_ref, f"data:image/jpeg;base64,{artifact.payload_base64}")

        entries = await journal.read()
        self.assertEqual(len(entries), 1)
        review = entries[0]
        self.assertEqual(review.kind, JournalKind.EVIDENCE_REVIEW)
        self.assertEqual(review.experience["evidence"]["sha256"], sha256)
        self.assertTrue(review.experience["integrity_verified"])
        self.assertNotIn("payload_base64", str(review.experience))

    async def test_review_refuses_corrupted_content_addressed_evidence(self) -> None:
        evidence = InMemoryEvidenceStore()
        journal = InMemoryJournalStore()
        artifact = SensoryEvidenceArtifact(
            captured_at=datetime(2026, 9, 20, 3, 50, tzinfo=UTC),
            modality="audio",
            source="browser-microphone",
            media_type="audio/webm",
            sha256="a" * 64,
            byte_length=5,
            payload_base64=base64.b64encode(b"audio").decode("ascii"),
        )
        await evidence.preserve(artifact)
        tool = SensoryEvidenceReviewTool(
            evidence=evidence,
            journal=journal,
            interpreter=FocusedInterpreter(),
        )

        with self.assertRaisesRegex(RuntimeError, "SHA-256 integrity"):
            await tool.invoke(
                {
                    "sha256": artifact.sha256,
                    "captured_at": artifact.captured_at.isoformat(),
                    "focus": "Check the spoken weekday.",
                }
            )

        self.assertEqual(await journal.read(), [])

    async def test_review_returns_not_found_without_inventing_evidence(self) -> None:
        journal = InMemoryJournalStore()
        tool = SensoryEvidenceReviewTool(
            evidence=InMemoryEvidenceStore(),
            journal=journal,
            interpreter=FocusedInterpreter(),
        )
        captured_at = datetime(2026, 9, 20, 4, 0, tzinfo=UTC)

        result = await tool.invoke(
            {
                "sha256": "b" * 64,
                "captured_at": captured_at.isoformat(),
                "focus": "Check the original observation.",
            }
        )

        self.assertFalse(result["found"])
        self.assertEqual(await journal.read(), [])

    async def test_memory_recall_carries_exact_sensory_evidence_reference(self) -> None:
        captured_at = datetime(2026, 9, 20, 4, 5, tzinfo=UTC)
        sha256 = "c" * 64
        journal = InMemoryJournalStore()
        await journal.append(
            JournalEntry(
                kind=JournalKind.SENSORY_EVIDENCE,
                occurred_at=captured_at,
                experience={
                    "status": "admitted",
                    "source": "body:vision",
                    "evidence": {
                        "sha256": sha256,
                        "captured_at": captured_at,
                        "modality": "vision",
                        "source": "browser-camera",
                        "media_type": "image/jpeg",
                        "byte_length": 1234,
                    },
                    "metadata": {"width": 640, "height": 480},
                },
            ),
            recorded_by="conscious_workspace",
        )
        steward = MemoryStewardTool(
            mind=CognitiveMind(identity=MindIdentity(self_name="AICognitiveMind")),
            input_text="What did the camera actually see?",
            memory=InMemoryMemoryStore(),
            journal=journal,
        )

        result = await steward.invoke(
            {"action": "recall", "focus": "camera vision evidence"}
        )

        experiences = result["context"]["prior_experience"]
        self.assertEqual(len(experiences), 1)
        references = experiences[0]["evidence_references"]
        self.assertEqual(len(references), 1)
        self.assertEqual(references[0]["sha256"], sha256)
        self.assertEqual(
            references[0]["captured_at"],
            captured_at.isoformat().replace("+00:00", "Z"),
        )


if __name__ == "__main__":
    unittest.main()
