from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field, field_validator

from aicognitive_mind.commit import CommitConflict


class ProviderEndpointRevisionConflict(ValueError):
    """A provider catalog save used a stale or concurrently changed revision."""


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
    model_capability_exclusions: dict[str, list[str]] = Field(default_factory=dict, max_length=2000)

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
        return (await self.snapshot())[0]

    async def snapshot(self) -> tuple[list[ProviderEndpoint], int]:
        record = await self.records.get(self.RECORD_KEY)
        if not record:
            return [], 0
        return ([ProviderEndpoint.model_validate(value) for value in record.get("items", [])],
                record.get("revision", 0))

    async def replace(
        self, endpoints: list[ProviderEndpoint], *, expected_revision: int | None = None,
    ) -> list[ProviderEndpoint]:
        if expected_revision is not None and (type(expected_revision) is not int or expected_revision < 0):
            raise ValueError("expected_revision must be a nonnegative integer")
        by_id = {item.id: item for item in endpoints}
        if len(by_id) != len(endpoints):
            raise ValueError("Endpoint IDs must be unique")
        ordered = list(by_id.values())
        before = await self.records.get(self.RECORD_KEY)
        revision = (before or {}).get("revision", 0)
        if expected_revision is not None and expected_revision != revision:
            raise ProviderEndpointRevisionConflict("Provider endpoints changed; refresh before saving.")
        after = {"items": [item.model_dump(mode="json") for item in ordered], "revision": revision + 1}
        if before is None:
            try:
                await self.records.create(self.RECORD_KEY, after)
            except Exception as exc:
                if await self.records.get(self.RECORD_KEY) is not None:
                    raise ProviderEndpointRevisionConflict("Provider endpoints changed; refresh before saving.") from exc
                raise
        else:
            try:
                replaced = await self.records.replace(self.RECORD_KEY, before, after)
            except CommitConflict as exc:
                raise ProviderEndpointRevisionConflict("Provider endpoints changed; refresh before saving.") from exc
            if not replaced:
                raise ProviderEndpointRevisionConflict("Provider endpoints changed; refresh before saving.")
        return ordered


_CAPABILITY_ALIASES = {
    "image": "Vision", "vision": "Vision", "video": "Video",
    "audio": "Audio", "text": "Text", "embedding": "Embeddings",
    "embeddings": "Embeddings", "function_calling": "Tools", "tool_calling": "Tools",
    "tools": "Tools", "tool_choice": "Tools", "tool_use": "Tools",
    "completion": "Text", "chat": "Text", "completion_chat": "Text",
    "text_generation": "Text", "structured_outputs": "Structured Outputs",
    "response_schema": "Structured Outputs", "json_schema": "Structured Outputs",
    "audio_input": "Audio Input", "audio_output": "Audio Output",
    "speech_to_text": "Audio Input", "text_to_speech": "Audio Output",
    "transcription": "Audio Input", "tts": "Audio Output",
    "supports_vision": "Vision", "supports_audio_input": "Audio Input",
    "supports_audio_output": "Audio Output", "supports_function_calling": "Tools",
    "supports_tool_calling": "Tools", "supports_response_schema": "Structured Outputs",
    "supports_structured_outputs": "Structured Outputs", "supports_reasoning": "Reasoning",
}


def _capability_label(value: str) -> str:
    normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
    return _CAPABILITY_ALIASES.get(normalized, normalized.replace("_", " ").title())


def _negative_labels(value: str) -> list[str]:
    label = _capability_label(value)
    if label == "Audio":
        return ["Audio", "Audio Input", "Audio Output"]
    if value.strip().lower() == "text":
        return ["Text", "Text Input"]
    return [label]


def _metadata_capabilities(entry: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Read reported features, retaining explicit negatives for later enrichment."""
    values: list[str] = []
    excluded: list[str] = []
    raw_capabilities = entry.get("capabilities")
    if isinstance(raw_capabilities, dict):
        for name, enabled in raw_capabilities.items():
            if enabled is True:
                values.append(_capability_label(str(name)))
            elif enabled is False:
                excluded.extend(_negative_labels(str(name)))
    elif isinstance(raw_capabilities, list):
        values.extend(_capability_label(value) for value in raw_capabilities if isinstance(value, str) and value.strip())
    elif isinstance(raw_capabilities, str) and raw_capabilities.strip():
        values.append(_capability_label(raw_capabilities))

    raw_modalities = entry.get("modalities")
    if isinstance(raw_modalities, dict):
        for name, enabled in raw_modalities.items():
            if enabled is True:
                values.append(_capability_label(str(name)))
            elif enabled is False:
                excluded.extend(_negative_labels(str(name)))
    elif isinstance(raw_modalities, list):
        values.extend(_capability_label(value) for value in raw_modalities if isinstance(value, str) and value.strip())
    elif isinstance(raw_modalities, str) and raw_modalities.strip():
        values.append(_capability_label(raw_modalities))

    architecture = entry.get("architecture")
    modality_containers = [entry, architecture] if isinstance(architecture, dict) else [entry]
    outputs = [value.strip().lower() for container in modality_containers
               for value in (container.get("output_modalities")
                             if isinstance(container.get("output_modalities"), list) else [])
               if isinstance(value, str)]
    for container in modality_containers:
        for direction in ("input", "output"):
            raw = container.get(direction + "_modalities")
            if not isinstance(raw, list):
                continue
            for value in raw:
                if not isinstance(value, str) or not value.strip():
                    continue
                normalized = value.strip().lower()
                if normalized == "text":
                    label = "Text Input" if direction == "input" and outputs and "text" not in outputs else "Text"
                elif normalized == "audio":
                    label = "Audio Input" if direction == "input" else "Audio Output"
                elif normalized in {"image", "vision"}:
                    label = "Vision" if direction == "input" else "Image Output"
                elif normalized == "video":
                    label = "Video Input" if direction == "input" else "Video Output"
                else:
                    label = _capability_label(normalized)
                values.append(label)

    # OpenRouter lists accepted parameters separately from modalities. A plain
    # response_format parameter is not proof of JSON-schema structured output.
    parameters = entry.get("supported_parameters")
    if isinstance(parameters, list):
        names = {str(value).strip().lower() for value in parameters if isinstance(value, str)}
        if names & {"tools", "tool_choice"}:
            values.append("Tools")
        if "structured_outputs" in names:
            values.append("Structured Outputs")

    # Explicit provider classifications and gateway feature flags are evidence;
    # a model's spelling or generateContent method alone is not.
    kind = entry.get("type")
    if isinstance(kind, str) and kind in {"chat", "text", "embedding", "embeddings", "tts", "text-to-speech", "speech-to-text"}:
        values.append(_capability_label(kind))
    flags = [key for key in _CAPABILITY_ALIASES if key.startswith("supports_")]
    for container in (entry, entry.get("model_info"), entry.get("metadata")):
        if not isinstance(container, dict):
            continue
        for name in flags:
            if container.get(name) is True:
                values.append(_capability_label(name))
            elif container.get(name) is False:
                excluded.extend(_negative_labels(name))
    blocked = set(excluded)
    return list(dict.fromkeys(value for value in values if value not in blocked)), list(dict.fromkeys(excluded))


def _reported_capabilities(entry: dict[str, Any]) -> list[str]:
    """Extract only capabilities explicitly reported by a model-listing API."""
    return _metadata_capabilities(entry)[0]


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
        from aicognitive_mind.model_capability_catalog import documented_capabilities

        return documented_capabilities(endpoint, model_id)
    documented = _OPENAI_DOCUMENTED_MODELS.get(model_id)
    if documented is None:
        # Only strip a conventional dated snapshot suffix, not arbitrary model
        # suffixes such as -audio, -realtime or a provider-specific variant.
        import re

        alias = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_id)
        documented = _OPENAI_DOCUMENTED_MODELS.get(alias)
    return documented if documented else ([], "")


def _merge_capabilities(
    reported: list[str], documented: list[str], excluded: list[str], source: str,
) -> tuple[list[str], str]:
    blocked = {_capability_label(value) for value in excluded}
    published = [_capability_label(value) for value in documented]
    legacy_directions = (
        {"Text": "Text Input", "Audio": "Audio Output"}
        if "Text Input" in published and "Audio Output" in published and "Text" not in published else {}
    )
    # Earlier discovery flattened input/output modalities into generic labels.
    # The finite catalog can disambiguate those cached labels for an exact,
    # documented audio-only TTS model without guessing from a name suffix.
    native = list(dict.fromkeys(
        label for value in reported
        if (label := legacy_directions.get(_capability_label(value), _capability_label(value))) not in blocked
    ))
    additional = [label for label in published if label not in blocked and label not in native]
    labels = native + list(dict.fromkeys(additional))
    corrected_direction = any(_capability_label(value) in legacy_directions for value in reported)
    if native and (additional or corrected_direction):
        return labels, "provider_metadata+" + source
    return labels, "provider_metadata" if native else source if labels else ""


def enrich_endpoint_capabilities(endpoint: ProviderEndpoint) -> ProviderEndpoint:
    """Supplement a saved endpoint view without network calls or settings writes.

    Only known model/official-host pairs receive documented labels. Explicit
    negatives retained during discovery still take precedence after a Save.
    """
    result = endpoint.model_copy(deep=True)
    for model_id in dict.fromkeys([*endpoint.models, endpoint.model]):
        if not model_id:
            continue
        documented, source = _documented_capabilities(endpoint, model_id)
        if not documented:
            continue
        existing = endpoint.model_capabilities.get(model_id, [])
        previous_source = endpoint.model_capability_sources.get(model_id, "")
        # Refresh our documented view; retain genuine provider metadata when
        # supplementing it rather than treating prior documentation as live data.
        reported = existing if previous_source.startswith("provider_metadata") else []
        labels, combined_source = _merge_capabilities(
            reported, documented, endpoint.model_capability_exclusions.get(model_id, []), source,
        )
        if reported and previous_source.startswith("provider_metadata+") and labels:
            combined_source = "provider_metadata+" + source
        result.model_capabilities[model_id] = labels
        if combined_source:
            result.model_capability_sources[model_id] = combined_source
    return result


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
    exclusions: dict[str, list[str]] = {}
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
                reported, excluded = _metadata_capabilities(entry) if isinstance(entry, dict) else ([], [])
                documented, source = _documented_capabilities(endpoint, model_id)
                labels, combined_source = _merge_capabilities(reported, documented, excluded, source)
                if labels:
                    capabilities[model_id] = labels
                    sources[model_id] = combined_source
                if excluded:
                    exclusions[model_id] = excluded
    return {
        "models": models,
        "model_capabilities": capabilities,
        "model_capability_sources": sources,
        "model_capability_exclusions": exclusions,
    }


async def discover_endpoint_models(endpoint: ProviderEndpoint) -> list[str]:
    """Query an OpenAI-compatible model listing endpoint and return the IDs it reports."""
    details = await discover_endpoint_model_details(endpoint)
    return details["models"]
