import unittest

from unittest.mock import patch

from pydantic import ValidationError

from aicognitive_mind.provider_endpoints import (
    ProviderEndpoint,
    ProviderEndpointRegistry,
    _reported_capabilities,
    discover_endpoint_model_details,
)


class FakeRecords:
    def __init__(self):
        self.values = {}

    async def get(self, key):
        return self.values.get(key)

    async def create(self, key, value):
        self.values[key] = value

    async def replace(self, key, before, after):
        if self.values.get(key) != before:
            return False
        self.values[key] = after
        return True


class ProviderEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_endpoint_registry_round_trips_credentials_and_models(self):
        registry = ProviderEndpointRegistry(FakeRecords())
        endpoint = ProviderEndpoint(
            id="local",
            name="Local model server",
            base_url="http://localhost:8000/v1/",
            api_key="admin-visible-key",
            models=["vision-model", "audio-model", "vision-model"],
        )

        saved = await registry.replace([endpoint])
        loaded = await registry.list()

        self.assertEqual(saved, loaded)
        self.assertEqual(loaded[0].base_url, "http://localhost:8000/v1")
        self.assertEqual(loaded[0].api_key, "admin-visible-key")
        self.assertEqual(loaded[0].models, ["vision-model", "audio-model"])

    def test_capability_labels_use_only_explicit_provider_metadata(self):
        self.assertEqual(
            _reported_capabilities({"id": "model-a", "architecture": {"input_modalities": ["text", "image"]}}),
            ["Text", "Vision"],
        )
        self.assertEqual(_reported_capabilities({"id": "model-b"}), [])


    async def test_model_discovery_uses_exact_configured_base_url_without_v1_fallback(self):
        requested_urls = []

        class FakeResponse:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return {"data": [{"id": "model-a"}]}

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, headers=None):
                requested_urls.append(url)
                return FakeResponse()

        endpoint = ProviderEndpoint(
            id="custom",
            name="Custom versioned API",
            base_url="https://provider.example/custom/v3",
        )
        with patch("aicognitive_mind.provider_endpoints.httpx.AsyncClient", FakeClient):
            details = await discover_endpoint_model_details(endpoint)

        self.assertEqual(requested_urls, ["https://provider.example/custom/v3/models"])
        self.assertEqual(details["models"], ["model-a"])

    async def test_endpoint_ids_must_be_unique(self):
        registry = ProviderEndpointRegistry(FakeRecords())
        endpoint = ProviderEndpoint(id="same", name="Provider", base_url="https://example.com/v1")

        with self.assertRaisesRegex(ValueError, "unique"):
            await registry.replace([endpoint, endpoint])

    async def test_endpoint_requires_absolute_http_url(self):
        with self.assertRaises(ValidationError):
            ProviderEndpoint(id="provider", name="Provider", base_url="not-a-url")


if __name__ == "__main__":
    unittest.main()
