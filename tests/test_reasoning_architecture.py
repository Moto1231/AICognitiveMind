# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from pathlib import Path
import unittest

from aicognitive_mind.config import Settings


class ReasoningArchitectureTests(unittest.TestCase):
    def test_standalone_provider_overrides_legacy_provider(self) -> None:
        settings = Settings(
            _env_file=None,
            standalone_reasoning_provider="openai",
            reasoning_provider="gemini",
        )

        self.assertEqual(
            settings.effective_standalone_reasoning_provider,
            "openai",
        )

    def test_legacy_provider_remains_compatible(self) -> None:
        settings = Settings(
            _env_file=None,
            standalone_reasoning_provider=None,
            reasoning_provider="gemini",
        )

        self.assertEqual(
            settings.effective_standalone_reasoning_provider,
            "gemini",
        )

    def test_api_reports_external_host_as_primary(self) -> None:
        api = Path(
            "src/aicognitive_mind/api.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"primary_mode": "external_host"', api)
        self.assertIn('"external_host_protocol": "MCP"', api)
        self.assertIn('"standalone_fallback": {', api)
        self.assertIn(
            "effective_standalone_reasoning_provider",
            api,
        )

    def test_architecture_decision_preserves_model_continuity(self) -> None:
        decision = Path(
            "docs/0008-external-host-primary-reasoning.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "Inter-reasoning-model continuity",
            decision,
        )
        self.assertIn(
            "standalone fallback reasoning provider",
            decision,
        )


if __name__ == "__main__":
    unittest.main()
