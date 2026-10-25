import unittest
from types import SimpleNamespace

from aicognitive_mind.model_capability_catalog import documented_capabilities


class ModelCapabilityCatalogTests(unittest.TestCase):
    def capabilities(self, base_url, model_id):
        return documented_capabilities(SimpleNamespace(base_url=base_url), model_id)

    def test_current_saved_models_receive_provider_scoped_documentation(self):
        entries = (
            ("https://api.groq.com/openai/v1", "openai/gpt-oss-20b", "console.groq.com"),
            ("https://api.cerebras.ai/v1", "gpt-oss-120b", "inference-docs.cerebras.ai"),
            ("https://openrouter.ai/api/v1", "openai/gpt-chat-latest", "openrouter.ai"),
            ("https://api.sambanova.ai/v1", "gpt-oss-120b", "docs.sambanova.ai"),
            ("https://api.mistral.ai/v1", "mistral-medium-latest", "docs.mistral.ai"),
            ("https://api.mistral.ai/v1", "mistral-medium-3-5", "docs.mistral.ai"),
        )
        for base_url, model_id, source_host in entries:
            with self.subTest(base_url=base_url, model_id=model_id):
                labels, source = self.capabilities(base_url, model_id)
                self.assertIn("Text", labels)
                self.assertIn("Tools", labels)
                self.assertIn(source_host, source)

    def test_gemini_tts_cannot_be_mistaken_for_text_or_tool_output(self):
        for model_id in ("gemini-3.8-flash-tts", "models/gemini-3.8-flash-tts"):
            labels, source = self.capabilities(
                "https://generativelanguage.googleapis.com/v1beta/openai", model_id,
            )
            self.assertEqual(labels, ["Text Input", "Audio Output"])
            self.assertNotIn("Text", labels)
            self.assertNotIn("Tools", labels)
            self.assertNotIn("Audio Input", labels)
            self.assertNotIn("Structured Outputs", labels)
            self.assertTrue(source.endswith("/gemini-3.8-flash-tts"))

    def test_provider_documentation_keeps_vision_and_structured_output_scopes_distinct(self):
        mistral, _ = self.capabilities("https://api.mistral.ai/v1", "mistral-medium-3-5")
        self.assertIn("Vision", mistral)
        cerebras, source = self.capabilities("https://api.cerebras.ai/v1", "gpt-oss-120b")
        self.assertIn("Structured Outputs", cerebras)
        self.assertTrue(source.endswith("/capabilities/structured-outputs"))
        samba, _ = self.capabilities("https://api.sambanova.ai/v1", "gpt-oss-120b")
        self.assertEqual(samba, ["Text", "Tools"])
        self.assertNotIn("Vision", cerebras)
        self.assertNotIn("Vision", samba)

    def test_verified_gemini_text_models_have_inputs_and_tools_but_no_audio_output(self):
        for model_id in (
            "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.1-flash-lite",
            "gemini-3.5-flash-lite", "gemini-3.8-flash",
        ):
            for alias in (model_id, f"models/{model_id}"):
                with self.subTest(model_id=alias):
                    labels, source = self.capabilities(
                        "https://generativelanguage.googleapis.com/v1beta/openai/", alias,
                    )
                    self.assertEqual(labels, [
                        "Text", "Vision", "Video Input", "Audio Input", "Tools", "Structured Outputs",
                    ])
                    self.assertNotIn("Audio Output", labels)
                    self.assertTrue(source.endswith("/" + model_id))

    def test_unknown_suffixed_preview_and_legacy_models_do_not_inherit_claims(self):
        entries = (
            ("https://api.mistral.ai/v1", "mistral-medium"),
            ("https://api.mistral.ai/v1", "mistral-medium-latest-audio"),
            ("https://api.cerebras.ai/v1", "gpt-oss-120b-vision"),
            ("https://api.sambanova.ai/v1", "gpt-oss-120b-audio"),
            ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.1-flash-lite-image"),
            ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-3.1-flash-lite-preview"),
            ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-future-flash"),
        )
        for base_url, model_id in entries:
            with self.subTest(base_url=base_url, model_id=model_id):
                self.assertEqual(self.capabilities(base_url, model_id), ([], ""))

    def test_documented_provider_features_do_not_transfer_to_proxy_or_wrong_api(self):
        for base_url in (
            "https://proxy.example/v1", "https://api.cerebras.ai.evil.example/v1",
            "https://custom.api.cerebras.ai/v1", "http://api.cerebras.ai/v1",
            "https://api.cerebras.ai/custom/v1", "https://api.cerebras.ai/v2",
            "https://api.cerebras.ai/v1/chat/completions", "https://api.cerebras.ai:8443/v1",
            "https://api.cerebras.ai/v1?proxy=1", "https://api.cerebras.ai/v1#other",
            "https://user:password@api.cerebras.ai/v1",
        ):
            with self.subTest(base_url=base_url):
                self.assertEqual(self.capabilities(base_url, "gpt-oss-120b"), ([], ""))
        self.assertEqual(self.capabilities("https://api.sambanova.ai/v1", "openai/gpt-chat-latest"), ([], ""))
        self.assertEqual(self.capabilities("https://generativelanguage.googleapis.com/v1beta", "gemini-3.8-flash"), ([], ""))

    def test_independent_returned_lists_and_safe_url_normalization(self):
        labels, source = self.capabilities("https://API.CEREBRAS.AI:443/v1/", "gpt-oss-120b")
        self.assertIn("Tools", labels)
        labels.append("Invented")
        later, later_source = self.capabilities("https://api.cerebras.ai/v1", "gpt-oss-120b")
        self.assertNotIn("Invented", later)
        self.assertEqual(later_source, source)

    def test_invalid_endpoint_values_return_no_claims(self):
        for base_url in (None, 4, "https://api.cerebras.ai:wrong/v1", "https://[invalid/v1"):
            with self.subTest(base_url=base_url):
                self.assertEqual(self.capabilities(base_url, "gpt-oss-120b"), ([], ""))
        self.assertEqual(documented_capabilities(object(), "gpt-oss-120b"), ([], ""))


if __name__ == "__main__":
    unittest.main()
