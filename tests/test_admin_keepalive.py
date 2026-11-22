import unittest
from unittest.mock import patch

import httpx

from aicognitive_mind.api import app


class AdminKeepaliveTests(unittest.IsolatedAsyncioTestCase):
    async def test_ping_is_empty_public_and_does_not_require_runtime(self):
        # Deliberately do not start the application lifespan or a storage backend.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            with patch("aicognitive_mind.api.app_access_authorized", return_value=False):
                response = await client.get("/ping")
                protected = await client.get("/v1/portal/status")

        self.assertEqual(protected.status_code, 401)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers.get("cache-control"), "no-store")
