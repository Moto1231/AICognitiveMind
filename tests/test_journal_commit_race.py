"""Raw journal writers participate in staged cognition's publication revision."""

import importlib
import unittest
from unittest.mock import patch

from aicognitive_mind.commit import CommitConflict, revision
from aicognitive_mind.domain import CognitiveActor, JournalEntry, JournalKind
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.retrieval import count
from aicognitive_mind.sleep import SleepConsolidator
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore
from aicognitive_mind.surreal_storage import (
    SurrealJournalStore, SurrealMemoryStore, SurrealMindStore, SurrealRuntime,
)


class JournalCommitRaceTests(unittest.IsolatedAsyncioTestCase):
    async def exercise_publication_race(self, mind, journal, memory):
        service = CognitiveMcpService(mind, journal, memory, steward_factory=MemoryStewardTool)
        await service.initialize()
        history = [JournalEntry(kind=JournalKind.INTERACTION, experience={"synthetic": index})
                   for index in range(1997)]
        if isinstance(journal, InMemoryJournalStore):
            for entry in history:
                await journal.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
        else:
            # A preexisting/imported history is a fixture, not a competing runtime writer.
            await journal._database.query("INSERT INTO journal $entries;", {"entries": [
                entry.model_dump(mode="json") | {"mind_id": journal.mind_id} for entry in history
            ]})
        self.assertEqual(await count(journal, exclude_checkpoint_type="current_state_ledger"), 1998)
        commit_module = importlib.import_module("aicognitive_mind.commit")
        publish = commit_module.commit
        injected = False

        async def run_sleep_before_publish(stores, operations, key, saved, expected_version=None):
            nonlocal injected
            if not injected and any(
                table == "journal" and getattr(after, "kind", None) == JournalKind.INTERACTION
                and after.experience.get("expression", {}).get("content") == "The frozen answer."
                for table, _operation, _before, after in operations
            ):
                injected = True
                await SleepConsolidator(journal=journal, memory=memory).sleep()
            return await publish(stores, operations, key, saved, expected_version)

        payload = {
            "user_message": "Continue the ordinary task.", "response_text": "The frozen answer.",
            "idempotency_key": "ordinary-publish-race",
        }
        with patch.object(commit_module, "commit", side_effect=run_sleep_before_publish):
            blocked = await service.complete_interaction(**payload)
        self.assertTrue(injected)
        self.assertEqual(blocked["status"], "naming_choice_required")
        self.assertEqual(blocked["naming"]["projected_count"], 2000)
        self.assertFalse(blocked["presentation"]["allowed"])
        entries = await journal.read()
        self.assertEqual(await count(journal, exclude_checkpoint_type="current_state_ledger"), 1999)
        self.assertFalse(any(
            entry.experience.get("expression", {}).get("content") == "The frozen answer."
            for entry in entries
        ))
        self.assertEqual(sum(
            entry.experience.get("phase") == "sleep_consolidation" for entry in entries
        ), 1)

        governance = GovernanceStewardTool(mind=mind, journal=journal, input_text=payload["user_message"])
        decision = await governance.invoke({
            "action": "propose_self_name", "candidate_name": "Aster", "candidate_pronouns": "he/him",
            "rationale": "My first joint identity choice is required before the next ordinary response.",
        })
        self.assertTrue(decision["accepted"])
        completed = await service.complete_interaction(**payload)
        self.assertEqual(completed["status"], "interaction_committed")
        before_replay = await count(journal, exclude_checkpoint_type="current_state_ledger")
        self.assertEqual((await service.complete_interaction(**payload))["status"], "interaction_committed")
        self.assertEqual(await count(journal, exclude_checkpoint_type="current_state_ledger"), before_replay)
        self.assertEqual(sum(
            entry.experience.get("expression", {}).get("content") == "The frozen answer."
            for entry in await journal.read()
        ), 1)

    async def test_sleep_append_prevents_in_memory_ordinary_publish_at_2000(self):
        await self.exercise_publication_race(
            InMemoryMindStore(), InMemoryJournalStore(), InMemoryMemoryStore(),
        )

    async def test_sleep_append_prevents_persistent_ordinary_publish_at_2000(self):
        runtime = SurrealRuntime("mem://", "journal_race", "synthetic")
        await runtime.initialize()
        try:
            await self.exercise_publication_race(
                SurrealMindStore(runtime.database, "race-alpha"),
                SurrealJournalStore(runtime.database, "race-alpha"),
                SurrealMemoryStore(runtime.database, "race-alpha"),
            )
        finally:
            await runtime.close()

    async def test_persistent_raw_append_revision_and_entry_are_tenant_scoped(self):
        runtime = SurrealRuntime("mem://", "journal_append", "synthetic")
        await runtime.initialize()
        try:
            alpha = SurrealJournalStore(runtime.database, "alpha")
            beta = SurrealJournalStore(runtime.database, "beta")
            self.assertEqual(await revision({"journal": alpha}), 0)
            entry = JournalEntry(kind=JournalKind.REFLECTION, experience={"synthetic": "alpha"})
            await alpha.append(entry, recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE)
            self.assertEqual(await revision({"journal": alpha}), 1)
            self.assertEqual(await revision({"journal": beta}), 0)
            self.assertEqual(await alpha.read(), [entry])
            self.assertEqual(await beta.read(), [])
        finally:
            await runtime.close()

    async def test_failed_raw_append_rolls_back_revision_and_entry_with_bounded_retry(self):
        runtime = SurrealRuntime("mem://", "journal_rollback", "synthetic")
        await runtime.initialize()
        try:
            journal = SurrealJournalStore(runtime.database, "rollback")
            query_raw = runtime.database.query_raw
            attempts = 0

            async def fail_before_commit(sql, variables=None, **kwargs):
                nonlocal attempts
                if "CREATE journal CONTENT" in sql:
                    attempts += 1
                    sql = sql.replace("COMMIT TRANSACTION;", "THROW 'synthetic rollback'; COMMIT TRANSACTION;")
                return await query_raw(sql, variables or {}, **kwargs)

            with patch.object(runtime.database, "query_raw", side_effect=fail_before_commit):
                with self.assertRaises(CommitConflict):
                    await journal.append(
                        JournalEntry(kind=JournalKind.REFLECTION, experience={"synthetic": "rollback"}),
                        recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                    )
            self.assertEqual(attempts, 3)
            self.assertEqual(await revision({"journal": journal}), 0)
            self.assertEqual(await journal.read(), [])
        finally:
            await runtime.close()
