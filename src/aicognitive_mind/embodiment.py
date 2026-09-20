from __future__ import annotations

import base64
import binascii
import hashlib
from datetime import datetime
from typing import Any, Protocol

from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from pydantic import BaseModel

from aicognitive_mind.body import BodyRuntime, Percept, SensoryModality
from aicognitive_mind.core import CognitiveCore
from aicognitive_mind.domain import (
    CognitiveActor,
    InteractionResult,
    JournalEntry,
    JournalKind,
    SensoryEvidenceArtifact,
    SensoryEvidenceReference,
)
from aicognitive_mind.storage import EvidenceStore, JournalStore


class PerceptInterpreter(Protocol):
    async def interpret(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str: ...


class EmbodiedInteractionResult(BaseModel):
    sensory_modality: SensoryModality
    sensory_source: str
    evidence: SensoryEvidenceReference
    interpretation: str
    response_text: str
    occurred_at: datetime


class SummaryPerceptInterpreter:
    """Fallback interpreter used when no multimodal reasoning service is configured."""

    async def interpret(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        summary = (percept.summary or "Uninterpreted sensory observation.").strip()
        focus_suffix = f" Review focus: {focus}" if focus else ""
        return (
            f"Body {percept.modality.value} perception from {percept.source}: "
            f"{summary}{focus_suffix}"
        )


class OpenAIPerceptInterpreter:
    """Mind-side sensory interpreter.

    Vision is interpreted as an image input. Audio is transcribed before it is
    handed to the conscious workspace. The admitted source media is preserved
    separately as immutable sensory evidence before interpretation.
    """

    def __init__(
        self,
        api_key: str,
        *,
        vision_model: str,
        transcription_model: str = "gpt-4o-transcribe",
        client: Any | None = None,
    ) -> None:
        self._client = client or AsyncOpenAI(api_key=api_key)
        self._vision_model = vision_model
        self._transcription_model = transcription_model

    async def interpret(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        if percept.modality == SensoryModality.VISION:
            return await self._interpret_vision(percept, focus=focus)
        if percept.modality == SensoryModality.AUDIO:
            return await self._interpret_audio(percept, focus=focus)

        summary = (percept.summary or "Uninterpreted sensory observation.").strip()
        return (
            f"Body {percept.modality.value} perception from {percept.source}: "
            f"{summary}"
        )

    async def _interpret_vision(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        if not percept.content_ref:
            raise ValueError("Visual percept contains no image content")

        response = await self._client.responses.create(
            model=self._vision_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Interpret this as direct visual sensory input for a persistent "
                                "cognitive mind. Describe only what is reasonably observable. "
                                "Do not invent identity, intent, or hidden facts."
                                + (
                                    f" Re-examine the original evidence specifically for: {focus}"
                                    if focus
                                    else ""
                                )
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": percept.content_ref,
                            "detail": "auto",
                        },
                    ],
                }
            ],
        )
        text = (response.output_text or "").strip()
        if not text:
            raise RuntimeError("Vision interpreter returned no description")
        return f"Visual perception: {text}"

    async def _interpret_audio(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        if not percept.content_ref:
            raise ValueError("Audio percept contains no audio content")

        media_type, audio_bytes = self._decode_audio(percept.content_ref)
        filename = self._audio_filename(media_type)
        transcription = await self._client.audio.transcriptions.create(
            model=self._transcription_model,
            file=(filename, audio_bytes, media_type),
        )
        text = (getattr(transcription, "text", "") or "").strip()
        if not text:
            raise RuntimeError("Audio interpreter returned no transcription")
        if focus:
            return (
                f"Auditory perception: {text}\n"
                f"Evidence review focus: {focus}"
            )
        return f"Auditory perception: {text}"

    @staticmethod
    def _decode_audio(data_url: str) -> tuple[str, bytes]:
        if not data_url.startswith("data:") or "," not in data_url:
            raise ValueError("Audio percept does not contain a valid data URL")
        header, encoded = data_url.split(",", 1)
        if not header.endswith(";base64"):
            raise ValueError("Audio percept does not contain base64 data")
        descriptor = header.removeprefix("data:").removesuffix(";base64")
        media_type = descriptor.split(";", 1)[0].lower()
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Audio percept contains invalid base64 data") from exc
        if not payload:
            raise ValueError("Audio percept is empty")
        return media_type, payload

    @staticmethod
    def _audio_filename(media_type: str) -> str:
        extension_by_type = {
            "audio/webm": "webm",
            "audio/ogg": "ogg",
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mp4": "mp4",
            "audio/mpeg": "mp3",
        }
        extension = extension_by_type.get(media_type, "webm")
        return f"percept.{extension}"


class GeminiPerceptInterpreter:
    """Gemini-backed Mind-side interpretation for preserved visual and audio evidence."""

    def __init__(
        self,
        api_key: str,
        *,
        model: str = "gemini-3.5-flash",
        client: Any | None = None,
    ) -> None:
        self._client = client or genai.Client(api_key=api_key)
        self._model = model

    async def interpret(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        if percept.modality == SensoryModality.VISION:
            return await self._interpret_vision(percept, focus=focus)
        if percept.modality == SensoryModality.AUDIO:
            return await self._interpret_audio(percept, focus=focus)

        summary = (percept.summary or "Uninterpreted sensory observation.").strip()
        return (
            f"Body {percept.modality.value} perception from {percept.source}: "
            f"{summary}"
        )

    async def _interpret_vision(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        media_type, payload = self._decode_data_url(
            percept.content_ref,
            expected_prefix="image/",
            label="Visual",
        )
        prompt = (
            "Interpret this as direct visual sensory input for a persistent cognitive mind. "
            "Describe only what is reasonably observable. "
            "Do not invent identity, intent, or hidden facts."
        )
        if focus:
            prompt += f" Re-examine the original evidence specifically for: {focus}"

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                genai_types.Part.from_bytes(data=payload, mime_type=media_type),
                prompt,
            ],
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini vision interpreter returned no description")
        return f"Visual perception: {text}"

    async def _interpret_audio(
        self,
        percept: Percept,
        *,
        focus: str | None = None,
    ) -> str:
        media_type, payload = self._decode_data_url(
            percept.content_ref,
            expected_prefix="audio/",
            label="Audio",
        )
        prompt = (
            "Interpret this as direct auditory sensory input for a persistent cognitive mind. "
            "Transcribe spoken words faithfully and briefly note materially relevant non-speech "
            "sounds. Do not invent speakers, intent, or hidden facts."
        )
        if focus:
            prompt += f" Re-examine the original evidence specifically for: {focus}"

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                genai_types.Part.from_bytes(data=payload, mime_type=media_type),
                prompt,
            ],
        )
        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini audio interpreter returned no interpretation")
        return f"Auditory perception: {text}"

    @staticmethod
    def _decode_data_url(
        data_url: str | None,
        *,
        expected_prefix: str,
        label: str,
    ) -> tuple[str, bytes]:
        if not data_url or not data_url.startswith("data:") or "," not in data_url:
            raise ValueError(f"{label} percept does not contain a valid data URL")
        header, encoded = data_url.split(",", 1)
        if not header.endswith(";base64"):
            raise ValueError(f"{label} percept does not contain base64 data")
        descriptor = header.removeprefix("data:").removesuffix(";base64")
        media_type = descriptor.split(";", 1)[0].lower()
        if not media_type.startswith(expected_prefix):
            raise ValueError(f"{label} percept contains an unexpected media type")
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError(f"{label} percept contains invalid base64 data") from exc
        if not payload:
            raise ValueError(f"{label} percept is empty")
        return media_type, payload


class MindBodyBridge:
    """Connects transient Body perception to the persistent Cognitive Mind."""

    def __init__(
        self,
        *,
        core: CognitiveCore,
        body: BodyRuntime,
        interpreter: PerceptInterpreter,
        evidence: EvidenceStore,
        journal: JournalStore,
    ) -> None:
        self._core = core
        self._body = body
        self._interpreter = interpreter
        self._evidence = evidence
        self._journal = journal

    async def see(self, *, express: bool = True) -> EmbodiedInteractionResult:
        return await self.perceive(await self._body.see(), express=express)

    async def hear(self, *, express: bool = True) -> EmbodiedInteractionResult:
        return await self.perceive(await self._body.hear(), express=express)

    async def interact(
        self,
        message: str,
        *,
        express: bool = True,
    ) -> InteractionResult:
        interaction = await self._core.interact(
            message,
            source="human",
            input_context={"interface": "body:live:text"},
        )
        if express:
            await self._body.express(interaction.response_text)
        return interaction

    async def perceive(
        self,
        percept: Percept,
        *,
        express: bool = True,
    ) -> EmbodiedInteractionResult:
        artifact = await self._preserve_evidence(percept)
        reference = artifact.reference()
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.SENSORY_EVIDENCE,
                occurred_at=percept.observed_at,
                experience={
                    "status": "admitted",
                    "source": f"body:{percept.modality.value}",
                    "evidence": reference.model_dump(mode="python"),
                    "metadata": self._journal_safe_metadata(percept.metadata),
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        interpretation = await self._interpreter.interpret(percept)
        context = {
            "modality": percept.modality.value,
            "source": percept.source,
            "observed_at": percept.observed_at.isoformat(),
            "evidence": reference.model_dump(mode="json"),
            "metadata": self._journal_safe_metadata(percept.metadata),
        }
        interaction = await self._core.interact(
            interpretation,
            source=f"body:{percept.modality.value}",
            input_context=context,
        )
        if express:
            await self._body.express(interaction.response_text)

        return EmbodiedInteractionResult(
            sensory_modality=percept.modality,
            sensory_source=percept.source,
            evidence=reference,
            interpretation=interpretation,
            response_text=interaction.response_text,
            occurred_at=interaction.occurred_at,
        )

    async def _preserve_evidence(self, percept: Percept) -> SensoryEvidenceArtifact:
        if not percept.content_ref:
            raise ValueError("Sensory percept contains no evidence content")

        media_type, payload_base64, payload = self._decode_data_url(percept.content_ref)
        artifact = SensoryEvidenceArtifact(
            captured_at=percept.observed_at,
            modality=percept.modality.value,
            source=percept.source,
            media_type=media_type,
            sha256=hashlib.sha256(payload).hexdigest(),
            byte_length=len(payload),
            payload_base64=payload_base64,
            metadata=self._journal_safe_metadata(percept.metadata),
        )
        return await self._evidence.preserve(artifact)

    @staticmethod
    def _decode_data_url(data_url: str) -> tuple[str, str, bytes]:
        if not data_url.startswith("data:") or "," not in data_url:
            raise ValueError("Sensory evidence does not contain a valid data URL")
        header, encoded = data_url.split(",", 1)
        if not header.endswith(";base64"):
            raise ValueError("Sensory evidence does not contain base64 data")
        descriptor = header.removeprefix("data:").removesuffix(";base64")
        media_type = descriptor.split(";", 1)[0].lower()
        try:
            payload = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("Sensory evidence contains invalid base64 data") from exc
        if not payload:
            raise ValueError("Sensory evidence is empty")
        return media_type, encoded, payload

    @staticmethod
    def _journal_safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        # Preserve provenance and physical characteristics, never raw media.
        return {
            key: value
            for key, value in metadata.items()
            if key not in {"content_ref", "data", "audio_data", "image_data"}
        }
