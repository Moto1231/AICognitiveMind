from __future__ import annotations

import base64
import binascii
import hashlib
import math
from copy import deepcopy
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
from aicognitive_mind.presence_resolver import PresenceResolver
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
        self.task_dispatcher: Any | None = None

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

        dispatcher = self.task_dispatcher
        if dispatcher is not None and await dispatcher.is_configured("vision"):
            prompt = (
                "Interpret this as direct visual sensory input for a persistent cognitive mind. "
                "Describe only what is reasonably observable. Do not invent identity, intent, or hidden facts."
                + (f" Re-examine the original evidence specifically for: {focus}" if focus else "")
            )
            text = await dispatcher.complete_chat(
                "vision",
                [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": percept.content_ref}},
                ]}],
            )
            return f"Visual perception: {text}"

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
        dispatcher = self.task_dispatcher
        if dispatcher is not None and await dispatcher.is_configured("audio"):
            text = await dispatcher.transcribe(
                "audio", filename=filename, audio_bytes=audio_bytes, media_type=media_type
            )
            return (
                f"Auditory perception: {text}\nEvidence review focus: {focus}"
                if focus else f"Auditory perception: {text}"
            )

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
        self.task_dispatcher: Any | None = None

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

        dispatcher = self.task_dispatcher
        if dispatcher is not None and await dispatcher.is_configured("vision"):
            text = await dispatcher.complete_chat(
                "vision",
                [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": percept.content_ref}},
                ]}],
            )
            return f"Visual perception: {text}"

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

        dispatcher = self.task_dispatcher
        if dispatcher is not None and await dispatcher.is_configured("audio"):
            text = await dispatcher.transcribe(
                "audio", filename="percept.webm", audio_bytes=payload, media_type=media_type
            )
            return (
                f"Auditory perception: {text}\nEvidence review focus: {focus}"
                if focus else f"Auditory perception: {text}"
            )

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
        presence: PresenceResolver | None = None,
    ) -> None:
        self._core = core
        self._body = body
        self._interpreter = interpreter
        self._evidence = evidence
        self._journal = journal
        self._presence = presence

    async def see(
        self,
        *,
        express: bool = True,
        presence_scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> EmbodiedInteractionResult:
        return await self.perceive(
            await self._body.see(), express=express, presence_scope=presence_scope
        )

    async def hear(
        self,
        *,
        express: bool = True,
        presence_scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> EmbodiedInteractionResult:
        return await self.perceive(
            await self._body.hear(), express=express, presence_scope=presence_scope
        )

    async def interact(
        self,
        message: str,
        *,
        express: bool = True,
        presence_scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> InteractionResult:
        interaction = await self._core.interact(
            message,
            source="human",
            input_context=self._with_presence_context(
                {"interface": "body:live:text"}, scope=presence_scope
            ),
        )
        if express:
            await self._body.express(interaction.response_text)
        return interaction

    async def perceive(
        self,
        percept: Percept,
        *,
        express: bool = True,
        automatic: bool = False,
        conversation: bool = False,
        presence_scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> EmbodiedInteractionResult:
        if conversation and percept.modality != SensoryModality.AUDIO:
            raise ValueError("Spoken conversation requires audio evidence")
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
        # The saved artifact is authoritative. Give host workers a usable locator
        # even when large inline media is omitted from their text handoff.
        interpretation_percept = percept.model_copy(update={
            "metadata": {**percept.metadata, "evidence": reference.model_dump(mode="json")},
        })
        automatic_interpreter = getattr(self._interpreter, "interpret_automatically", None)
        spoken_interpreter = getattr(self._interpreter, "interpret_spoken_automatically", None)
        derived_audio = None
        if conversation and spoken_interpreter is not None:
            spoken = await spoken_interpreter(interpretation_percept)
            interpretation = spoken["interpretation"]
            derived_audio = spoken.get("derived_audio")
        elif automatic:
            if automatic_interpreter is None:
                raise RuntimeError("Automatic sensory interpretation is not supported by the configured interpreter.")
            interpretation = await automatic_interpreter(interpretation_percept)
        else:
            interpretation = await self._interpreter.interpret(interpretation_percept)
        await self._journal.append(
            JournalEntry(
                kind=JournalKind.SENSORY_EVIDENCE,
                occurred_at=percept.observed_at,
                experience={
                    "status": "interpreted",
                    "source": f"body:{percept.modality.value}",
                    "evidence": reference.model_dump(mode="python"),
                    "interpretation": interpretation,
                    "metadata": self._journal_safe_metadata(percept.metadata),
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        self._admit_presence_observation(
            percept=percept,
            evidence=reference,
            interpretation=interpretation,
            scope=presence_scope,
        )
        context = {
            "modality": percept.modality.value,
            "source": percept.source,
            "observed_at": percept.observed_at.isoformat(),
            "evidence": reference.model_dump(mode="json"),
            "metadata": self._journal_safe_metadata(percept.metadata),
        }
        transcript = self._supported_spoken_transcript(derived_audio, reference) if conversation else None
        if transcript:
            # The browser explicitly requested a spoken turn. Preserve the fact
            # that its words are derived evidence, without inventing a speaker.
            context.update({
                "intentional_conversation": True,
                "derived_audio": deepcopy(derived_audio),
                "transcription_status": "derived_not_independently_verified",
                "speaker_identity": "unresolved",
                "addressee_identity": "unresolved",
            })
            interaction = await self._core.interact(
                transcript,
                source="body:audio",
                input_context=self._with_presence_context(context, scope=presence_scope),
            )
            if interaction.response_text.strip():
                await self._body.express(interaction.response_text)
            return EmbodiedInteractionResult(
                sensory_modality=percept.modality, sensory_source=percept.source,
                evidence=reference, interpretation=interpretation,
                response_text=interaction.response_text, occurred_at=interaction.occurred_at,
            )
        # Passive sensory admission (used by continuous sensing) stops here.
        # The Body supplies perception; the Mind records and interprets it, but
        # does not enter a full conscious interaction for every observation.
        if not express or conversation:
            return EmbodiedInteractionResult(
                sensory_modality=percept.modality,
                sensory_source=percept.source,
                evidence=reference,
                interpretation=interpretation,
                response_text="",
                occurred_at=percept.observed_at,
            )

        interaction = await self._core.interact(
            interpretation,
            source=f"body:{percept.modality.value}",
            input_context=self._with_presence_context(context, scope=presence_scope),
        )
        await self._body.express(interaction.response_text)

        return EmbodiedInteractionResult(
            sensory_modality=percept.modality,
            sensory_source=percept.source,
            evidence=reference,
            interpretation=interpretation,
            response_text=interaction.response_text,
            occurred_at=interaction.occurred_at,
        )

    @staticmethod
    def _supported_spoken_transcript(
        derived: Any, evidence: SensoryEvidenceReference,
    ) -> str | None:
        if derived is None:
            return None
        if not isinstance(derived, dict) or derived.get("source") not in {"local_asr", "configured_asr"}:
            raise ValueError("Spoken input requires a supported derived transcription")
        if not isinstance(derived.get("model"), str) or not derived["model"].strip():
            raise ValueError("Spoken transcription must identify its model or configured task")
        try:
            captured_at = datetime.fromisoformat(derived["captured_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError, AttributeError) as exc:
            raise ValueError("Spoken transcription has an invalid capture time") from exc
        if derived.get("sha256") != evidence.sha256 or captured_at != evidence.captured_at:
            raise ValueError("Spoken transcription does not match its preserved audio")
        transcript = derived.get("transcript")
        if not isinstance(transcript, str) or len(transcript) > 16_000:
            raise ValueError("Spoken transcription text is invalid")
        transcript = transcript.strip()
        if not transcript:
            return None
        segments = derived.get("segments", [])
        if not isinstance(segments, list):
            raise ValueError("Spoken transcription segments are invalid")
        for segment in segments:
            if not isinstance(segment, dict):
                raise ValueError("Spoken transcription segment is invalid")
            for key, threshold, high_is_bad in (
                ("no_speech_probability", 0.6, True), ("avg_logprob", -1.0, False),
            ):
                value = segment.get(key)
                if value is None:
                    continue  # A provider may omit scores; never invent them.
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Spoken transcription quality metadata is invalid")
                if (high_is_bad and value >= threshold) or (not high_is_bad and value < threshold):
                    return None
        return transcript

    def _admit_presence_observation(
        self,
        *,
        percept: Percept,
        evidence: SensoryEvidenceReference,
        interpretation: str,
        scope: tuple[str, str],
    ) -> None:
        if self._presence is None:
            return
        text = interpretation.casefold()
        if percept.modality == SensoryModality.VISION:
            person_cues = (" person", " people", " man", " woman", " child", " human")
        elif percept.modality == SensoryModality.AUDIO:
            person_cues = (" speaker", " speaking", " speech", " voice", " says ", " said ")
        else:
            return
        if not any(cue in f" {text}" for cue in person_cues):
            return
        presence_key = f"{percept.modality.value}:{percept.source}"
        self._presence.observe(
            presence_key,
            evidence=evidence,
            observation=interpretation,
            scope=scope,
        )

    def _with_presence_context(
        self,
        context: dict[str, Any],
        *,
        scope: tuple[str, str] = ("legacy", "legacy"),
    ) -> dict[str, Any]:
        if self._presence is None:
            return context
        presence_context = self._presence.context(scope=scope)
        if not presence_context["present_people"]:
            return context
        return {**context, "presence": presence_context}

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
