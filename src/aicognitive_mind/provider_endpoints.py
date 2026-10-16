from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator


class ProviderEndpoint(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    provider_name: str = Field(default="", max_length=120)
    base_url: str = Field(min_length=8, max_length=1000)
    api_key: str = Field(default="", max_length=4096)
    model: str = Field(default="", max_length=160)
    models: list[str] = Field(default_factory=list, max_length=2000)
    model_capabilities: dict[str, list[str]] = Field(default_factory=dict, max_length=2000)
    model_capability_sources: dict[str, str] = Field(default_factory=dict, max_length=2000)

    @field_validator("id", "name", "provider_name", "base_url", "api_key", "model")
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
        elif isinstance(raw, dict):
            values.extend(str(name).lower() for name, enabled in raw.items() if enabled is True)
    architecture = entry.get("architecture")
    if isinstance(architecture, dict):
        for key in ("input_modalities", "output_modalities"):
            raw = architecture.get(key)
            if isinstance(raw, list):
                values.extend(value.strip().lower() for value in raw if isinstance(value, str) and value.strip())
    # LiteLLM and other compatible gateways expose feature flags rather than a
    # modalities array. A false flag must never be presented as a capability.
    for container in (entry, entry.get("model_info"), entry.get("metadata")):
        if not isinstance(container, dict):
            continue
        for key, label in {
            "supports_vision": "vision", "supports_audio_input": "audio",
            "supports_audio_output": "audio", "supports_function_calling": "tools",
            "supports_tool_calling": "tools", "supports_response_schema": "structured_outputs",
        }.items():
            if container.get(key) is True:
                values.append(label)
    aliases = {
        "image": "Vision", "vision": "Vision", "video": "Video",
        "audio": "Audio", "text": "Text", "embedding": "Embeddings",
        "embeddings": "Embeddings", "function_calling": "Tools", "tools": "Tools",
        "completion": "Text", "chat": "Text",
    }
    labels = []
    for value in values:
        label = aliases.get(value, value.replace("_", " ").title())
        if label not in labels:
            labels.append(label)
    return labels


# OpenAI's /models response contains identity/ownership, not modalities:
# https://developers.openai.com/api/reference/resources/models/methods/retrieve
# This deliberately finite catalog supplements that response with documented
# modalities (checked 2026-10-16). It is not a live capability or key-access test.
# Never infer a third-party compatible server's features from a model-like name.
_OPENAI_DOCUMENTED_MODELS = {
    model_id: (["Text", "Vision"], f"https://developers.openai.com/api/docs/models/{model_id}")
    for model_id in (
        "gpt-6-astra", "gpt-6-sol", "gpt-6.1-sol", "gpt-6-luna",
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5",
    )
}


def _documented_capabilities(endpoint: ProviderEndpoint, model_id: str) -> tuple[list[str], str]:
    hostname = urlparse(endpoint.base_url).hostname or ""
    if hostname != "api.openai.com" and not hostname.endswith(".api.openai.com"):
        return [], ""
    documented = _OPENAI_DOCUMENTED_MODELS.get(model_id)
    if documented is None:
        # Only strip a conventional dated snapshot suffix, not arbitrary model
        # suffixes such as -audio, -realtime or a provider-specific variant.
        import re

        alias = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_id)
        documented = _OPENAI_DOCUMENTED_MODELS.get(alias)
    return documented if documented else ([], "")


async def discover_endpoint_model_details(endpoint: ProviderEndpoint) -> dict[str, Any]:
    """Return model IDs and any capabilities explicitly reported by the provider."""
    url = endpoint.base_url.rstrip("/") + "/models"
    headers = {"Authorization": f"Bearer {endpoint.api_key}"} if endpoint.api_key else {}
    async with httpx.AsyncClient(timeout=20.0) as client:
        # The configured base URL is authoritative. Do not silently rewrite it
        # by adding /v1: providers may use /v3, custom paths, or root-level APIs.
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        payload = response.json()

    entries = payload.get("data", payload.get("models", [])) if isinstance(payload, dict) else []
    models: list[str] = []
    capabilities: dict[str, list[str]] = {}
    sources: dict[str, str] = {}
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
                reported = _reported_capabilities(entry) if isinstance(entry, dict) else []
                if reported:
                    capabilities[model_id] = reported
                    sources[model_id] = "provider_metadata"
                else:
                    documented, source = _documented_capabilities(endpoint, model_id)
                    if documented:
                        capabilities[model_id] = documented
                        sources[model_id] = source
    return {
        "models": models,
        "model_capabilities": capabilities,
        "model_capability_sources": sources,
    }


async def discover_endpoint_models(endpoint: ProviderEndpoint) -> list[str]:
    """Query an OpenAI-compatible model listing endpoint and return the IDs it reports."""
    details = await discover_endpoint_model_details(endpoint)
    return details["models"]
