import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pydantic import ValidationError

from aicognitive_mind.body_sessions import BodySessionHeartbeat, active_body_status


CLIENT_STATE = {
    "client_revision": "20261027-host-recovery", "hearing": True, "voice": True,
    "page_visible": True, "microphone_live": True, "microphone_enabled": False,
    "voice_mode": "connected_host", "last_playback": "started",
}


class BodyClientStateTests(unittest.IsolatedAsyncioTestCase):
    def records(self, value):
        return SimpleNamespace(get=AsyncMock(return_value=value))

    def test_heartbeat_accepts_only_bounded_operational_fields(self):
        report = BodySessionHeartbeat.model_validate({"client_state": CLIENT_STATE})
        self.assertEqual(report.client_state.model_dump(exclude_none=True), CLIENT_STATE)
        self.assertIsNone(BodySessionHeartbeat.model_validate({}).client_state)
        for invalid in (
            {"extra": "not allowed"}, {"client_state": {"error": "private content"}},
            {"client_state": {"audio_data_url": "data:audio/webm;base64,AAAA"}},
            {"client_state": {"hearing": "true"}}, {"client_state": {"voice": 1}},
            {"client_state": {"client_revision": "a" * 65}},
            {"client_state": {"client_revision": "not\na revision"}},
            {"client_state": {"voice_mode": "other"}},
            {"client_state": {"last_playback": "raw error text"}},
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValidationError):
                BodySessionHeartbeat.model_validate(invalid)

    async def test_fresh_state_is_explicitly_client_reported_without_session_identifier(self):
        records = self.records({"session_id": "private-body-session", "updated_at": 950, "client_state": CLIENT_STATE})
        report = await active_body_status(records, now=1000)
        self.assertEqual(report, {
            "fresh": True, "last_heartbeat_age_seconds": 50.0,
            "client_state": CLIENT_STATE, "client_state_source": "client_reported",
        })
        self.assertNotIn("private-body-session", str(report))
        records.get.assert_awaited_once_with("active_body_session")

    async def test_stale_registration_does_not_expose_current_client_state(self):
        records = self.records({"session_id": "named", "updated_at": 879, "client_state": CLIENT_STATE})
        report = await active_body_status(records, now=1000)
        self.assertFalse(report["fresh"])
        self.assertEqual(report["last_heartbeat_age_seconds"], 121)
        self.assertIsNone(report["client_state"])
        self.assertIsNone(report["client_state_source"])
        records.get.return_value["updated_at"] = 880
        self.assertTrue((await active_body_status(records, now=1000))["fresh"])

    async def test_legacy_report_and_invalid_stored_fields_are_not_promoted(self):
        for active in (
            None, {"session_id": "legacy", "updated_at": 990},
            {"session_id": "named", "updated_at": float("nan")},
            {"session_id": "named", "updated_at": True},
        ):
            with self.subTest(active=active):
                self.assertIsNone(await active_body_status(self.records(active), now=1000))
        for state in (None, {**CLIENT_STATE, "api_key": "must not be exposed"}):
            with self.subTest(state=state):
                report = await active_body_status(self.records({
                    "session_id": "named", "updated_at": 990, "client_state": state,
                }), now=1000)
                self.assertTrue(report["fresh"])
                self.assertIsNone(report["client_state"])
                self.assertNotIn("must not be exposed", str(report))


if __name__ == "__main__":
    unittest.main()
