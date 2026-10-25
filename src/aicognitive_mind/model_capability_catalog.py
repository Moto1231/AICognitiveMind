"""Finite, provider-scoped documentation supplements for sparse model listings.

These entries describe published features checked on 2026-10-25. They are not
credential, quota, adapter compatibility, or live inference checks. Unknown IDs
and compatible proxies must supply their own metadata rather than inherit claims
from a similar model name. Provider-reported restrictions take precedence at the
discovery layer.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse


Documentation = tuple[tuple[str, ...], str]

_GEMINI_TEXT_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
)

# Each listed model card explicitly supplies these modalities and capabilities.
# The 2.5 cards also warn that access is limited to established users; a catalog
# entry never implies that a particular key can use the model.
_GEMINI_MODELS: dict[str, Documentation] = {
    alias: (
        ("Text", "Vision", "Video Input", "Audio Input", "Tools", "Structured Outputs"),
        f"https://ai.google.dev/gemini-api/docs/models/{model_id}",
    )
    for model_id in _GEMINI_TEXT_MODELS
    for alias in (model_id, f"models/{model_id}")
}
_GEMINI_MODELS.update({
    alias: (
        ("Text Input", "Audio Output"),
        "https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts",
    )
    for alias in ("gemini-3.8-flash-tts", "models/gemini-3.8-flash-tts")
})

_CATALOG: dict[tuple[str, str], dict[str, Documentation]] = {
    ("api.groq.com", "/openai/v1"): {
        "openai/gpt-oss-20b": (
            ("Text", "Tools", "Structured Outputs"),
            "https://console.groq.com/docs/model/openai/gpt-oss-20b",
        ),
    },
    ("api.cerebras.ai", "/v1"): {
        # This page names gpt-oss-120b for text, JSON Schema and strict output;
        # the tool-use page also explicitly lists its named function support.
        "gpt-oss-120b": (
            ("Text", "Tools", "Structured Outputs"),
            "https://inference-docs.cerebras.ai/capabilities/structured-outputs",
        ),
    },
    ("generativelanguage.googleapis.com", "/v1beta/openai"): _GEMINI_MODELS,
    ("openrouter.ai", "/api/v1"): {
        "openai/gpt-chat-latest": (
            ("Text", "Vision", "Tools", "Structured Outputs"),
            "https://openrouter.ai/openai/gpt-chat-latest",
        ),
    },
    ("api.sambanova.ai", "/v1"): {
        # The model catalog confirms text-only serving for this model, and the
        # function-calling guide names this exact ID. Do not import another
        # provider's deployment capabilities from the shared weights.
        "gpt-oss-120b": (
            ("Text", "Tools"),
            "https://docs.sambanova.ai/docs/en/features/function-calling",
        ),
    },
    ("api.mistral.ai", "/v1"): {
        # Vision is explicit in the Medium 3.5 release article, including its
        # image-size/aspect-ratio encoder, in addition to the model card:
        # https://mistral.ai/news/vibe-remote-agents-mistral-medium-3-5/
        model_id: (
            ("Text", "Vision", "Tools", "Structured Outputs"),
            "https://docs.mistral.ai/models/mistral-medium-3-5-26-04",
        )
        for model_id in ("mistral-medium-latest", "mistral-medium-3-5")
    },
}


def documented_capabilities(endpoint: Any, model_id: str) -> tuple[list[str], str]:
    """Return documented labels only for an exact official API and known ID.

    The native Gemini model-list prefix is an explicit alias of each finite
    known model, rather than a rule that grants capabilities to arbitrary IDs.
    Returned lists are independent of the shared catalog and safe to enrich.
    """
    base_url = getattr(endpoint, "base_url", None)
    if not isinstance(base_url, str) or not isinstance(model_id, str):
        return [], ""
    try:
        parsed = urlparse(base_url)
        official_api = (
            parsed.scheme == "https"
            and parsed.port in (None, 443)
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
        )
    except (TypeError, ValueError):
        return [], ""
    if not official_api:
        return [], ""
    documented = _CATALOG.get((parsed.hostname or "", parsed.path.rstrip("/")), {}).get(model_id)
    if documented is None:
        return [], ""
    labels, source = documented
    return list(labels), source
