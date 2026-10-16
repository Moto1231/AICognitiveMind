import unittest

from aicognitive_mind.state_context import CurrentStateLedger


class CurrentStateLedgerTests(unittest.TestCase):
    def test_location_event_invalidates_only_location_and_scene(self) -> None:
        ledger = CurrentStateLedger.empty()
        ledger.answer("identity", {"self_name": "Axiom"}, source="mind")
        ledger.answer("locality", {"place": "Lab A"}, source="sensor")
        ledger.answer("active_topic", "memory architecture", source="conversation")

        updated = ledger.apply_event("location_changed")

        self.assertEqual(updated.fields["identity"].value, {"self_name": "Axiom"})
        self.assertEqual(updated.fields["locality"].status, "unknown")
        self.assertIsNone(updated.fields["locality"].value)
        self.assertEqual(updated.fields["active_topic"].value, "memory architecture")
        self.assertEqual(updated.last_event, "location_changed")

    def test_event_can_supply_grounded_values_after_invalidation(self) -> None:
        ledger = CurrentStateLedger.empty()
        ledger.answer("locality", {"place": "old place"}, source="old sensor")

        updated = ledger.apply_event(
            "location_changed",
            {
                "values": {
                    "locality": {
                        "value": {"place": "new place"},
                        "source": "fresh location sensor",
                        "status": "current",
                    }
                }
            },
        )

        self.assertEqual(updated.fields["locality"].value, {"place": "new place"})
        self.assertEqual(updated.fields["locality"].source, "fresh location sensor")
        self.assertEqual(updated.fields["locality"].status, "current")

    def test_unknown_is_explicit_and_invalid_events_are_rejected(self) -> None:
        ledger = CurrentStateLedger.empty()
        self.assertEqual(ledger.fields["interlocutor"].status, "unknown")
        with self.assertRaises(ValueError):
            ledger.apply_event("invented_event")

    def test_each_event_invalidates_only_its_declared_answers(self) -> None:
        expected = {
            "session_started": {"interlocutor", "presence", "active_topic", "active_task"},
            "location_changed": {"locality", "current_scene"},
            "speaker_changed": {"interlocutor", "presence", "who_is_speaking"},
            "topic_changed": {"active_topic", "current_context", "decisions_and_open_questions"},
            "task_changed": {"active_task", "pending_work"},
            "connection_changed": {"connection_status", "capabilities", "pending_work"},
            "scene_changed": {"current_scene", "presence", "who_is_present"},
            "begin_context": set(),
            "evidence_conflict": set(),
            "state_refreshed": set(),
        }
        original = CurrentStateLedger.empty()
        for key in original.FUNDAMENTAL_FIELDS:
            original.answer(key, f"grounded {key}", source="grounded observation")
        for event, affected in expected.items():
            with self.subTest(event=event):
                updated = original.apply_event(event)
                self.assertEqual(updated.revision, original.revision + 1)
                for key in original.FUNDAMENTAL_FIELDS:
                    if key in affected:
                        self.assertEqual(updated.fields[key].status, "unknown")
                        self.assertIsNone(updated.fields[key].value)
                    else:
                        self.assertEqual(updated.fields[key], original.fields[key])

    def test_evidence_conflict_marks_only_named_field_unknown_or_disputed(self) -> None:
        ledger = CurrentStateLedger.empty()
        ledger.answer("presence", [{"name": "Candidate"}], source="camera")
        ledger.answer("identity", {"self_name": "Axiom"}, source="mind")

        updated = ledger.apply_event(
            "evidence_conflict",
            {
                "values": {
                    "presence": {
                        "value": [{"name": "Candidate A"}, {"name": "Candidate B"}],
                        "source": "conflicting sensory evidence",
                        "status": "disputed",
                        "note": "Two observations disagree.",
                    }
                }
            },
        )

        self.assertEqual(updated.fields["presence"].status, "disputed")
        self.assertEqual(updated.fields["identity"].value, {"self_name": "Axiom"})


if __name__ == "__main__":
    unittest.main()
