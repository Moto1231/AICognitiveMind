from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator


class ProviderEndpoint(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    base_url: str = Field(min_length=8, max_length=1000)
    api_key: str = Field(default="", max_length=4096)
    models: list[str] = Field(default_factory=list, max_length=2000)
    model_capabilities: dict[str, list[str]] = Field(default_factory=dict, max_length=2000)

    @field_validator("id", "name", "base_url", "api_key")
    @classmethod
    def strip_values(cls, value: str) -> str:
        return value.strip()

    @field_validator("base_url")
    @classmethod
    def require_http_endpoint(cls, value: str) -> str:
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Endpoint URL must be an absolute HTTP(S) URL")
        return value.rstrip("/")

    @field_validator("models")
    @classmethod
    def clean_models(cls, values: list[str]) -> list[str]:
        return list(dict.fromkeys(value.strip() for value in values if value.strip()))


class ProviderEndpointRegistry:
    RECORD_KEY = "provider_endpoints"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[ProviderEndpoint]:
        record = await self.records.get(self.RECORD_KEY)
        if not record:
            return []
        return [ProviderEndpoint.model_validate(value) for value in record.get("items", [])]

    async def replace(self, endpoints: list[ProviderEndpoint]) -> list[ProviderEndpoint]:
        by_id = {item.id: item for item in endpoints}
        if len(by_id) != len(endpoints):
            raise ValueError("Endpoint IDs must be unique")
        ordered = list(by_id.values())
        after = {"items": [item.model_dump(mode="json") for item in ordered]}
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("Provider endpoints changed concurrently; refresh and retry")
        return ordered


def _reported_capabilities(entry: dict[str, Any]) -> list[str]:
    """Extract only capabilities explicitly reported by a model-listing API."""
    values: list[str] = []
    for key in ("capabilities", "modalities", "input_modalities", "output_modalities"):
        raw = entry.get(key)
        if isinstance(raw, list):
            values.extend(value.strip().lower() for value in raw if isinstance(value, str) and value.strip())
        elif isinstance(raw, str) and raw.strip():
            values.append(raw.strip().lower())
    architecture = entry.get("architecture")
    if isinstance(architecture, dict):
        raw = architecture.get("input_modalities")
        if isinstance(raw, list):
            values.extend(value.strip().lower() for value in raw if isinstance(value, str) and value.strip())
    aliases = {
        "image": "Vision", "vision": "Vision", "video": "Video",
        "audio": "Audio", "text": "Text", "embedding": "Embeddings",
    }
    labels = []
    for value in values:
        label = aliases.get(value, value.replace("_", " ").title())
        if label not in labels:
            labels.append(label)
    return labels


async def discover_endpoint_model_details(endpoint: ProviderEndpoint) -> dict[str, Any]:
    """Return model IDs and any capabilities explicitly reported by the provider."""
    url = endpoint.base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
    async with httpx.AsyncClient(timeout=20.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 404 and not endpoint.base_url.endswith("/v1"):
            response = await client.get(endpoint.base_url.rstrip("/") + "/v1/models", headers=headers)
        response.raise_for_status()
        payload = response.json()

    entries = payload.get("data", payload.get("models", [])) if isinstance(payload, dict) else []
    models: list[str] = []
    capabilities: dict[str, list[str]] = {}
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, str):
                model_id = entry
            elif isinstance(entry, dict):
                model_id = entry.get("id") or entry.get("name") or entry.get("model")
            else:
                model_id = None
            if isinstance(model_id, str) and model_id.strip():
                model_id = model_id.strip()
                if model_id not in models:
                    models.append(model_id)
                if isinstance(entry, dict):
                    reported = _reported_capabilities(entry)
                    if reported:
                        capabilities[model_id] = reported
    return {"models": models, "model_capabilities": capabilities}


async def discover_endpoint_models(endpoint: ProviderEndpoint) -> list[str]:
    """Query an OpenAI-compatible model listing endpoint and return the IDs it reports."""
    details = await discover_endpoint_model_details(endpoint)
    return details["models"]
