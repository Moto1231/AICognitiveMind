from __future__ import annotations

import time
import unittest
from types import SimpleNamespace

from aicognitive_mind.api import (
    read_portal_session,
    revoke_portal_session,
    store_portal_session,
)


class FakeRuntimeRecords:
    def __init__(self) -> None:
        self.values: dict[str, dict] = {}

    async def create(self, key: str, value: dict) -> None:
        if key in self.values:
            raise ValueError("duplicate record")
        self.values[key] = dict(value)

    async def get(self, key: str) -> dict | None:
        value = self.values.get(key)
        return dict(value) if value is not None else None

    async def replace(self, key: str, before: dict, after: dict) -> bool:
        if self.values.get(key) != before:
            return False
        self.values[key] = dict(after)
        return True


class PortalSessionPersistenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_session_can_be_read_after_app_wrapper_is_recreated(self) -> None:
        records = FakeRuntimeRecords()
        first_app = SimpleNamespace(state=SimpleNamespace(runtime_records=records))
        second_app = SimpleNamespace(state=SimpleNamespace(runtime_records=records))
        token = "opaque-session-token"

        await store_portal_session(first_app, token, "mind-123", time.time() + 3600)

        session = await read_portal_session(second_app, token)
        self.assertEqual(session["mind_id"], "mind-123")
        self.assertGreater(session["expires_at"], time.time())

    async def test_revoked_session_is_no_longer_accepted(self) -> None:
        app = SimpleNamespace(state=SimpleNamespace(runtime_records=FakeRuntimeRecords()))
        token = "opaque-session-token"
        await store_portal_session(app, token, "mind-123", time.time() + 3600)

        await revoke_portal_session(app, token)

        self.assertIsNone(await read_portal_session(app, token))

    async def test_expired_session_is_not_accepted(self) -> None:
        app = SimpleNamespace(state=SimpleNamespace(runtime_records=FakeRuntimeRecords()))
        token = "opaque-session-token"
        await store_portal_session(app, token, "mind-123", time.time() - 1)

        self.assertIsNone(await read_portal_session(app, token))


if __name__ == "__main__":
    unittest.main()
