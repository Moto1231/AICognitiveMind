import base64
import hashlib
import unittest
from types import SimpleNamespace

from aicognitive_mind.domain import SensoryEvidenceArtifact
from aicognitive_mind.mcp_server import body_request_tool_result, next_body_interaction, read_sensory_evidence
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


    async def test_next_body_interaction_delivers_live_audio_as_native_content(self):
        payload = b"live spoken words"
        data_url = "data:audio/webm;base64," + base64.b64encode(payload).decode()
        class Hosts:
            async def next_request(self, _token):
                return {
                    "request_id": "request-1",
                    "user_message": "Listen and respond to the speaker.",
                    "context": {"status": "ready_to_reason"},
                    "media_data_url": data_url,
                }
        ctx = SimpleNamespace(request_context=SimpleNamespace(
            lifespan_context=SimpleNamespace(hosts=Hosts())))
        result = await next_body_interaction("lease", ctx)
        self.assertEqual(result.content[1].type, "audio")
        self.assertEqual(result.content[1].mime_type, "audio/webm")
        self.assertEqual(base64.b64decode(result.content[1].data), payload)
        self.assertNotIn("media_data_url", result.structured_content)


    def test_body_request_tool_result_preserves_audio_as_native_content(self):
        payload = b"spoken words"
        data_url = "data:audio/webm;base64," + base64.b64encode(payload).decode()
        result = body_request_tool_result({
            "request_id": "request-2",
            "user_message": "Listen to the speaker.",
            "media_data_url": data_url,
        })
        self.assertEqual(result.content[1].type, "audio")
        self.assertEqual(result.content[1].mime_type, "audio/webm")
        self.assertEqual(base64.b64decode(result.content[1].data), payload)
        self.assertNotIn("media_data_url", result.structured_content)
