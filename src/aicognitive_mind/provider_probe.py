"""Small Administrator-initiated checks of the actual Steward function contract."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlparse

import httpx
from pydantic import ValidationError

from aicognitive_mind.provider_endpoints import ProviderEndpoint
from aicognitive_mind.steward_agent import RecallAction, ReviewAction, steward_action_tools
from aicognitive_mind.task_dispatcher import TaskModelDispatcher


_HTTP_GUIDANCE = {
    400: "The provider rejected the probe request. Check whether this model accepts the tool schema and request parameters.",
    401: "The provider did not authenticate the request. Check the API key for this endpoint.",
    402: "The provider requires billing or credits. Check the provider account.",
    403: "The provider denied access. Check the key's permissions and model access.",
    404: "The provider could not find the route or model. Check the endpoint URL and model ID.",
    422: "The provider could not process the probe request. Check model and tool-parameter compatibility.",
    429: "The provider reported a rate or quota limit. Check rate limits and billing before retrying.",
}

# Upstream payloads, including their structured fields, are not trusted. Display
# only exact, predefined tokens. Never include messages, details, or headers.
_ERROR_CODES = frozenset({
    "unsupported_parameter", "unsupported_value", "invalid_parameter", "invalid_value",
    "invalid_api_key", "model_not_found", "insufficient_quota", "rate_limit_exceeded",
    "context_length_exceeded", "INVALID_ARGUMENT", "UNAUTHENTICATED", "PERMISSION_DENIED",
    "NOT_FOUND", "RESOURCE_EXHAUSTED", "FAILED_PRECONDITION", "UNAVAILABLE",
})
_ERROR_PARAMETERS = frozenset({
    "model", "max_tokens", "max_completion_tokens", "messages", "tools", "tool_choice",
    "parallel_tool_calls", "temperature", "top_p",
})


def _known_token(value: Any, allowed: frozenset[str]) -> str:
    return value if isinstance(value, str) and value in allowed else ""


def _http_failure_message(phase: str, response: httpx.Response) -> str:
    status = response.status_code
    if 500 <= status < 600:
        guidance = "The provider reported a server error. Retry later or check its service status."
    elif 300 <= status < 400:
        guidance = "The provider redirected the request. Check the endpoint URL."
    else:
        guidance = _HTTP_GUIDANCE.get(status, "Check the endpoint URL and provider service status.")
    message = f"{phase.title()} check returned HTTP {status}. {guidance}"
    if len(response.content) > 16_384:
        return message
    try:
        body = response.json()
    except (ValueError, RecursionError):
        return message
    error = body.get("error") if isinstance(body, dict) else None
    if not isinstance(error, dict):
        return message
    code = _known_token(error.get("code"), _ERROR_CODES) or _known_token(
        error.get("status"), _ERROR_CODES
    )
    parameter = _known_token(error.get("param"), _ERROR_PARAMETERS)
    if code:
        message += f" Provider code: {code}."
    if parameter:
        message += f" Parameter: {parameter}."
    return message


async def probe_endpoint_tools(endpoint: ProviderEndpoint, *, client: Any | None = None) -> dict[str, Any]:
    """Use synthetic context, at most two requests, no retries and no settings writes.

    Both recall and review use the same function schemas as real interactions.
    A passing sample proves these two responses worked, not future availability.
    """
    if not endpoint.api_key or not endpoint.model:
        raise ValueError("Enter an API key and select a model before testing tool calling.")
    if client is None:
        async with httpx.AsyncClient(timeout=20.0) as session:
            return await probe_endpoint_tools(endpoint, client=session)
    url = TaskModelDispatcher._url(endpoint, "chat/completions")
    target = urlparse(url)
    # OpenAI uses the new field; other compatible endpoints keep their existing contract.
    token_limit = (
        "max_completion_tokens"
        if target.scheme == "https" and target.hostname == "api.openai.com"
        else "max_tokens"
    )
    for phase in ("recall", "review"):
        sample = (
            {"action": "finish", "outcome": "no_recall_needed", "reason": "Synthetic connection check.",
             "summary": "", "references": []}
            if phase == "recall" else
            {"action": "finish", "reason": "Synthetic connection check; nothing to retain.",
             "memories": [], "references": [], "evidence_indices": [],
             "transition_indices": [], "reframe_indices": []}
        )
        try:
            response = await client.post(
                url,
                headers=TaskModelDispatcher._headers(endpoint),
                json={
                    "model": endpoint.model, token_limit: 768,
                    "messages": [{"role": "user", "content":
                        "Synthetic Axiom connection check. Do not search or retain anything. "
                        "Call steward_action once with decision equal to: " + json.dumps(sample)}],
                    "tools": steward_action_tools(phase),
                    "tool_choice": {"type": "function", "function": {"name": "steward_action"}},
                    "parallel_tool_calls": False,
                },
            )
            response.raise_for_status()
            payload = response.json()
            message = payload["choices"][0]["message"]
            calls = message.get("tool_calls")
            if not isinstance(calls, list) or len(calls) != 1 or message.get("content"):
                raise ValueError("Expected one function call without additional text.")
            function = calls[0].get("function", {})
            arguments = function.get("arguments")
            if function.get("name") != "steward_action" or not isinstance(arguments, str) or len(arguments) > 16000:
                raise ValueError("The function name or arguments did not match the Steward contract.")
            validator = RecallAction if phase == "recall" else ReviewAction
            decision = validator.model_validate_json(arguments).decision
            # The prose reason may differ while preserving the requested action.
            actual = decision.model_dump(mode="json")
            if {key: value for key, value in actual.items() if key != "reason"} != {
                key: value for key, value in sample.items() if key != "reason"
            }:
                raise ValueError("The function response did not match the requested synthetic decision.")
        except httpx.HTTPStatusError as exc:
            return {"tool_calling_verified": False,
                    "message": _http_failure_message(phase, exc.response)}
        except httpx.RequestError:
            return {"tool_calling_verified": False,
                    "message": f"{phase.title()} check could not reach the provider within the request limit."}
        except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
            return {"tool_calling_verified": False,
                    "message": f"{phase.title()} check did not return a valid Steward function response. Try another tool-capable model."}
    return {"tool_calling_verified": True,
            "message": "Recall and review tool checks passed for this key and model. Provider availability and quota can still change."}
