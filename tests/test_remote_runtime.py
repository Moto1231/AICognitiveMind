import base64
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from aicognitive_mind.api import (
    _reasoning_backend_error_detail,
    _validate_reasoning_configuration,
    app_access_authorized,
)
from aicognitive_mind.config import Settings
from aicognitive_mind.persistence import create_storage


def basic(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


class RemoteRuntimeTests(unittest.IsolatedAsyncioTestCase):
    def test_access_auth_is_open_when_password_is_not_configured(self) -> None:
        settings = SimpleNamespace(
            app_access_username="mind",
            app_access_password=None,
        )
        with patch("aicognitive_mind.api.get_settings", return_value=settings):
            self.assertTrue(app_access_authorized(None))

    def test_access_auth_requires_matching_username_and_password(self) -> None:
        settings = SimpleNamespace(
            app_access_username="mind",
            app_access_password="secret-password",
        )
        with patch("aicognitive_mind.api.get_settings", return_value=settings):
            self.assertFalse(app_access_authorized(None))
            self.assertFalse(app_access_authorized("Bearer nope"))
            self.assertFalse(app_access_authorized(basic("other", "secret-password")))
            self.assertFalse(app_access_authorized(basic("mind", "wrong")))
            self.assertTrue(app_access_authorized(basic("mind", "secret-password")))

    def test_render_blueprint_targets_remote_atlas_runtime(self) -> None:
        blueprint = Path("render.yaml").read_text(encoding="utf-8")
        self.assertIn("type: web", blueprint)
        self.assertIn("runtime: python", blueprint)
        self.assertIn("plan: free", blueprint)
        self.assertIn("region: ohio", blueprint)
        self.assertIn("healthCheckPath: /health", blueprint)
        self.assertIn("STORAGE_PROVIDER", blueprint)
        self.assertIn("value: mongo", blueprint)
        self.assertIn("MONGODB_URI", blueprint)
        self.assertIn("REASONING_PROVIDER", blueprint)
        self.assertIn("value: gemini", blueprint)
        self.assertIn("GEMINI_API_KEY", blueprint)
        self.assertIn("GEMINI_MODEL", blueprint)
        self.assertIn("gemini-3.5-flash", blueprint)
        self.assertIn("APP_ACCESS_PASSWORD", blueprint)
        self.assertGreaterEqual(blueprint.count("sync: false"), 3)
        self.assertIn(
            "uvicorn aicognitive_mind.api:app --host 0.0.0.0 --port $PORT",
            blueprint,
        )

    async def test_render_requires_gemini_api_key_for_gemini_provider(self) -> None:
        settings = SimpleNamespace(
            reasoning_provider="gemini",
            gemini_api_key=None,
            openai_api_key=None,
        )
        with patch.dict("os.environ", {"RENDER": "true"}, clear=False):
            with self.assertRaisesRegex(
                RuntimeError,
                "GEMINI_API_KEY is not configured for Render",
            ):
                _validate_reasoning_configuration(settings)

    async def test_render_rejects_echo_reasoning_provider(self) -> None:
        settings = SimpleNamespace(
            reasoning_provider="echo",
            gemini_api_key=None,
            openai_api_key=None,
        )
        with patch.dict("os.environ", {"RENDER": "true"}, clear=False):
            with self.assertRaisesRegex(
                RuntimeError,
                "REASONING_PROVIDER=echo is not allowed on Render",
            ):
                _validate_reasoning_configuration(settings)

    async def test_render_allows_configured_gemini_provider(self) -> None:
        settings = SimpleNamespace(
            reasoning_provider="gemini",
            gemini_api_key="test-gemini-key",
            openai_api_key=None,
        )
        with patch.dict("os.environ", {"RENDER": "true"}, clear=False):
            self.assertEqual(_validate_reasoning_configuration(settings), "gemini")

    async def test_render_rejects_local_mongo_fallback(self) -> None:
        settings = Settings(
            storage_provider="mongo",
            mongodb_uri="mongodb://mongodb:27017",
        )
        with patch.dict("os.environ", {"RENDER": "true"}, clear=False):
            with self.assertRaisesRegex(
                RuntimeError,
                "MONGODB_URI is not configured for Render",
            ):
                await create_storage(settings)

    def test_reasoning_backend_errors_are_classified_without_raw_exception_text(self) -> None:
        auth_error = type("AuthenticationError", (Exception,), {"status_code": 401})(
            "secret-bearing authentication text"
        )
        quota_error = type("RateLimitError", (Exception,), {"status_code": 429})(
            "raw quota text"
        )
        bad_request = type("BadRequestError", (Exception,), {"status_code": 400})(
            "raw request text"
        )

        settings = SimpleNamespace(reasoning_provider="gemini")
        with patch("aicognitive_mind.api.get_settings", return_value=settings):
            auth_detail = _reasoning_backend_error_detail(auth_error)
            quota_detail = _reasoning_backend_error_detail(quota_error)
            request_detail = _reasoning_backend_error_detail(bad_request)

        self.assertIn("authentication or project permission failed", auth_detail.lower())
        self.assertIn("gemini", auth_detail.lower())
        self.assertIn("quota or rate-limit", quota_detail.lower())
        self.assertIn("rejected", request_detail.lower())
        self.assertNotIn("secret-bearing", auth_detail)
        self.assertNotIn("raw quota", quota_detail)
        self.assertNotIn("raw request", request_detail)

    def test_render_python_version_is_pinned_to_project_major_minor(self) -> None:
        version = Path(".python-version").read_text(encoding="utf-8").strip()
        self.assertEqual(version, "3.12")


if __name__ == "__main__":
    unittest.main()
