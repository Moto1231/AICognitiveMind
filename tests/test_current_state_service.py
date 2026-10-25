from functools import partial
from aicognitive_mind.memory_steward import MemoryStewardTool
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.domain import CognitiveActor, JournalEntry, JournalKind
from aicognitive_mind.mcp_service import CognitiveMcpService as ProductionMcpService
from aicognitive_mind.host_behaviors import HostBehavior, HostBehaviorRegistry
from aicognitive_mind.core_skills import REQUIRED_SKILLS, load_required_skill
from aicognitive_mind.host_runtime import HostAwareCore, RuntimeRecords
from aicognitive_mind.state_context import apply_current_state_event
from aicognitive_mind.task_model_assignments import TaskModelAssignment, TaskModelAssignmentRegistry
from aicognitive_mind.storage import (
    InMemoryJournalStore,
    InMemoryMemoryStore,
    InMemoryMindStore,
)


CognitiveMcpService = partial(ProductionMcpService, steward_factory=MemoryStewardTool)


class CurrentStateServiceTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.mind = InMemoryMindStore()
        self.journal = InMemoryJournalStore()
        self.memory = InMemoryMemoryStore()
        self.service = CognitiveMcpService(self.mind, self.journal, self.memory)
        await self.service.initialize("Axiom", ("Preserve continuity of identity",))

    async def test_begin_restores_grounded_context_and_read_survives_new_service(self) -> None:
        begun = await self.service.begin_interaction(
            "Continue the state ledger work.",
            {
                "summary": "Implement Axiom's current-state ledger",
                "participants": [
                    {
                        "participant_id": "human",
                        "name": "Human",
                        "identity_status": "confirmed",
                        "presence_status": "reported",
                        "grounding": ["current conversation"],
                    }
                ],
                "active_speaker": "human",
                "addressee": "human",
                "unresolved_references": ["Implement event invalidation"],
            },
        )
        state = begun["current_state"]
        self.assertEqual(state["fields"]["identity"]["value"]["self_name"], "Axiom")
        self.assertEqual(
            state["fields"]["active_topic"]["value"], "Implement Axiom's current-state ledger"
        )
        self.assertEqual(state["fields"]["interlocutor"]["value"]["active_speaker"], "human")
        self.assertEqual(state["fields"]["presence"]["source"], "validated_host_working_context")
        self.assertEqual(state["fields"]["pending_work"]["value"], ["Implement event invalidation"])
        self.assertEqual(state["fields"]["locality"]["status"], "unknown")

        restarted = CognitiveMcpService(self.mind, self.journal, self.memory)
        self.assertEqual(await restarted.read_current_state(), state)

    async def test_active_state_rules_include_only_selected_enabled_reasoning_behaviors(self) -> None:
        records = RuntimeRecords(self.mind)
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace(await assignments.list())
        catalog = HostBehaviorRegistry(records)
        await catalog.replace([
            *await catalog.list(),
            HostBehavior(id="coding-only", name="Coding only", instruction="Coding marker rule."),
            HostBehavior(id="disabled-rule", name="Disabled", instruction="Disabled marker rule.", enabled=False),
        ])
        await assignments.replace([
            item.model_copy(update={"behavior_ids": ["coding-only"]}) if item.task == "coding" else
            item.model_copy(update={"behavior_ids": [*item.behavior_ids, "disabled-rule"]})
            if item.task == "reasoning" else item for item in await assignments.list()
        ])
        begun = await self.service.begin_interaction("Hello.")
        rules = begun["current_state"]["fields"]["behaviors"]["value"]["rules"]
        self.assertEqual({item["id"] for item in rules}, {
            "ground-recalled-context", "verify-capabilities", *REQUIRED_SKILLS,
        })
        self.assertNotIn("Coding marker rule.", begun["conscious_workspace_contract"])
        self.assertNotIn("Disabled marker rule.", begun["conscious_workspace_contract"])

    async def test_skipped_recall_keeps_grounded_procedures_and_records_packaged_protocols(self):
        procedure = {"memory_class": "procedural", "content": "Preserve this grounded procedure."}
        await self.service.update_current_state("state_refreshed", {"values": {"skills": {
            "value": [procedure], "source": "previous_grounded_recall",
        }}})
        service = ProductionMcpService(self.mind, self.journal, self.memory)
        service._steward_runtime = SimpleNamespace(execute=AsyncMock(return_value=json.dumps({
            "action": "finish", "outcome": "no_recall_needed", "reason": "Current context suffices.",
        })))
        begun = await service.begin_interaction("Continue with the supplied context.")
        skills = begun["current_state"]["fields"]["skills"]
        self.assertEqual(skills["status"], "current")
        self.assertEqual({item.get("slug") for item in skills["value"] if item.get("required")}, set(REQUIRED_SKILLS))
        self.assertIn(procedure, skills["value"])
        self.assertIn("host plugin or catalog refresh is not verified", skills["note"])
        for item in skills["value"]:
            if item.get("required"):
                self.assertEqual(item["source"], "packaged_core")
                self.assertNotIn("content", item)
                self.assertEqual(begun["conscious_workspace_contract"].count(load_required_skill(item["slug"])), 1)

    async def test_legacy_ledger_missing_skills_field_is_upgraded_with_packaged_protocols(self):
        ledger = await self.service.read_current_state()
        ledger["fields"].pop("skills")
        await self.journal.append(JournalEntry(kind=JournalKind.CHECKPOINT, experience={
            "checkpoint_type": "current_state_ledger", "state_ledger": ledger,
        }), recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
        begun = await self.service.begin_interaction("Continue with this legacy ledger.")
        skills = begun["current_state"]["fields"]["skills"]
        self.assertEqual(skills["status"], "current")
        self.assertEqual({item["slug"] for item in skills["value"]}, set(REQUIRED_SKILLS))

    async def test_unknown_resolution_notes_survive_unchanged_begins_until_real_events(self):
        fields = ("locality", "current_scene")
        values = {key: {
            "value": None, "status": "unknown", "source": "bounded_current_context_check",
            "note": json.dumps({
                "field": key, "attempts": [{"kind": "current_context_check", "result": "no grounded evidence"}],
                "retry_condition": "new evidence or a state-changing event",
            }),
        } for key in fields}
        seeded = await self.service.update_current_state("state_refreshed", {"values": values})
        expected = {key: seeded["fields"][key] for key in fields}
        service = ProductionMcpService(self.mind, self.journal, self.memory)
        service._steward_runtime = SimpleNamespace(execute=AsyncMock(return_value=json.dumps({
            "action": "finish", "outcome": "no_recall_needed", "reason": "Current context suffices.",
        })))
        for _ in range(2):
            begun = await service.begin_interaction("Continue.", {"summary": "Unchanged current-state check"})
            self.assertEqual(begun["memory_assessment"]["outcome"], "no_recall_needed")
            for key in fields:
                # Whole-answer equality includes source, JSON note and observed_at.
                self.assertEqual(begun["current_state"]["fields"][key], expected[key])
        reloaded = await service.read_current_state()
        self.assertEqual({key: reloaded["fields"][key] for key in fields}, expected)

        for event, affected in (
            ("scene_changed", {"current_scene"}),
            ("location_changed", {"locality", "current_scene"}),
        ):
            seeded = await service.update_current_state("state_refreshed", {"values": values})
            changed = await service.update_current_state(event)
            for key in fields:
                answer = changed["fields"][key]
                if key in affected:
                    self.assertEqual(answer["status"], "unknown")
                    self.assertEqual(answer["source"], "invalidated by event:" + event)
                    self.assertNotEqual(answer["note"], values[key]["note"])
                else:
                    self.assertEqual(answer, seeded["fields"][key])

    async def test_body_endpoint_preserves_sensory_provenance_without_inventing_human_presence(self) -> None:
        dispatcher = SimpleNamespace(
            assignment=AsyncMock(return_value=TaskModelAssignment(task="reasoning", provider="endpoint")),
            complete_chat=AsyncMock(return_value="A grounded visual response."),
        )
        hosts = SimpleNamespace(
            active=AsyncMock(return_value=None), records=RuntimeRecords(self.mind), service=self.service,
        )
        core = SimpleNamespace(interact=AsyncMock())
        sensory_context = {
            "modality": "vision", "source": "browser-camera",
            "evidence": {"sha256": "preserved-evidence-reference"},
            "metadata": {"image_data": "c2VjcmV0"},
        }
        with patch("aicognitive_mind.host_runtime.TaskModelDispatcher", return_value=dispatcher), patch(
            "aicognitive_mind.config.body_allow_standalone_fallback_enabled", return_value=True,
        ):
            result = await HostAwareCore(core, hosts).interact(
                "A camera scene", source="body:vision", input_context=sensory_context,
            )
        self.assertEqual(result.response_text, "A grounded visual response.")
        entries = await self.journal.read()
        entry = next(item for item in reversed(entries) if item.kind == JournalKind.INTERACTION)
        self.assertEqual(entry.experience["input"]["source"], "body:vision")
        self.assertEqual(entry.experience["input"]["context"]["evidence"]["sha256"], "preserved-evidence-reference")
        self.assertEqual(entry.experience["reasoning_runtime"]["source"], "configured_reasoning_endpoint")
        self.assertNotIn("c2VjcmV0", json.dumps([item.model_dump(mode="json") for item in entries]))
        state = await self.service.read_current_state()
        self.assertEqual(state["fields"]["active_topic"]["source"], "body:vision")
        self.assertEqual(state["fields"]["interlocutor"]["status"], "unknown")
        self.assertEqual(state["fields"]["presence"]["status"], "unknown")
        self.assertNotIn("human input received", json.dumps(state))
        core.interact.assert_not_awaited()

    async def test_service_and_external_events_share_latest_exact_checkpoint(self) -> None:
        await self.service.begin_interaction("Start.")
        location = await self.service.update_current_state(
            "location_changed",
            {"values": {"locality": {"value": {"place": "Lab A"}, "source": "user"}}},
        )
        # An unrelated checkpoint can mention the ledger without replacing it.
        await self.journal.append(
            JournalEntry(
                kind=JournalKind.CHECKPOINT,
                experience={
                    "checkpoint_type": "sleep_consolidation",
                    "notes": "Reviewed current_state_ledger",
                },
            ),
            recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
        )
        external = await apply_current_state_event(self.journal, "topic_changed")
        self.assertEqual(external.revision, location["revision"] + 1)
        self.assertEqual(external.fields["locality"].value, {"place": "Lab A"})
        self.assertEqual(external.fields["active_topic"].status, "unknown")
        self.assertEqual(await self.service.read_current_state(), external.as_context())

        next_turn = await self.service.begin_interaction("Continue.", {"summary": "New topic"})
        self.assertEqual(
            next_turn["current_state"]["fields"]["locality"]["value"], {"place": "Lab A"}
        )
        self.assertEqual(next_turn["current_state"]["fields"]["active_topic"]["value"], "New topic")

    async def test_new_host_does_not_reuse_previous_host_participant_presence(self) -> None:
        await self.service.begin_interaction(
            "Hello.",
            {
                "participants": [
                    {
                        "participant_id": "speaker",
                        "name": "Will",
                        "identity_status": "confirmed",
                        "presence_status": "observed",
                        "grounding": ["current direct introduction"],
                    }
                ],
                "active_speaker": "speaker",
            },
        )
        restarted = CognitiveMcpService(self.mind, self.journal, self.memory)
        begun = await restarted.begin_interaction("Hello from a new conversation.")
        presence = begun["current_state"]["fields"]["presence"]
        self.assertEqual(presence["value"]["physical_presence"], "unknown")
        self.assertNotIn("Will", json.dumps(presence))

        await restarted.update_current_state(
            "scene_changed", {"values": {"presence": {"value": ["person"], "source": "camera"}}}
        )
        later = await restarted.begin_interaction("Continue.")
        self.assertEqual(later["current_state"]["fields"]["presence"]["source"], "camera")

    async def test_ledger_reads_use_bounded_lookup_without_reading_journal_history(self) -> None:
        await self.service.begin_interaction("Start.")
        expected = await self.service.read_current_state()
        with (
            patch.object(self.journal, "read", side_effect=AssertionError("unbounded read")),
            patch.object(
                self.journal, "query_page", side_effect=AssertionError("substring search")
            ),
            patch.object(
                self.journal, "latest_checkpoint", wraps=self.journal.latest_checkpoint
            ) as lookup,
        ):
            self.assertEqual(await self.service.read_current_state(), expected)
            updated = await apply_current_state_event(self.journal, "scene_changed")
        self.assertEqual(lookup.await_count, 2)
        self.assertEqual(updated.revision, expected["revision"] + 1)

    async def test_invalid_state_update_does_not_append_a_checkpoint(self) -> None:
        await self.service.begin_interaction("Start.")
        before = await self.journal.read()
        with self.assertRaises(ValueError):
            await self.service.update_current_state(
                "location_changed", {"values": {"invented_field": "invalid"}}
            )
        self.assertEqual(await self.journal.read(), before)

    async def test_begin_checkpoint_redacts_media_without_changing_reasoning_state(self) -> None:
        message = "Look at data:image/png;base64,c2VjcmV0"
        begun = await self.service.begin_interaction(message)
        self.assertEqual(begun["current_state"]["fields"]["active_topic"]["value"], message)
        serialized = json.dumps(
            [entry.model_dump(mode="json") for entry in await self.journal.read()]
        )
        self.assertNotIn("c2VjcmV0", serialized)
        self.assertIn("encoded sensory payload omitted from journal", serialized)

    async def test_concurrent_begin_and_update_cannot_overwrite_a_committed_revision(self) -> None:
        original_lookup = self.journal.latest_checkpoint
        both_read = asyncio.Event()
        reads = 0

        async def overlapping_lookup(checkpoint_type):
            nonlocal reads
            result = await original_lookup(checkpoint_type)
            reads += 1
            if reads == 2:
                both_read.set()
            await both_read.wait()
            return result

        with patch.object(self.journal, "latest_checkpoint", side_effect=overlapping_lookup):
            results = await asyncio.gather(
                self.service.begin_interaction("Start."),
                self.service.update_current_state(
                    "location_changed", {"values": {"locality": "Lab A"}}
                ),
                return_exceptions=True,
            )
        self.assertEqual(sum(isinstance(result, CommitConflict) for result in results), 1)
        checkpoints = await original_lookup("current_state_ledger")
        self.assertEqual(checkpoints[0].experience["state_ledger"]["revision"], 1)
        self.assertEqual(
            sum(entry.kind == JournalKind.CHECKPOINT for entry in await self.journal.read()), 1
        )

    async def test_service_and_external_state_events_redact_nested_media(self) -> None:
        for apply_event in (self.service.update_current_state, apply_current_state_event):
            arguments = (self.journal,) if apply_event is apply_current_state_event else ()
            updates = {
                "values": {
                    "current_scene": {
                        "value": {
                            "image_data": "c2VjcmV0",
                            "evidence_sha256": "preserved-reference",
                        },
                        "source": "preserved evidence",
                    }
                }
            }
            await apply_event(*arguments, "scene_changed", updates)
            latest = await self.journal.latest_checkpoint("current_state_ledger")
            serialized = json.dumps(latest[0].model_dump(mode="json"))
            self.assertNotIn("c2VjcmV0", serialized)
            self.assertIn("preserved-reference", serialized)

    async def test_begin_and_external_event_share_in_memory_commit_coordination(self) -> None:
        original_lookup = self.journal.latest_checkpoint
        begin_read = asyncio.Event()
        event_committed = asyncio.Event()
        reads = 0

        async def overlapping_lookup(checkpoint_type):
            nonlocal reads
            result = await original_lookup(checkpoint_type)
            reads += 1
            if reads == 1:
                begin_read.set()
                await event_committed.wait()
            return result

        async def external_event():
            await begin_read.wait()
            result = await apply_current_state_event(
                self.journal, "location_changed", {"values": {"locality": "Lab A"}}
            )
            event_committed.set()
            return result

        with patch.object(self.journal, "latest_checkpoint", side_effect=overlapping_lookup):
            results = await asyncio.gather(
                self.service.begin_interaction("Start."),
                external_event(),
                return_exceptions=True,
            )
        self.assertIsInstance(results[0], CommitConflict)
        self.assertNotIsInstance(results[1], Exception)
        checkpoints = await original_lookup("current_state_ledger")
        self.assertEqual(checkpoints[0].experience["state_ledger"]["revision"], 1)
        self.assertEqual(
            checkpoints[0].experience["state_ledger"]["fields"]["locality"]["value"], "Lab A"
        )
        resumed = await self.service.begin_interaction("Start.")
        self.assertEqual(resumed["current_state"]["revision"], 2)
        self.assertEqual(resumed["current_state"]["fields"]["locality"]["value"], "Lab A")

    async def test_ledger_revisions_do_not_advance_naming_experience_threshold(self) -> None:
        for _ in range(998):
            await self.journal.append(
                JournalEntry(kind=JournalKind.INTERACTION, experience={"input": "experience"}),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
        await self.service.begin_interaction("Start.")
        await self.service.update_current_state("topic_changed")
        before = await self.service.status()
        self.assertEqual(before["journal_experience_count"], 999)
        self.assertEqual(before["naming"]["status"], "prohibited")
        await self.service.complete_interaction("Continue.", "Continuing.")
        after = await self.service.status()
        self.assertEqual(after["journal_experience_count"], 1000)
        self.assertEqual(after["naming"]["status"], "eligible")


if __name__ == "__main__":
    unittest.main()
