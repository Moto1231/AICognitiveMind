from __future__ import annotations

import unittest

from aicognitive_mind.config import (
    body_allow_standalone_fallback_enabled,
    body_allow_standalone_fallback_override,
    get_settings,
    set_body_allow_standalone_fallback_override,
)


class BodyFallbackConfigTests(unittest.TestCase):
    def tearDown(self) -> None:
        set_body_allow_standalone_fallback_override(None)

    def test_runtime_override_takes_precedence_over_deployment_setting(self) -> None:
        set_body_allow_standalone_fallback_override(True)
        self.assertTrue(body_allow_standalone_fallback_enabled())
        self.assertIs(body_allow_standalone_fallback_override(), True)

        set_body_allow_standalone_fallback_override(False)
        self.assertFalse(body_allow_standalone_fallback_enabled())
        self.assertIs(body_allow_standalone_fallback_override(), False)

    def test_clearing_runtime_override_restores_deployment_setting(self) -> None:
        set_body_allow_standalone_fallback_override(True)
        set_body_allow_standalone_fallback_override(None)
        self.assertIsNone(body_allow_standalone_fallback_override())
        self.assertEqual(
            body_allow_standalone_fallback_enabled(),
            get_settings().body_allow_standalone_fallback,
        )


if __name__ == "__main__":
    unittest.main()
