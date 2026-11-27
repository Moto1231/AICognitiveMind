import asyncio
import json
from datetime import UTC, datetime, timedelta

import unittest
from unittest.mock import patch

from aicognitive_mind.domain import CognitiveActor, CognitiveMind, JournalEntry, JournalKind, MindIdentity
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.journal_review import (
    JournalReviewRunner,
    interaction_speaker,
    journal_review_key,
)
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.steward_agent import StewardProtocolError
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore

NOW = datetime(2026, 11, 27, 18, tzinfo=UTC)
USER_TEXT = "I am in my room now. For all future reports, use the regional columns."


class Journal(InMemoryJournalStore):
    reads = 0

    async def query_page(self, **kwargs):
        self.reads += 1
        return await super().query_page(**kwargs)


class Runtime:
    fail_audit = False
    invalid_quote = False
    memory_calls = 0
    speaker = None
    audit_calls = 0

    async def execute(self, ctx, payload):
        assert ctx.task == "memory_recall"
        system, user = payload["messages"][:2]
        context = json.loads(user["content"])
        if "observation" in context:
            self.audit_calls += 1
            if self.fail_audit:
                raise RuntimeError("offline")
            assert "Independently compare" in system["content"]
            assert context["observation"] == USER_TEXT
            return json.dumps({"findings": [{
                "field": "locality", "issue": "missed",
                "quote": "invented" if self.invalid_quote else "I am in my room now.",
                "reason": "The journal report was not in the ledger.",
            }]})
        self.memory_calls += 1
        self.speaker = context["host_working_context"]["original_speaker"]
        assert "Independently look for durable" in system["content"]
        assert context["user_message"] == USER_TEXT
        return json.dumps({
            "action": "finish", "reason": "Save the standing reporting preference.",
            "memories": [{
                "memory_class": "procedural", "content": "Use regional columns in future reports.",
                "support": [{"source": "user_message", "quote": "use the regional columns"}],
            }],
        })


async def setup():
    mind, journal, memory = InMemoryMindStore(), Journal(), InMemoryMemoryStore()
    await mind.initialize(CognitiveMind(identity=MindIdentity(self_name="Axiom", pronouns="she/her")))
    service = CognitiveMcpService(mind, journal, memory)
    service._steward_runtime = Runtime()
    entry = JournalEntry(
        kind=JournalKind.INTERACTION, occurred_at=NOW - timedelta(minutes=10),
        experience={
            "input": {"source": "human", "content": USER_TEXT},
            "interaction_speaker": {"name": "Example Speaker", "status": "confirmed"},
            "expression": {"content": "Understood."},
            "memory_steward": {"assessment": {"outcome": "reviewed"}},
            "current_state_snapshot": {"locality": {"status": "unknown"}},
        },
    )
    await journal.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
    records = RuntimeRecords(mind)
    return service, journal, memory, entry, records


class JournalReviewTests(unittest.TestCase):
    def test_shared_scan_and_independent_restart_checkpoint(self):
        async def scenario():
            service, journal, memory, entry, records = await setup()
            runtime = service._steward_runtime
            runtime.fail_audit = True
            runner = JournalReviewRunner(service, journal, records)
            assert await runner.run_once(now=NOW) == {"current_state_review": 0, "memory_review": 1}
            assert journal.reads == 1
            assert len(await memory.read()) == 1
            assert runtime.memory_calls == 1
            runtime.fail_audit = False
            # Restart the worker: successful lane is not repeated, even for a previously reviewed turn.
            runner = JournalReviewRunner(service, journal, records)
            assert await runner.run_once(now=NOW) == {"current_state_review": 1, "memory_review": 0}
            assert runtime.memory_calls == 1
            report = await records.get("journal_review_current_state_review")
            assert report["findings"][0]["journal_reference"] == journal_review_key(entry)
            assert report["findings"][0]["field"] == "locality"
            assert (await service.read_current_state())["fields"]["locality"]["value"] is None
            assert len(await journal.read()) == 1
            assert await runner.run_once(now=NOW) == {"current_state_review": 0, "memory_review": 0}
        asyncio.run(scenario())


    def test_unsupported_state_quote_and_repeated_memory_commit(self):
        async def scenario():
            service, _, memory, entry, _ = await setup()
            key = journal_review_key(entry)
            service._steward_runtime.invalid_quote = True
            with self.assertRaisesRegex(StewardProtocolError, "unsupported evidence"):
                await service.review_journal_entry("current_state_review", entry, idempotency_key=key)
            await service.review_journal_entry("memory_review", entry, idempotency_key=key)
            await service.review_journal_entry("memory_review", entry, idempotency_key=key)
            rows = await memory.read()
            assert len(rows) == 1
            assert f"journal:{key}" in rows[0].grounding
            assert service._steward_runtime.speaker == {"name": "Example Speaker", "status": "confirmed"}
            assert any(artifact.kind == "journal_speaker" and artifact.payload == {
                "name": "Example Speaker", "journal_reference": key,
            } for artifact in rows[0].artifacts)
        asyncio.run(scenario())


    def test_slow_provider_never_blocks_conversational_begin(self):
        async def scenario():
            service, journal, _, _, records = await setup()
            entered, released = asyncio.Event(), asyncio.Event()
            real_runtime = service._steward_runtime

            class Slow(Runtime):
                async def execute(self, context, payload):
                    data = json.loads(payload["messages"][1]["content"])
                    if data.get("phase") == "recall":
                        return json.dumps({"action": "finish", "outcome": "no_recall_needed",
                                           "reason": "Nothing relevant for this chat."})
                    entered.set()
                    await released.wait()
                    return await real_runtime.execute(context, payload)

            service._steward_runtime = Slow()
            run = asyncio.create_task(JournalReviewRunner(service, journal, records).run_once(now=NOW))
            try:
                await asyncio.wait_for(entered.wait(), 1)
                response = await asyncio.wait_for(service.begin_interaction("Hello"), 1)
                assert response["status"] == "ready_to_reason"
                assert not run.done()
            finally:
                released.set()
                await run
        asyncio.run(scenario())


    def test_speaker_requires_grounding_on_this_interaction(self):
        participant = {
            "participant_id": "session-person",
            "name": "Example Speaker",
            "identity_status": "confirmed",
            "grounding": ["Current authenticated sender"],
        }
        assert interaction_speaker({"participants": [participant]}) == {"status": "unknown"}
        context = {"active_speaker": "session-person", "participants": [participant]}
        assert interaction_speaker(context) == {"name": "Example Speaker", "status": "confirmed"}
        participant["identity_status"] = "candidate"
        assert interaction_speaker(context) == {"status": "unknown"}


    def test_findings_disappear_when_newer_evidence_exists(self):
        from aicognitive_mind.config import Settings
        from aicognitive_mind.state_context import CurrentStateLedger

        async def scenario():
            service, journal, _, _, records = await setup()
            await JournalReviewRunner(service, journal, records).run_once(now=NOW)
            ledger = CurrentStateLedger.empty()
            ledger.fields["locality"].observed_at = NOW - timedelta(minutes=20)
            findings = await service._pending_state_review(ledger)
            assert len(findings["current_state_review"]["findings"]) == 1
            ledger.fields["locality"].observed_at = NOW
            assert await service._pending_state_review(ledger) == {}

        with patch("aicognitive_mind.config.get_settings", return_value=Settings(
            journal_review_interval_seconds=60, journal_review_mind_id="root",
        )):
            asyncio.run(scenario())
