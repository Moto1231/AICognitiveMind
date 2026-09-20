from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aicognitive_mind.body import Percept, SensoryModality
from aicognitive_mind.domain import CognitiveActor, JournalEntry, JournalKind
from aicognitive_mind.storage import EvidenceStore, JournalStore


class EvidenceReviewCall(BaseModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: datetime
    focus: str = Field(min_length=1, max_length=1000)


class SensoryEvidenceReviewTool:
    """Lets conscious reasoning deliberately re-examine preserved sensory evidence."""

    name = "sensory_evidence_review"
    description = (
        "Retrieve an exact preserved sensory evidence artifact by SHA-256 and capture time, "
        "verify its integrity, and reinterpret the original media for a specific review focus. "
        "Use this when recalled interpretation is uncertain, contradicted, or needs closer inspection. "
        "The original evidence is never modified."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "sha256": {
                "type": "string",
                "pattern": "^[0-9a-f]{64}$",
                "description": "SHA-256 from the preserved sensory evidence reference.",
            },
            "captured_at": {
                "type": "string",
                "format": "date-time",
                "description": "Exact capture timestamp from the evidence reference.",
            },
            "focus": {
                "type": "string",
                "minLength": 1,
                "maxLength": 1000,
                "description": (
                    "Specific question or detail to re-examine in the original sensory evidence."
                ),
            },
        },
        "required": ["sha256", "captured_at", "focus"],
        "additionalProperties": False,
    }

    def __init__(
        self,
        *,
        evidence: EvidenceStore,
        journal: JournalStore,
        interpreter: Any,
    ) -> None:
        self._evidence = evidence
        self._journal = journal
        self._interpreter = interpreter

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        call = EvidenceReviewCall.model_validate(arguments)
        artifact = await self._evidence.find_exact(
            sha256=call.sha256,
            captured_at=call.captured_at,
        )
        if artifact is None:
            return {
                "found": False,
                "sha256": call.sha256,
                "captured_at": call.captured_at.isoformat(),
                "focus": call.focus,
            }

        try:
            payload = base64.b64decode(artifact.payload_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("Stored sensory evidence cannot be decoded") from exc

        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != artifact.sha256:
            raise RuntimeError("Stored sensory evidence failed SHA-256 integrity verification")
        if len(payload) != artifact.byte_length:
            raise RuntimeError("Stored sensory evidence failed byte-length integrity verification")

        try:
            modality = SensoryModality(artifact.modality)
        except ValueError as exc:
            raise RuntimeError(
                f"Unsupported stored sensory modality: {artifact.modality}"
            ) from exc

        percept = Percept(
            modality=modality,
            observed_at=artifact.captured_at,
            source=artifact.source,
            summary="Preserved sensory evidence under deliberate review.",
            content_ref=(
                f"data:{artifact.media_type};base64,{artifact.payload_base64}"
            ),
            metadata={
                **artifact.metadata,
                "evidence_review": True,
                "evidence_sha256": artifact.sha256,
            },
        )

        interpretation = await self._interpreter.interpret(percept, focus=call.focus)
        reference = artifact.reference()

        await self._journal.append(
            JournalEntry(
                kind=JournalKind.EVIDENCE_REVIEW,
                experience={
                    "status": "reviewed",
                    "focus": call.focus,
                    "evidence": reference.model_dump(mode="python"),
                    "integrity_verified": True,
                    "interpretation": interpretation,
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )

        return {
            "found": True,
            "integrity_verified": True,
            "focus": call.focus,
            "evidence": reference.model_dump(mode="json"),
            "interpretation": interpretation,
        }
