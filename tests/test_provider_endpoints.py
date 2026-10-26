import unittest

from unittest.mock import patch

from pydantic import ValidationError

from aicognitive_mind.provider_endpoints import (
    ProviderEndpoint,
    ProviderEndpointRegistry,
    _reported_capabilities,
    _documented_capabilities,
    discover_endpoint_model_details,
    enrich_endpoint_capabilities,
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
            provider_name=" Example Provider ",
            base_url="http://localhost:8000/v1/",
            api_key="admin-visible-key",
            model=" vision-model ",
            models=["vision-model", "audio-model", "vision-model"],
        )

        saved = await registry.replace([endpoint])
        loaded = await registry.list()

        self.assertEqual(saved, loaded)
        self.assertEqual(loaded[0].base_url, "http://localhost:8000/v1")
        self.assertEqual(loaded[0].api_key, "admin-visible-key")
        self.assertEqual(loaded[0].provider_name, "Example Provider")
        self.assertEqual(loaded[0].model, "vision-model")
        self.assertEqual(loaded[0].models, ["vision-model", "audio-model"])

    def test_capability_labels_use_only_explicit_provider_metadata(self):
        self.assertEqual(
            _reported_capabilities({"id": "model-a", "architecture": {"input_modalities": ["text", "image"]}}),
            ["Text", "Vision"],
        )
        self.assertEqual(_reported_capabilities({"id": "model-b"}), [])

    def test_gateway_flags_and_output_modalities_are_read_without_false_flags(self):
        self.assertEqual(_reported_capabilities({
            "capabilities": {"vision": True, "audio": False},
            "architecture": {"output_modalities": ["text"]},
            "model_info": {"supports_function_calling": True, "supports_audio_output": False},
        }), ["Vision", "Text", "Tools"])

    def test_openrouter_parameters_and_mistral_feature_names_are_recognized(self):
        self.assertEqual(_reported_capabilities({
            "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
            "supported_parameters": ["tools", "tool_choice", "structured_outputs", "response_format"],
        }), ["Text", "Vision", "Tools", "Structured Outputs"])
        self.assertEqual(_reported_capabilities({"capabilities": {
            "completion_chat": True, "function_calling": True, "vision": True,
        }}), ["Text", "Tools", "Vision"])

    def test_response_format_alone_and_generation_methods_do_not_claim_tools_or_schema(self):
        self.assertEqual(_reported_capabilities({"supported_parameters": ["response_format"]}), [])
        self.assertEqual(_reported_capabilities({
            "id": "tool-vision-model", "supportedGenerationMethods": ["generateContent"],
        }), [])

    def test_input_and_output_modalities_distinguish_speech_generation_from_chat(self):
        self.assertEqual(_reported_capabilities({"architecture": {
            "input_modalities": ["text"], "output_modalities": ["audio"],
        }}), ["Text Input", "Audio Output"])
        self.assertEqual(_reported_capabilities({
            "input_modalities": ["audio", "image"], "output_modalities": ["text"],
        }), ["Audio Input", "Vision", "Text"])

    def test_malformed_modality_values_are_ignored_without_crashing(self):
        for malformed in (None, "audio", 7, {"text": True}):
            with self.subTest(value=malformed):
                self.assertEqual(_reported_capabilities({
                    "input_modalities": malformed, "output_modalities": malformed,
                    "architecture": {"input_modalities": malformed, "output_modalities": malformed},
                }), [])

    def test_explicit_false_takes_precedence_over_equivalent_positive_parameter(self):
        self.assertEqual(_reported_capabilities({
            "capabilities": {"function_calling": False, "audio": False},
            "supported_parameters": ["tools", "tool_choice"],
            "model_info": {"supports_function_calling": True, "supports_audio_input": True},
        }), [])

    def test_modality_feature_maps_preserve_positive_and_negative_values(self):
        self.assertEqual(_reported_capabilities({
            "modalities": {"text": True, "audio": False},
            "metadata": {"supports_audio_output": True},
        }), ["Text"])

    def test_saved_gemini_tts_view_gets_documented_directional_labels_without_mutation(self):
        model = "models/gemini-3.8-flash-tts"
        endpoint = ProviderEndpoint(id="gemini", name="Saved Gemini", api_key="unchanged-key",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai", model=model, models=[model])
        before = endpoint.model_dump()
        enriched = enrich_endpoint_capabilities(endpoint)
        self.assertEqual(enriched.model_capabilities[model], ["Text Input", "Audio Output"])
        self.assertNotIn("Tools", enriched.model_capabilities[model])
        self.assertTrue(enriched.model_capability_sources[model].startswith("https://ai.google.dev/"))
        self.assertEqual(endpoint.model_dump(), before)
        self.assertEqual((enriched.api_key, enriched.model, enriched.models),
                         (endpoint.api_key, endpoint.model, endpoint.models))

    def test_legacy_flattened_tts_metadata_is_disambiguated_by_exact_documented_model(self):
        model = "models/gemini-3.8-flash-tts"
        endpoint = ProviderEndpoint(id="gemini", name="Gemini",
            base_url="https://generativelanguage.googleapis.com/v1beta/openai", model=model,
            model_capabilities={model: ["Text", "Audio"]},
            model_capability_sources={model: "provider_metadata"})
        enriched = enrich_endpoint_capabilities(endpoint)
        self.assertEqual(enriched.model_capabilities[model], ["Text Input", "Audio Output"])
        self.assertTrue(enriched.model_capability_sources[model].startswith("provider_metadata+https://ai.google.dev/"))
        blocked = endpoint.model_copy(update={"model_capability_exclusions": {model: ["Audio Output"]}})
        self.assertEqual(enrich_endpoint_capabilities(blocked).model_capabilities[model], ["Text Input"])

    async def test_discovery_direction_correction_retains_documentation_provenance(self):
        endpoint = ProviderEndpoint(id="gemini", name="Gemini", model="models/gemini-3.8-flash-tts",
                                    base_url="https://generativelanguage.googleapis.com/v1beta/openai")
        details = await self.discover_fixture(endpoint, {"data": [{
            "id": endpoint.model, "modalities": ["text", "audio"],
        }]})
        self.assertEqual(details["model_capabilities"][endpoint.model], ["Text Input", "Audio Output"])
        self.assertTrue(details["model_capability_sources"][endpoint.model].startswith("provider_metadata+https://ai.google.dev/"))

    async def test_documentation_supplements_partial_metadata_and_keeps_mixed_provenance(self):
        endpoint = ProviderEndpoint(id="cerebras", name="Cerebras", model="gpt-oss-120b",
                                    base_url="https://api.cerebras.ai/v1")
        details = await self.discover_fixture(endpoint, {"data": [{
            "id": "gpt-oss-120b", "input_modalities": ["text"],
        }]})
        self.assertEqual(details["model_capabilities"][endpoint.model], ["Text", "Tools", "Structured Outputs"])
        source = details["model_capability_sources"][endpoint.model]
        self.assertTrue(source.startswith("provider_metadata+https://inference-docs.cerebras.ai/"))
        enriched = enrich_endpoint_capabilities(endpoint.model_copy(update=details))
        self.assertEqual(enriched.model_capability_sources[endpoint.model], source)

    async def test_explicit_negative_survives_discovery_save_and_saved_view_enrichment(self):
        endpoint = ProviderEndpoint(id="cerebras", name="Cerebras", model="gpt-oss-120b",
                                    base_url="https://api.cerebras.ai/v1")
        details = await self.discover_fixture(endpoint, {"data": [{
            "id": "gpt-oss-120b", "input_modalities": ["text"],
            "capabilities": {"function_calling": False, "structured_outputs": False},
        }]})
        self.assertEqual(details["model_capabilities"][endpoint.model], ["Text"])
        self.assertEqual(set(details["model_capability_exclusions"][endpoint.model]), {"Tools", "Structured Outputs"})
        records = FakeRecords()
        registry = ProviderEndpointRegistry(records)
        await registry.replace([endpoint.model_copy(update=details)])
        loaded = (await registry.list())[0]
        enriched = enrich_endpoint_capabilities(loaded)
        self.assertEqual(enriched.model_capabilities[endpoint.model], ["Text"])
        self.assertEqual(set(enriched.model_capability_exclusions[endpoint.model]), {"Tools", "Structured Outputs"})

    def test_saved_exclusion_aliases_cannot_be_reintroduced_by_documentation(self):
        endpoint = ProviderEndpoint(id="cerebras", name="Cerebras", model="gpt-oss-120b",
            base_url="https://api.cerebras.ai/v1", model_capability_exclusions={
                "gpt-oss-120b": ["tool_calling", "structured outputs"],
            })
        self.assertEqual(enrich_endpoint_capabilities(endpoint).model_capabilities[endpoint.model], ["Text"])

    async def discover_fixture(self, endpoint, payload):
        class FakeResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return payload

        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def get(self, url, headers=None):
                return FakeResponse()

        with patch("aicognitive_mind.provider_endpoints.httpx.AsyncClient", FakeClient):
            return await discover_endpoint_model_details(endpoint)

    async def test_groq_vision_documentation_enriches_sparse_discovery_without_overriding_denials(self):
        model = "qwen/qwen3.8-27b"
        endpoint = ProviderEndpoint(id="groq", name="Groq", model=model,
                                    base_url="https://api.groq.com/openai/v1")
        details = await self.discover_fixture(endpoint, {"data": [{"id": model}]})
        self.assertEqual(details["model_capabilities"][model], ["Text", "Vision", "Tools"])
        self.assertEqual(details["model_capability_sources"][model], "https://console.groq.com/docs/vision")
        denied = await self.discover_fixture(endpoint, {"data": [{
            "id": model, "capabilities": {"supports_vision": False},
        }]})
        self.assertNotIn("Vision", denied["model_capabilities"][model])
        self.assertIn("Vision", denied["model_capability_exclusions"][model])
        proxy = endpoint.model_copy(update={"base_url": "https://compatible.example/openai/v1"})
        self.assertEqual(_documented_capabilities(proxy, model), ([], ""))
        self.assertEqual(_documented_capabilities(endpoint, "qwen/qwen-future-vision"), ([], ""))

    def test_documented_modalities_are_scoped_to_actual_openai_endpoint(self):
        official = ProviderEndpoint(id="openai", name="OpenAI", base_url="https://api.openai.com/v1")
        labels, source = _documented_capabilities(official, "gpt-5.5-2026-04-23")
        self.assertEqual(labels, ["Text", "Vision"])
        self.assertEqual(source, "https://developers.openai.com/api/docs/models/gpt-5.5")
        custom = official.model_copy(update={"base_url": "https://compatible.example/v1"})
        self.assertEqual(_documented_capabilities(custom, "gpt-5.5"), ([], ""))
        self.assertEqual(_documented_capabilities(official, "gpt-future-unknown"), ([], ""))


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
