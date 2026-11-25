import json
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import HTTPException
from starlette.requests import Request

from aicognitive_mind import api
from aicognitive_mind.provider_endpoints import ProviderEndpoint
from aicognitive_mind.provider_probe import probe_endpoint_tools


class ProviderProbeTests(unittest.IsolatedAsyncioTestCase):
    def endpoint(self):
        return ProviderEndpoint(id="sample", name="Sample", base_url="https://example.test/v1",
                                api_key="secret-test-key", model="chosen-model")

    async def test_both_real_steward_schemas_must_pass_without_settings_writes(self):
        requests = []

        async def respond(request):
            body = json.loads(request.content)
            requests.append(body)
            sample = json.loads(body["messages"][0]["content"].split("equal to: ")[1])
            return httpx.Response(200, json={"choices": [{"message": {"content": None, "tool_calls": [
                {"function": {"name": "steward_action", "arguments": json.dumps({"decision": sample})}}
            ]}}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            result = await probe_endpoint_tools(self.endpoint(), client=client)
        self.assertTrue(result["tool_calling_verified"])
        self.assertEqual(len(requests), 2)
        self.assertTrue(all(item["model"] == "chosen-model" for item in requests))
        self.assertTrue(all(item["tool_choice"]["function"]["name"] == "steward_action" for item in requests))
        self.assertIn("no_recall_needed", json.dumps(requests[0]["tools"]))
        self.assertIn("memories", json.dumps(requests[1]["tools"]))

    async def test_rejects_text_or_wrong_action_and_stops_after_first_failure(self):
        for message in ({"content": "looks fine"}, {"content": None, "tool_calls": [
            {"function": {"name": "invented", "arguments": "{}"}}
        ]}):
            with self.subTest(message=message):
                client = AsyncMock()
                client.post.return_value = httpx.Response(200, request=httpx.Request("POST", "https://example.test"),
                                                         json={"choices": [{"message": message}]})
                result = await probe_endpoint_tools(self.endpoint(), client=client)
                self.assertFalse(result["tool_calling_verified"])
                self.assertEqual(client.post.await_count, 1)

    async def test_http_error_is_redacted_and_not_retried(self):
        client = AsyncMock()
        client.post.return_value = httpx.Response(429, request=httpx.Request("POST", "https://example.test"),
                                                 json={"error": "secret-test-key"})
        result = await probe_endpoint_tools(self.endpoint(), client=client)
        self.assertFalse(result["tool_calling_verified"])
        self.assertIn("HTTP 429", result["message"])
        self.assertNotIn("secret-test-key", json.dumps(result))
        self.assertEqual(client.post.await_count, 1)

    async def test_actual_admin_probe_route_shows_only_safe_upstream_diagnostics(self):
        cases = (
            (400, "https://api.openai.com/v1", {
                "message": "Unsupported parameter. Private fixture secret-test-key",
                "type": "invalid_request_error",
                "code": "unsupported_parameter",
                "param": "max_tokens",
            }, ("rejected the probe request", "unsupported_parameter", "max_tokens")),
            (400, "https://generativelanguage.googleapis.com/v1beta/openai", {
                "status": "INVALID_ARGUMENT",
                "code": 400,
                "message": "Request contains invalid argument. Private fixture secret-test-key",
                "details": [{"field": "tools", "value": "private-fixture-detail"}],
                "param": "private-fixture-param",
            }, ("rejected the probe request", "INVALID_ARGUMENT")),
            (429, "https://generativelanguage.googleapis.com/v1beta/openai", {
                "status": "RESOURCE_EXHAUSTED",
                "code": "private-fixture-code",
                "message": "Private fixture secret-test-key",
            }, ("rate or quota limit", "RESOURCE_EXHAUSTED")),
            (401, "https://api.openai.com/v1", {
                "code": "invalid_api_key", "message": "Private fixture secret-test-key",
            }, ("did not authenticate", "invalid_api_key")),
            (403, "https://api.openai.com/v1", {
                "code": [], "param": {"secret": "private-fixture-param"},
            }, ("denied access",)),
            (503, "https://api.openai.com/v1", None, ("reported a server error",)),
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=api.app), base_url="http://test"
        ) as browser:
            for status, base_url, error, expected in cases:
                with self.subTest(status=status, base_url=base_url):
                    provider = AsyncMock()
                    request = httpx.Request("POST", base_url, headers={
                        "Authorization": "Bearer secret-test-key",
                    })
                    if error is None:
                        provider.post.return_value = httpx.Response(
                            status, request=request, text="Private fixture secret-test-key"
                        )
                    else:
                        provider.post.return_value = httpx.Response(
                            status, request=request, json={"error": error}
                        )
                    with patch.object(api, "require_admin") as auth, patch(
                        "aicognitive_mind.provider_probe.httpx.AsyncClient"
                    ) as provider_factory:
                        provider_factory.return_value.__aenter__.return_value = provider
                        response = await browser.post(
                            "/v1/admin/provider-endpoints/probe",
                            json=self.endpoint().model_copy(
                                update={"base_url": base_url}
                            ).model_dump(mode="json"),
                        )
                    self.assertEqual(response.status_code, 200)
                    result = response.json()
                    self.assertIs(result["tool_calling_verified"], False)
                    self.assertIn(f"Recall check returned HTTP {status}", result["message"])
                    for token in expected:
                        self.assertIn(token, result["message"])
                    for forbidden in ("secret-test-key", "Private fixture", "private-fixture"):
                        self.assertNotIn(forbidden, response.text)
                    auth.assert_called_once()
                    provider.post.assert_awaited_once()

    async def test_missing_credentials_or_model_does_not_make_request(self):
        client = AsyncMock()
        for change in ({"api_key": ""}, {"model": ""}):
            with self.assertRaises(ValueError):
                await probe_endpoint_tools(self.endpoint().model_copy(update=change), client=client)
        client.post.assert_not_awaited()

    async def test_api_requires_administrator_before_probe(self):
        request = Request({"type": "http", "app": api.app, "headers": []})
        with patch("aicognitive_mind.api.require_admin", side_effect=HTTPException(401, "Admin required")), \
             patch("aicognitive_mind.api.probe_endpoint_tools", new_callable=AsyncMock) as probe:
            with self.assertRaises(HTTPException) as error:
                await api.probe_admin_provider_endpoint_tools(self.endpoint(), request)
        self.assertEqual(error.exception.status_code, 401)
        probe.assert_not_awaited()
