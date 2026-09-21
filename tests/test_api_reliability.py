import unittest
from unittest.mock import patch

import httpx

from aicognitive_mind.api import app, lifespan
from aicognitive_mind.config import Settings


class ApiReliability(unittest.IsolatedAsyncioTestCase):
    async def test_disabled_fallback_boots_and_body_delivery_requires_matching_session_ack(self):
        settings = Settings(
            _env_file=None,
            storage_provider="surreal",
            surrealdb_uri="mem://",
            standalone_reasoning_provider="disabled",
            app_access_password=None,
        )
        with patch("aicognitive_mind.api.get_settings", return_value=settings):
            async with lifespan(app):
                async with httpx.AsyncClient(
                    transport=httpx.ASGITransport(app), base_url="http://localhost"
                ) as client:
                    self.assertEqual((await client.get("/health")).status_code, 200)
                    response = await client.post("/v1/mind/initialize", json={"self_name": "Axiom"})
                    self.assertEqual(response.status_code, 201, response.text)
                    self.assertFalse(
                        (await client.get("/v1/portal/status")).json()["reasoning"][
                            "fallback_enabled"
                        ]
                    )
                    headers = {"X-Body-Session": "one"}
                    response = await client.post(
                        "/v1/body/mouth/speak", headers=headers, json={"text": "First"}
                    )
                    self.assertLess(response.status_code, 300, response.text)
                    response = await client.get("/v1/body/mouth/next", headers=headers)
                    receipt = response.headers["X-Body-Delivery"]
                    self.assertEqual(response.json()["text"], "First")
                    self.assertEqual(
                        (await client.get("/v1/body/mouth/next", headers=headers)).headers[
                            "X-Body-Delivery"
                        ],
                        receipt,
                    )
                    self.assertIsNone(
                        (
                            await client.get(
                                "/v1/body/mouth/next", headers={"X-Body-Session": "two"}
                            )
                        ).json()
                    )
                    await client.post(
                        "/v1/body/mouth/ack",
                        headers={"X-Body-Session": "two"},
                        params={"delivery_id": receipt},
                    )
                    self.assertIsNotNone(
                        (await client.get("/v1/body/mouth/next", headers=headers)).json()
                    )
                    await client.post(
                        "/v1/body/mouth/ack", headers=headers, params={"delivery_id": receipt}
                    )
                    self.assertIsNone(
                        (await client.get("/v1/body/mouth/next", headers=headers)).json()
                    )
                    backup = await client.get("/v1/admin/backup")
                    self.assertEqual(
                        backup.status_code, 200, backup.text if backup.status_code != 200 else ""
                    )
                    self.assertTrue(backup.content.startswith(b"PK"))
