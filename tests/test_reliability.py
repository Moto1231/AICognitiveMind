import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock

import httpx

from aicognitive_mind.body import BrowserVoiceOutput, ExpressionIntent, ExpressionModality
from aicognitive_mind.body_sessions import BodyQueue, body_session
from aicognitive_mind.commit import CommitConflict, commit
from aicognitive_mind.config import Settings
from aicognitive_mind.domain import CognitiveActor, CognitiveMind, MemoryClass, MindIdentity
from aicognitive_mind.governance_steward import GovernanceStewardTool
from aicognitive_mind.host_runtime import HostRuntime, RuntimeRecords
from aicognitive_mind.mcp_server import McpTokenAuth
from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.standalone import ProviderUnavailable, StandaloneRuntime
from aicognitive_mind.surreal_storage import (
    SurrealJournalStore,
    SurrealMemoryStore,
    SurrealMindStore,
    SurrealRuntime,
)


class ReliabilityTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.runtime = SurrealRuntime("mem://", "test", "reliability")
        await self.runtime.initialize()
        self.mind = SurrealMindStore(self.runtime.database)
        self.memory = SurrealMemoryStore(self.runtime.database)
        self.journal = SurrealJournalStore(self.runtime.database)
        self.service = CognitiveMcpService(self.mind, self.journal, self.memory)
        await self.service.initialize("Axiom")

    async def asyncTearDown(self):
        await self.runtime.close()

    async def test_negation_quotation_and_questions_cannot_rename(self):
        for message in [
            "Do not choose a new name",
            "Explain how you choose your name",
            'Say "choose a new name"',
            "If you could choose a new name, what would it be?",
            "Choose a name for the dog",
            "Please choose a new name, but do not change it",
        ]:
            tool = GovernanceStewardTool(mind=self.mind, journal=self.journal, input_text=message)
            result = await tool.invoke(
                {"action": "propose_self_name", "candidate_name": "Changed", "rationale": "test"}
            )
            self.assertFalse(result["accepted"], message)
        self.assertEqual((await self.mind.load()).identity.self_name, "Axiom")

    async def test_receipt_retries_commit_once_and_reject_different_payload(self):
        proposal = MemoryProposal(
            memory_class=MemoryClass.SEMANTIC, content="Atlas uses SurrealDB.", grounding=("user",)
        )
        first = await self.service.complete_interaction(
            "Remember Atlas", "Remembered", (proposal,), idempotency_key="turn-1"
        )
        second = await self.service.complete_interaction(
            "Remember Atlas", "Remembered", (proposal,), idempotency_key="turn-1"
        )
        self.assertEqual(first, second)
        self.assertEqual(len(await self.memory.read()), 1)
        self.assertEqual(len(await self.journal.read()), 2)
        with self.assertRaises(CommitConflict):
            await self.service.complete_interaction(
                "Remember Atlas", "Different", idempotency_key="turn-1"
            )

    async def test_late_transaction_failure_rolls_back_prior_write(self):
        original = await self.mind.load()
        replacement = original.model_copy(update={"identity": MindIdentity(self_name="Changed")})
        bad_original = original.model_copy(update={"identity": MindIdentity(self_name="Missing")})
        with self.assertRaises(Exception):
            await commit(
                {"mind": self.mind},
                [
                    ("mind", "replace", original, replacement),
                    ("mind", "replace", bad_original, original),
                ],
                None,
                {},
            )
        self.assertEqual(await self.mind.load(), original)

    async def test_concurrent_revisions_only_one_wins(self):
        original = await self.mind.load()

        async def rename(name):
            replacement = original.model_copy(update={"identity": MindIdentity(self_name=name)})
            return await self.mind.replace_exact(
                original, replacement, CognitiveActor.VALUES_STEWARD
            )

        results = await asyncio.gather(rename("One"), rename("Two"), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, CognitiveMind) for r in results), 1)

    async def test_host_handoff_routes_body_and_rejects_old_lease(self):
        host_a = HostRuntime(self.mind, self.service, timeout=3)
        host_b = HostRuntime(SurrealMindStore(self.runtime.database), self.service, timeout=3)
        lease_a = await host_a.attach("host-a", "model-a")
        pending = asyncio.create_task(host_a.submit("Hello from Body"))
        request = None
        for _ in range(30):
            request = await host_b.next_request(lease_a["lease_token"])
            if request:
                break
            await asyncio.sleep(0.01)
        self.assertIsNotNone(request)
        result = await host_b.complete(lease_a["lease_token"], request["request_id"], "Hello")
        self.assertEqual(await pending, result)
        await host_a.renew(lease_a["lease_token"], detach=True)
        lease_b = await host_b.attach("host-b", "model-b")
        with self.assertRaises(PermissionError):
            await host_a.next_request(lease_a["lease_token"])
        self.assertEqual((await host_b.active())["model"], "model-b")
        await host_b.renew(lease_b["lease_token"], detach=True)

    async def test_body_queues_are_isolated_fifo_across_instances(self):
        first = BodyQueue(RuntimeRecords(self.mind), "mouth", BrowserVoiceOutput())
        second = BodyQueue(
            RuntimeRecords(SurrealMindStore(self.runtime.database)), "mouth", BrowserVoiceOutput()
        )
        token = body_session.set("body-a")
        try:
            await first.speak(ExpressionIntent(modality=ExpressionModality.VOICE, text="one"))
            await first.speak(ExpressionIntent(modality=ExpressionModality.VOICE, text="two"))
            body_session.set("body-b")
            self.assertIsNone(await second.consume())
            body_session.set("body-a")
            self.assertEqual((await second.consume()).text, "one")
            self.assertEqual((await first.consume()).text, "two")
        finally:
            body_session.reset(token)

    async def test_fallback_is_lazy_and_quota_failure_opens_circuit(self):
        fallback = StandaloneRuntime(
            Settings(_env_file=None, standalone_reasoning_provider="disabled")
        )
        self.assertIsNone(fallback.engine)
        with self.assertRaises(ProviderUnavailable):
            await fallback.propose(None)
        settings = Settings(_env_file=None, standalone_reasoning_provider="echo")
        fallback = StandaloneRuntime(settings)
        error = type("Quota", (Exception,), {"status_code": 429})("quota")
        fallback.engine = AsyncMock()
        fallback.engine.propose.side_effect = error
        with self.assertRaises(type(error)):
            await fallback.propose(None)
        with self.assertRaises(ProviderUnavailable):
            await fallback.propose(None)
        self.assertEqual(fallback.engine.propose.await_count, 1)

    async def test_http_auth_rejects_before_dispatch(self):
        async def endpoint(scope, receive, send):
            from starlette.responses import Response

            await Response("authorized")(scope, receive, send)

        app = McpTokenAuth(endpoint, "test-token")
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://localhost"
        ) as client:
            self.assertEqual((await client.post("/mcp")).status_code, 401)
            self.assertEqual(
                (await client.post("/mcp", headers={"Authorization": "Bearer wrong"})).status_code,
                401,
            )
            self.assertEqual(
                (
                    await client.post("/mcp", headers={"Authorization": "Bearer test-token"})
                ).status_code,
                200,
            )


class PersistentRestartTests(unittest.IsolatedAsyncioTestCase):
    async def test_identity_relationships_memory_and_receipts_survive_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            uri = "surrealkv://" + str(Path(directory) / "mind").replace("\\", "/")
            runtime = SurrealRuntime(uri, "test", "restart")
            await runtime.initialize()
            mind = SurrealMindStore(runtime.database)
            journal, memory = (
                SurrealJournalStore(runtime.database),
                SurrealMemoryStore(runtime.database),
            )
            service = CognitiveMcpService(mind, journal, memory)
            await service.initialize("Axiom", ("Continuity",))
            original = await mind.load()
            updated = original.model_copy(
                update={
                    "identity": original.identity.model_copy(
                        update={"relationships": ({"name": "Will", "role": "creator"},)}
                    )
                }
            )
            await mind.replace_exact(original, updated, CognitiveActor.VALUES_STEWARD)
            proposal = MemoryProposal(
                memory_class=MemoryClass.SEMANTIC,
                content="Atlas uses SurrealDB.",
                grounding=("direct user statement",),
            )
            first = await service.complete_interaction(
                "Remember Atlas", "Saved", (proposal,), idempotency_key="restart-turn"
            )
            await runtime.close()
            runtime = SurrealRuntime(uri, "test", "restart")
            await runtime.initialize()
            try:
                service = CognitiveMcpService(
                    SurrealMindStore(runtime.database),
                    SurrealJournalStore(runtime.database),
                    SurrealMemoryStore(runtime.database),
                )
                resumed = await service.begin_interaction("Atlas")
                self.assertEqual(resumed["mind"], updated.model_dump(mode="json"))
                self.assertEqual(len(resumed["recalled_context"]["durable_memory"]), 1)
                retried = await service.complete_interaction(
                    "Remember Atlas", "Saved", (proposal,), idempotency_key="restart-turn"
                )
                self.assertEqual(retried, first)
                await service.complete_interaction(
                    "Continue", "Still Axiom", idempotency_key="second-host"
                )
                self.assertEqual((await service.status())["journal_experience_count"], 3)
            finally:
                await runtime.close()
