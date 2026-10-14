from __future__ import annotations

import base64
import binascii
import logging
from typing import Any
from urllib.parse import urlparse

import httpx

from aicognitive_mind.fish_audio import FishAudioError, FishAudioRenderer

from aicognitive_mind.provider_endpoints import ProviderEndpoint, ProviderEndpointRegistry
from aicognitive_mind.task_model_assignments import TaskKind, TaskModelAssignment, TaskModelAssignmentRegistry
from aicognitive_mind.task_behaviors import (
    TaskBehaviorRegistry,
    TaskExecutionContext,
    TaskPromptAssembler,
)


logger = logging.getLogger(__name__)


class TaskDispatchError(RuntimeError):
    """A selected task provider could not be resolved or did not complete the request."""


class TaskModelDispatcher:
    """Resolve saved task preferences and call the selected OpenAI-compatible endpoint.

    Provider/model choices are deliberately not capability-filtered. The selected
    endpoint's response, including errors, is authoritative.
    """

    def __init__(self, records: Any, *, timeout: float = 90.0, client: Any | None = None) -> None:
        self.assignments = TaskModelAssignmentRegistry(records)
        self.endpoints = ProviderEndpointRegistry(records)
        self.behaviors = TaskBehaviorRegistry(records)
        self.prompt_assembler = TaskPromptAssembler(self.behaviors)
        self.timeout = timeout
        self.client = client

    async def execute(self, context: TaskExecutionContext, payload: Any) -> Any:
        """Runtime-neutral entry point implemented by the stateless API adapter."""
        if not isinstance(payload, dict):
            raise TaskDispatchError("Task runtime payload must be an object.")
        operation = payload.get("operation")
        if operation == "chat":
            messages = payload.get("messages")
            if not isinstance(messages, list) or not all(isinstance(item, dict) for item in messages):
                raise TaskDispatchError("Chat runtime payload requires a messages list.")
            return await self.complete_chat(
                context.task, messages, temperature=payload.get("temperature"), context=context
            )
        if operation == "transcribe":
            filename = payload.get("filename")
            audio_bytes = payload.get("audio_bytes")
            media_type = payload.get("media_type")
            if not isinstance(filename, str) or not isinstance(audio_bytes, bytes) or not isinstance(media_type, str):
                raise TaskDispatchError("Transcription runtime payload requires filename, audio_bytes, and media_type.")
            return await self.transcribe(
                context.task, filename=filename, audio_bytes=audio_bytes,
                media_type=media_type, context=context,
            )
        if operation == "synthesize_voice":
            if context.task != "audio_voice":
                raise TaskDispatchError("Voice synthesis runtime operation requires the audio_voice task.")
            text = payload.get("text")
            speed = payload.get("speed", 1.0)
            volume = payload.get("volume", 0.0)
            if not isinstance(text, str) or not text.strip():
                raise TaskDispatchError("Voice synthesis runtime payload requires non-empty text.")
            if isinstance(speed, bool) or not isinstance(speed, (int, float)) or not 0.1 <= speed <= 10:
                raise TaskDispatchError("Voice synthesis speed must be between 0.1 and 10.")
            if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not -20 <= volume <= 0:
                raise TaskDispatchError("Voice synthesis volume must be between -20 and 0 dB.")
            return await self.synthesize_voice(text.strip(), speed=float(speed), volume=float(volume))
        raise TaskDispatchError("Unsupported task runtime operation.")

    async def assignment(self, task: TaskKind) -> TaskModelAssignment:
        return next(item for item in await self.assignments.list() if item.task == task)

    async def is_configured(self, task: TaskKind) -> bool:
        try:
            return bool(await self._candidate_assignments(task))
        except TaskDispatchError:
            return False

    async def _candidate_assignments(self, task: TaskKind) -> list[TaskModelAssignment]:
        """Return distinct, complete task-primary then task-fallback choices."""
        saved = await self.assignment(task)
        candidates: list[TaskModelAssignment] = []
        if saved.provider and saved.model:
            candidates.append(saved.model_copy(update={
                "fallbacks": [],
            }))
        for configured_fallback in saved.fallbacks:
            if not configured_fallback.provider or not configured_fallback.model:
                continue
            fallback = saved.model_copy(update={
                "provider": configured_fallback.provider,
                "model": configured_fallback.model,
                "fallbacks": [],
            })
            if not any(
                item.provider.casefold() == fallback.provider.casefold()
                and item.model.casefold() == fallback.model.casefold()
                for item in candidates
            ):
                candidates.append(fallback)
        if not candidates:
            raise TaskDispatchError(
                f"Task '{task}' has no complete provider/model assignment or fallback."
            )
        return candidates

    async def synthesize_voice(
        self, text: str, *, speed: float = 1.0, volume: float = 0.0
    ) -> bytes:
        """Synthesize speech using the configured Audio/Voice task fallback chain."""
        last_error: TaskDispatchError | None = None
        for assignment in await self._candidate_assignments("audio_voice"):
            try:
                assignment, endpoint = await self._resolve("audio_voice", assignment)
                renderer = FishAudioRenderer(
                    api_key=endpoint.api_key,
                    model=assignment.model,
                    reference_id=assignment.voice_reference_id or None,
                    endpoint_url=endpoint.base_url,
                )
                return await renderer.synthesize(text, speed=speed, volume=volume)
            except (TaskDispatchError, FishAudioError) as exc:
                last_error = exc if isinstance(exc, TaskDispatchError) else TaskDispatchError(str(exc))
                logger.warning(
                    "task_provider_fallback task=audio_voice provider=%s model=%s error=%s",
                    assignment.provider, assignment.model, exc,
                )
        if last_error is not None:
            raise last_error
        raise TaskDispatchError("Audio/Voice task has no configured provider/model assignment.")

    async def _resolve(
        self, task: TaskKind, assignment_override: TaskModelAssignment | None = None
    ) -> tuple[TaskModelAssignment, ProviderEndpoint]:
        assignment = assignment_override or await self.assignment(task)
        if not assignment.provider or not assignment.model:
            raise TaskDispatchError(
                f"Task '{task}' has an incomplete provider/model assignment."
            )
        endpoints = await self.endpoints.list()
        endpoint = next(
            (
                item for item in endpoints
                if assignment.provider.casefold() in {
                    item.id.casefold(), item.name.casefold(), item.base_url.casefold()
                }
            ),
            None,
        )
        if endpoint is None:
            raise TaskDispatchError(
                f"Provider endpoint '{assignment.provider}' for task '{task}' is not configured."
            )
        return assignment, endpoint

    @staticmethod
    def _url(endpoint: ProviderEndpoint, path: str) -> str:
        base = endpoint.base_url.rstrip("/")
        parsed = urlparse(base)
        prefix = parsed.path.rstrip("/")
        # Some saved endpoints were entered as a full operation URL instead of
        # an API base URL (for example, Eden AI /v3/audio/transcriptions).
        # Normalize known operation suffixes before appending the operation
        # selected by this dispatcher, so transcription does not become
        # /v3/audio/transcriptions/v1/audio/transcriptions.
        for suffix in (
            "/audio/transcriptions",
            "/audio/speech",
            "/chat/completions",
            "/models",
        ):
            if prefix.endswith(suffix):
                base = base[:-len(suffix)]
                parsed = urlparse(base)
                prefix = parsed.path.rstrip("/")
                break
        # Providers may expose an OpenAI-compatible API under /v1 or a
        # provider-specific API version such as Eden AI's /v3. Preserve an
        # explicit version prefix instead of incorrectly creating /v3/v1/....
        if prefix.endswith(("/v1", "/v3")):
            return base + "/" + path.lstrip("/")
        return base + "/v1/" + path.lstrip("/")

    @staticmethod
    def _headers(endpoint: ProviderEndpoint) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
        headers["Accept"] = "application/json"
        return headers

    async def _request(
        self,
        endpoint: ProviderEndpoint,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        data: dict[str, str] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
    ) -> dict[str, Any]:
        headers = self._headers(endpoint)
        request_url = self._url(endpoint, path)
        try:
            if self.client is not None:
                response = await self.client.request(
                    "POST", request_url, headers=headers,
                    json=json_body, data=data, files=files, timeout=self.timeout,
                )
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        request_url, headers=headers,
                        json=json_body, data=data, files=files,
                    )
        except httpx.HTTPError as exc:
            logger.exception(
                "task_provider_transport_error endpoint=%s url=%s operation=%s",
                endpoint.name, request_url, path,
            )
            raise TaskDispatchError(
                f"Provider endpoint '{endpoint.name}' could not complete {path}: {exc.__class__.__name__}"
            ) from exc
        if response.is_error:
            excerpt = response.text[:1200]
            logger.error(
                "task_provider_http_error endpoint=%s url=%s operation=%s status=%s response=%r",
                endpoint.name, request_url, path, response.status_code, excerpt,
            )
            raise TaskDispatchError(
                f"Provider endpoint '{endpoint.name}' returned HTTP {response.status_code}: {excerpt}"
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TaskDispatchError(
                f"Provider endpoint '{endpoint.name}' returned a non-JSON response."
            ) from exc
        if not isinstance(payload, dict):
            raise TaskDispatchError(f"Provider endpoint '{endpoint.name}' returned an unexpected response.")
        return payload

    async def interpret_percept(self, percept: Any, *, focus: str | None = None) -> str | None:
        """Interpret a sensory percept through its configured specialist assignment."""
        modality = getattr(getattr(percept, "modality", None), "value", "")
        if modality == "vision" and await self.is_configured("vision"):
            if not percept.content_ref:
                raise TaskDispatchError("Visual percept contains no image content.")
            prompt = (
                "Interpret this as direct visual sensory input for a persistent cognitive mind. "
                "Describe only what is reasonably observable. Do not invent identity, intent, or hidden facts."
                + (f" Re-examine the original evidence specifically for: {focus}" if focus else "")
            )
            result = await self.complete_chat(
                "vision",
                [{"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": percept.content_ref}},
                ]}],
            )
            return f"Visual perception: {result}"
        if modality == "audio" and await self.is_configured("audio"):
            data_url = percept.content_ref or ""
            if not data_url.startswith("data:") or "," not in data_url:
                raise TaskDispatchError("Audio percept does not contain a valid data URL.")
            header, encoded = data_url.split(",", 1)
            if not header.endswith(";base64"):
                raise TaskDispatchError("Audio percept does not contain base64 data.")
            media_type = header.removeprefix("data:").removesuffix(";base64").split(";", 1)[0].lower()
            try:
                audio_bytes = base64.b64decode(encoded, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise TaskDispatchError("Audio percept contains invalid base64 data.") from exc
            if not audio_bytes:
                raise TaskDispatchError("Audio percept is empty.")
            extension = {
                "audio/webm": "webm", "audio/ogg": "ogg", "audio/wav": "wav",
                "audio/x-wav": "wav", "audio/mp4": "mp4", "audio/mpeg": "mp3",
            }.get(media_type, "webm")
            result = await self.transcribe(
                "audio", filename=f"percept.{extension}",
                audio_bytes=audio_bytes, media_type=media_type,
            )
            return (
                f"Auditory perception: {result}\nEvidence review focus: {focus}"
                if focus else f"Auditory perception: {result}"
            )
        return None

    async def complete_chat(
        self,
        task: TaskKind,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
        context: TaskExecutionContext | None = None,
    ) -> str:
        last_error: TaskDispatchError | None = None
        for assignment in await self._candidate_assignments(task):
            try:
                return await self._complete_chat_with_assignment(
                    task, messages, assignment=assignment,
                    temperature=temperature, context=context,
                )
            except TaskDispatchError as exc:
                last_error = exc
                logger.warning(
                    "task_provider_fallback task=%s provider=%s model=%s error=%s",
                    task, assignment.provider, assignment.model, exc,
                )
        assert last_error is not None
        raise last_error

    async def _complete_chat_with_assignment(
        self,
        task: TaskKind,
        messages: list[dict[str, Any]],
        *,
        assignment: TaskModelAssignment,
        temperature: float | None = None,
        context: TaskExecutionContext | None = None,
    ) -> str:
        assignment, endpoint = await self._resolve(task, assignment)
        profile = next(item for item in await self.behaviors.list() if item.task == task)
        runtime_context = context or TaskExecutionContext(task=task)
        # The selected assignment always comes from Axiom's registry, not a caller's context.
        runtime_context = TaskExecutionContext(
            task=task,
            provider=assignment.provider,
            model=assignment.model,
            behavior_revision=profile.revision,
            session_id=runtime_context.session_id,
            state_ref=runtime_context.state_ref,
            memory_refs=runtime_context.memory_refs,
            working_context=runtime_context.working_context,
        )
        system_prompt = await self.prompt_assembler.system_prompt(runtime_context)
        caller_system = [
            str(message.get("content", ""))
            for message in messages
            if message.get("role") == "system" and message.get("content")
        ]
        if caller_system:
            system_prompt += "\n\nADDITIONAL CALLER INSTRUCTIONS:\n" + "\n".join(caller_system)
        request_messages = [
            {"role": "system", "content": system_prompt},
            *[message for message in messages if message.get("role") != "system"],
        ]
        body: dict[str, Any] = {"model": assignment.model, "messages": request_messages}
        if temperature is not None:
            body["temperature"] = temperature
        payload = await self._request(endpoint, "chat/completions", json_body=body)
        try:
            content = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise TaskDispatchError(
                f"Provider endpoint '{endpoint.name}' response has no chat completion content."
            ) from exc
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            text = "\n".join(
                str(part["text"]) for part in content
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ).strip()
            if text:
                return text
        raise TaskDispatchError(f"Provider endpoint '{endpoint.name}' returned empty completion content.")

    async def transcribe(
        self,
        task: TaskKind,
        *,
        filename: str,
        audio_bytes: bytes,
        media_type: str,
        context: TaskExecutionContext | None = None,
    ) -> str:
        last_error: TaskDispatchError | None = None
        for assignment in await self._candidate_assignments(task):
            try:
                return await self._transcribe_with_assignment(
                    task, assignment=assignment, filename=filename,
                    audio_bytes=audio_bytes, media_type=media_type, context=context,
                )
            except TaskDispatchError as exc:
                last_error = exc
                logger.warning(
                    "task_provider_fallback task=%s provider=%s model=%s error=%s",
                    task, assignment.provider, assignment.model, exc,
                )
        assert last_error is not None
        raise last_error

    async def _transcribe_with_assignment(
        self,
        task: TaskKind,
        *,
        assignment: TaskModelAssignment,
        filename: str,
        audio_bytes: bytes,
        media_type: str,
        context: TaskExecutionContext | None = None,
    ) -> str:
        assignment, endpoint = await self._resolve(task, assignment)
        profile = next(item for item in await self.behaviors.list() if item.task == task)
        runtime_context = context or TaskExecutionContext(task=task)
        runtime_context = TaskExecutionContext(
            task=task,
            provider=assignment.provider,
            model=assignment.model,
            behavior_revision=profile.revision,
            session_id=runtime_context.session_id,
            state_ref=runtime_context.state_ref,
            memory_refs=runtime_context.memory_refs,
            working_context=runtime_context.working_context,
        )
        # OpenAI-compatible transcription APIs accept an optional prompt. It is
        # the audio task's layered behavior, not an assumption that transcription
        # endpoints support chat-style system messages.
        transcription_prompt = await self.prompt_assembler.system_prompt(runtime_context)
        payload = await self._request(
            endpoint,
            "audio/transcriptions",
            data={"model": assignment.model, "prompt": transcription_prompt},
            files={"file": (filename, audio_bytes, media_type)},
        )
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise TaskDispatchError(
                f"Provider endpoint '{endpoint.name}' returned no transcription text."
            )
        return text.strip()
