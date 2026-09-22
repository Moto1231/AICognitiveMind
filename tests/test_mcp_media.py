import base64
import hashlib
import unittest
from types import SimpleNamespace

from aicognitive_mind.domain import SensoryEvidenceArtifact
from aicognitive_mind.mcp_server import read_sensory_evidence
from aicognitive_mind.storage import InMemoryEvidenceStore


class McpMediaTests(unittest.IsolatedAsyncioTestCase):
    async def test_original_media_returns_native_content_and_rejects_corruption(self):
        evidence = InMemoryEvidenceStore()
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(storage=SimpleNamespace(evidence=evidence))))
        for modality, media_type, content_type in (
            ("vision", "image/jpeg", "image"), ("audio", "audio/wav", "audio")
        ):
            payload = modality.encode()
            artifact = SensoryEvidenceArtifact(
                modality=modality, source="test", media_type=media_type,
                sha256=hashlib.sha256(payload).hexdigest(), byte_length=len(payload),
                payload_base64=base64.b64encode(payload).decode(),
            )
            await evidence.preserve(artifact)
            result = await read_sensory_evidence(
                artifact.sha256, artifact.captured_at.isoformat(), ctx)
            self.assertEqual(result.content[1].type, content_type)
            self.assertEqual(base64.b64decode(result.content[1].data), payload)
            self.assertTrue(result.structured_content["integrity_verified"])
        corrupted = artifact.model_copy(update={
            "sha256": "0" * 64, "payload_base64": base64.b64encode(b"changed").decode()})
        await evidence.preserve(corrupted)
        with self.assertRaisesRegex(ValueError, "integrity"):
            await read_sensory_evidence(
                corrupted.sha256, corrupted.captured_at.isoformat(), ctx)
