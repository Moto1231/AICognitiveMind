from __future__ import annotations

import base64
from typing import Any
from urllib.parse import urlparse

import httpx

from aicognitive_mind.provider_endpoints import ProviderEndpoint, ProviderEndpointRegistry
from aicognitive_mind.task_model_assignments import TaskKind, TaskModelAssignment, TaskModelAssignmentRegistry


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
        self.timeout = timeout
        self.client = client

    async def assignment(self, task: TaskKind) -> TaskModelAssignment:
        return next(item for item in await self.assignments.list() if item.task == task)

    async def is_configured(self, task: TaskKind) -> bool:
        assignment = await self.assignment(task)
        return bool(assignment.provider or assignment.model)

    async def _resolve(self, task: TaskKind) -> tuple[TaskModelAssignment, ProviderEndpoint]:
        assignment = await self.assignment(task)
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
        if prefix.endswith("/v1"):
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
        if self.client is not None:
            response = await self.client.request(
                "POST", self._url(endpoint, path), headers=headers,
                json=json_body, data=data, files=files, timeout=self.timeout,
            )
        else:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self._url(endpoint, path), headers=headers,
                    json=json_body, data=data, files=files,
                )
        if response.is_error:
            excerpt = response.text[:1200]
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

    async def complete_chat(
        self,
        task: TaskKind,
        messages: list[dict[str, Any]],
        *,
        temperature: float | None = None,
    ) -> str:
        assignment, endpoint = await self._resolve(task)
        body: dict[str, Any] = {"model": assignment.model, "messages": messages}
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
    ) -> str:
        assignment, endpoint = await self._resolve(task)
        payload = await self._request(
            endpoint,
            "audio/transcriptions",
            data={"model": assignment.model},
            files={"file": (filename, audio_bytes, media_type)},
        )
        text = payload.get("text")
        if not isinstance(text, str) or not text.strip():
            raise TaskDispatchError(
                f"Provider endpoint '{endpoint.name}' returned no transcription text."
            )
        return text.strip()
