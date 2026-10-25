"""Small Administrator-initiated checks of the actual Steward function contract."""

from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from aicognitive_mind.provider_endpoints import ProviderEndpoint
from aicognitive_mind.steward_agent import RecallAction, ReviewAction, steward_action_tools
from aicognitive_mind.task_dispatcher import TaskModelDispatcher


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
                TaskModelDispatcher._url(endpoint, "chat/completions"),
                headers=TaskModelDispatcher._headers(endpoint),
                json={
                    "model": endpoint.model, "max_tokens": 768,
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
                    "message": f"{phase.title()} check returned HTTP {exc.response.status_code}. Check the key, model access and provider limits."}
        except httpx.RequestError:
            return {"tool_calling_verified": False,
                    "message": f"{phase.title()} check could not reach the provider within the request limit."}
        except (KeyError, IndexError, TypeError, AttributeError, ValueError, ValidationError):
            return {"tool_calling_verified": False,
                    "message": f"{phase.title()} check did not return a valid Steward function response. Try another tool-capable model."}
    return {"tool_calling_verified": True,
            "message": "Recall and review tool checks passed for this key and model. Provider availability and quota can still change."}
