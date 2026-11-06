import asyncio
import json
import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.domain import CognitiveActor, CognitiveMind, JournalEntry, JournalKind, MindIdentity
from aicognitive_mind.governance_steward import GovernanceStewardTool, ProposeSelfNameCall
from aicognitive_mind.host_context import HostWorkingContext
from aicognitive_mind.host_runtime import HostAwareCore, HostRuntime
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.memory_steward import MemoryStewardTool
from aicognitive_mind.naming import naming_assessment
from aicognitive_mind.reference_host import CognitiveMindHost, HostReasoningResult, OpenAIHostReasoner
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore


CHOICE = {
    "action": "propose_self_name", "candidate_name": "Aster", "candidate_pronouns": "he/him",
    "rationale": "A considered initial name and pronoun choice for this Mind.",
}


async def assessment(experiences):
    return await naming_assessment(
        CognitiveMind(identity=MindIdentity()), InMemoryJournalStore(), experience_count=experiences,
    )


class NamingClient:
    def __init__(self, naming, *, blocked_once=False):
        self.naming = naming
        self.blocked_once = blocked_once
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, deepcopy(arguments)))
        if name == "begin_interaction":
            result = {
                "status": "ready_to_reason", "idempotency_key": "frozen-turn",
                "host_working_context": arguments["host_working_context"],
                "mind": {"identity": {"self_name": None, "pronouns": None}},
                "naming": self.naming,
            }
        elif name == "propose_self_name":
            result = {
                "accepted": True, "current_name": arguments["candidate_name"],
                "current_pronouns": arguments["candidate_pronouns"],
            }
        elif name == "complete_interaction":
            if self.blocked_once:
                self.blocked_once = False
                result = {
                    "status": "naming_choice_required", "naming": await assessment(1999),
                    "presentation": {"allowed": False},
                }
            else:
                result = {
                    "status": "interaction_committed", "presentation": {"allowed": True},
                    "host_working_context": arguments["host_working_context"],
                }
        else:
            raise AssertionError(name)
        return SimpleNamespace(is_error=False, structured_content=result, content=[])


class SequenceReasoner:
    def __init__(self, results):
        self.results = list(results)
        self.contexts = []

    async def reason(self, user_message, begin_context):
        self.contexts.append(deepcopy(begin_context))
        return self.results.pop(0)


class ReferenceHostNamingTests(unittest.IsolatedAsyncioTestCase):
    async def test_required_initial_choice_is_saved_before_ordinary_completion(self):
        client = NamingClient(await assessment(1999))
        reasoner = SequenceReasoner([HostReasoningResult(
            response_text="Four.", identity_choice=ProposeSelfNameCall.model_validate(CHOICE),
        )])
        turn = await CognitiveMindHost(client, reasoner).interact("What is two plus two?")

        self.assertEqual(turn.response_text, "Four.")
        self.assertEqual([name for name, _ in client.calls], [
            "begin_interaction", "propose_self_name", "complete_interaction",
        ])
        self.assertEqual(client.calls[1][1]["user_message"], "What is two plus two?")
        self.assertEqual(client.calls[1][1]["candidate_pronouns"], "he/him")

    async def test_required_choice_cannot_be_silently_omitted(self):
        client = NamingClient(await assessment(2000))
        reasoner = SequenceReasoner([HostReasoningResult(response_text="An ordinary answer.")])
        with self.assertRaisesRegex(ValueError, "required initial"):
            await CognitiveMindHost(client, reasoner).interact("Continue the ordinary task.")
        self.assertEqual([name for name, _ in client.calls], ["begin_interaction"])

    async def test_boundary_recovery_preserves_frozen_response_and_completion_key(self):
        client = NamingClient(await assessment(1500), blocked_once=True)
        reasoner = SequenceReasoner([
            HostReasoningResult(response_text="The frozen answer."),
            HostReasoningResult(
                response_text="A different answer must not replace the frozen one.",
                identity_choice=ProposeSelfNameCall.model_validate(CHOICE),
                working_context=HostWorkingContext(summary="A changed context must not replace it."),
            ),
        ])
        turn = await CognitiveMindHost(client, reasoner).interact("Continue.")
        self.assertEqual(turn.response_text, "The frozen answer.")
        completions = [arguments for name, arguments in client.calls if name == "complete_interaction"]
        self.assertEqual(len(completions), 2)
        self.assertEqual(completions[0], completions[1])
        self.assertEqual(completions[0]["idempotency_key"], "frozen-turn")

    async def test_exhausted_naming_recovery_reports_the_naming_condition(self):
        class StillBlockedClient(NamingClient):
            async def call_tool(self, name, arguments):
                if name == "complete_interaction":
                    self.blocked_once = True
                return await super().call_tool(name, arguments)

        client = StillBlockedClient(await assessment(1500))
        reasoner = SequenceReasoner([
            HostReasoningResult(response_text="The frozen answer."),
            HostReasoningResult(
                response_text="Recovery does not replace the response.",
                identity_choice=ProposeSelfNameCall.model_validate(CHOICE),
            ),
        ])
        with self.assertRaisesRegex(RuntimeError, "required identity choice"):
            await CognitiveMindHost(client, reasoner).interact("Continue.")
        self.assertEqual(len(reasoner.contexts), 2)

    async def test_openai_selection_schema_is_available_only_after_eligibility(self):
        for experiences, choice in ((999, None), (1000, None), (1999, CHOICE)):
            with self.subTest(experiences=experiences):
                arguments = {
                    "response_text": "A reply.", "working_context": {}, "proposed_memories": None,
                }
                if experiences >= 1000:
                    arguments["identity_choice"] = choice
                response = SimpleNamespace(output=[SimpleNamespace(
                    type="function_call", name="finalize_turn", arguments=json.dumps(arguments),
                )], output_text="")
                create = AsyncMock(return_value=response)
                reasoner = OpenAIHostReasoner(
                    api_key="synthetic-unused-key", client=SimpleNamespace(responses=SimpleNamespace(create=create)),
                )
                result = await reasoner.reason("An ordinary question.", {"naming": await assessment(experiences)})
                schema = create.await_args.kwargs["tools"][0]["parameters"]
                self.assertEqual("identity_choice" in schema["properties"], experiences >= 1000)
                self.assertEqual(result.identity_choice is not None, experiences == 1999)

    async def test_openai_required_choice_rejects_null(self):
        response = SimpleNamespace(output=[SimpleNamespace(
            type="function_call", name="finalize_turn", arguments=json.dumps({
                "response_text": "This must not be delivered.", "working_context": {},
                "identity_choice": None,
            }),
        )], output_text="")
        reasoner = OpenAIHostReasoner(api_key="synthetic-unused-key", client=SimpleNamespace(
            responses=SimpleNamespace(create=AsyncMock(return_value=response)),
        ))
        with self.assertRaisesRegex(ValueError, "required initial"):
            await reasoner.reason("Continue.", {"naming": await assessment(2000)})

    async def test_complete_identity_exposes_revision_only_for_an_explicit_command(self):
        selected = CognitiveMind(identity=MindIdentity(self_name="Existing", pronouns="they/them"))
        naming = await naming_assessment(selected, InMemoryJournalStore(), experience_count=2200)
        for message, permitted in (
            ("Choose a new name and pronouns", True),
            ("What is your name?", False),
            ("Do not choose a new name", False),
        ):
            with self.subTest(message=message):
                arguments = {"response_text": "A reply.", "working_context": {}}
                if permitted:
                    arguments["identity_choice"] = CHOICE
                response = SimpleNamespace(output=[SimpleNamespace(
                    type="function_call", name="finalize_turn", arguments=json.dumps(arguments),
                )], output_text="")
                create = AsyncMock(return_value=response)
                reasoner = OpenAIHostReasoner(api_key="synthetic-unused-key", client=SimpleNamespace(
                    responses=SimpleNamespace(create=create),
                ))
                result = await reasoner.reason(message, {"naming": naming})
                schema = create.await_args.kwargs["tools"][0]["parameters"]
                self.assertEqual("identity_choice" in schema["properties"], permitted)
                self.assertEqual(result.identity_choice is not None, permitted)


class BodyNamingTests(unittest.IsolatedAsyncioTestCase):
    async def runtime(self, experiences):
        mind = InMemoryMindStore()
        await mind.initialize(CognitiveMind(identity=MindIdentity()))
        journal = InMemoryJournalStore()
        for index in range(experiences):
            await journal.append(
                JournalEntry(kind=JournalKind.INTERACTION, experience={"synthetic": index}),
                recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
            )
        service = CognitiveMcpService(
            mind, journal, InMemoryMemoryStore(), steward_factory=MemoryStewardTool,
        )
        return mind, journal, service, HostRuntime(mind, service)

    async def test_2000th_response_stays_pending_until_choice_and_then_recovers(self):
        mind, journal, service, hosts = await self.runtime(1999)
        lease = await hosts.attach("Synthetic host", "Synthetic model")
        pending = asyncio.create_task(hosts.submit("An ordinary question."))
        try:
            for _ in range(100):
                requests = await hosts.records.pending()
                if requests:
                    break
                await asyncio.sleep(0)
            request = await hosts.next_request(lease["lease_token"])
            request_id = request["request_id"]
            blocked = await hosts.complete(lease["lease_token"], request_id, "The frozen response.")
            self.assertEqual(blocked["status"], "naming_choice_required")
            self.assertFalse(blocked["presentation"]["allowed"])
            self.assertFalse(pending.done())
            stored = await hosts.records.get(request_id)
            self.assertEqual(stored["state"], "pending")
            self.assertFalse(stored.get("presented", False))
            self.assertEqual((await service.naming_status())["experience_count"], 1999)
            with self.assertRaisesRegex(CommitConflict, "same response"):
                await hosts.complete(lease["lease_token"], request_id, "A changed response.")
            choice = GovernanceStewardTool(mind=mind, journal=journal, input_text="An ordinary question.")
            self.assertTrue((await choice.invoke(CHOICE))["accepted"])
            delivered = await hosts.complete(lease["lease_token"], request_id, "The frozen response.")
            self.assertEqual(delivered["response_text"], "The frozen response.")
            self.assertEqual((await pending)["response_text"], "The frozen response.")

            selected = await mind.load()
            cleared = selected.model_copy(update={"identity": MindIdentity()})
            await mind.replace_exact(selected, cleared, recorded_by=CognitiveActor.ADMINISTRATOR)
            cached = await hosts.complete(lease["lease_token"], request_id, "The frozen response.")
            self.assertEqual(cached["status"], "naming_choice_required")
            self.assertNotIn("response_text", cached)
            cached_message = await hosts.read_incoming_message(request_id)
            self.assertEqual(cached_message["result"]["status"], "naming_choice_required")
            self.assertNotIn("response_text", cached_message["result"])
            cached_claim = await hosts.claim_incoming_message(request_id)
            self.assertEqual(cached_claim["status"], "already_complete")
            self.assertNotIn("response_text", cached_claim["result"])
        finally:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)

    async def test_passive_sensory_completion_remains_operational_at_required_threshold(self):
        _, _, service, hosts = await self.runtime(2000)
        service.complete_interaction = AsyncMock()
        await hosts.records.create("passive-frame", {
            "kind": "body_request", "request_id": "passive-frame", "state": "pending",
            "task": "sensory_interpretation", "priority": 10, "message": "Preserved frame",
            "claim": "synthetic-claim", "claim_until": None, "deadline": None,
            "result": {}, "input_context": {},
        })
        result = await hosts._complete_claim("synthetic-claim", "passive-frame", "A chair is visible.")
        self.assertEqual(result["response_text"], "A chair is visible.")
        service.complete_interaction.assert_not_awaited()

    async def test_cached_delivery_checks_its_captured_current_assessment(self):
        naming = await assessment(2000)
        service = SimpleNamespace(
            naming_status=AsyncMock(return_value=naming), ensure_naming_ready=AsyncMock(),
        )
        hosts = HostRuntime(InMemoryMindStore(), service)
        await hosts.records.create("cached-before-crossing", {
            "kind": "body_request", "request_id": "cached-before-crossing", "state": "complete",
            "priority": 0, "message": "An old question.", "claim": "synthetic-claim",
            "result": {"response_text": "An old ordinary answer."},
        })
        result = await hosts._complete_claim(
            "synthetic-claim", "cached-before-crossing", "An old ordinary answer.",
        )
        self.assertEqual(result["status"], "naming_choice_required")
        service.naming_status.assert_awaited_once()
        service.ensure_naming_ready.assert_not_awaited()

    async def test_counter_crossing_during_final_request_write_blocks_delivery(self):
        mind, journal, service, hosts = await self.runtime(1998)
        request_id = "crossed-during-final-write"
        await hosts.records.create(request_id, {
            "kind": "body_request", "request_id": request_id, "state": "pending",
            "priority": 0, "message": "An ordinary question.", "created": 0,
            "claim": "synthetic-claim", "claim_until": None, "deadline": None, "result": {},
        })
        replace = hosts.records.replace

        async def cross_after_completion_write(key, before, after):
            saved = await replace(key, before, after)
            if saved and key == request_id and after.get("state") == "complete":
                await journal.append(
                    JournalEntry(kind=JournalKind.REFLECTION, experience={"synthetic": "crossing"}),
                    recorded_by=CognitiveActor.CONSCIOUS_WORKSPACE,
                )
            return saved

        with patch.object(hosts.records, "replace", side_effect=cross_after_completion_write):
            blocked = await hosts._complete_claim(
                "synthetic-claim", request_id, "The original frozen answer.",
            )
        self.assertEqual(blocked["status"], "naming_choice_required")
        self.assertFalse(blocked["presentation"]["allowed"])
        self.assertNotIn("response_text", blocked)
        self.assertEqual((await service.naming_status())["experience_count"], 2000)
        saved = await hosts.records.get(request_id)
        self.assertEqual(saved["state"], "complete")
        self.assertEqual(saved["result"]["response_text"], "The original frozen answer.")
        choice = GovernanceStewardTool(mind=mind, journal=journal, input_text="An ordinary question.")
        self.assertTrue((await choice.invoke(CHOICE))["accepted"])
        replayed = await hosts._complete_claim(
            "synthetic-claim", request_id, "The original frozen answer.",
        )
        self.assertEqual(replayed["response_text"], "The original frozen answer.")

    async def test_configured_endpoint_chooses_before_required_ordinary_reasoning(self):
        mind, _, service, hosts = await self.runtime(1999)
        dispatcher = SimpleNamespace(
            assignment=AsyncMock(return_value=SimpleNamespace(provider="configured", fallbacks=[])),
            complete_chat=AsyncMock(side_effect=[json.dumps(CHOICE), "A grounded ordinary answer."]),
        )
        with patch("aicognitive_mind.host_runtime.TaskModelDispatcher", return_value=dispatcher):
            result = await HostAwareCore(SimpleNamespace(), hosts, allow_standalone_fallback=True).interact(
                "Continue the ordinary task.",
            )
        self.assertEqual(result.response_text, "A grounded ordinary answer.")
        self.assertEqual((await mind.load()).identity.pronouns, "he/him")
        calls = dispatcher.complete_chat.await_args_list
        self.assertIn("INITIAL IDENTITY SELECTION", calls[0].args[1][0]["content"])
        self.assertIn("he/him", calls[1].kwargs["context"].working_context)

    async def test_optional_configured_endpoint_can_defer_without_choosing(self):
        mind, _, _, hosts = await self.runtime(1000)
        dispatcher = SimpleNamespace(
            assignment=AsyncMock(return_value=SimpleNamespace(provider="configured", fallbacks=[])),
            complete_chat=AsyncMock(side_effect=["null", "An ordinary answer while still eligible."]),
        )
        with patch("aicognitive_mind.host_runtime.TaskModelDispatcher", return_value=dispatcher):
            result = await HostAwareCore(SimpleNamespace(), hosts, allow_standalone_fallback=True).interact("Continue.")
        self.assertEqual(result.response_text, "An ordinary answer while still eligible.")
        self.assertIsNone((await mind.load()).identity.self_name)
        self.assertIsNone((await mind.load()).identity.pronouns)

    async def test_configured_endpoint_can_perform_an_explicit_later_revision(self):
        mind, journal, _, hosts = await self.runtime(1999)
        initial = GovernanceStewardTool(mind=mind, journal=journal, input_text="An ordinary question.")
        self.assertTrue((await initial.invoke(CHOICE))["accepted"])
        revised_choice = CHOICE | {"candidate_name": "Rhea", "candidate_pronouns": "she/her"}
        dispatcher = SimpleNamespace(
            assignment=AsyncMock(return_value=SimpleNamespace(provider="configured", fallbacks=[])),
            complete_chat=AsyncMock(side_effect=[json.dumps(revised_choice), "I chose Rhea and she/her."]),
        )
        with patch("aicognitive_mind.host_runtime.TaskModelDispatcher", return_value=dispatcher):
            result = await HostAwareCore(SimpleNamespace(), hosts, allow_standalone_fallback=True).interact(
                "Choose a new name and pronouns",
            )
        self.assertEqual(result.response_text, "I chose Rhea and she/her.")
        self.assertEqual((await mind.load()).identity.self_name, "Rhea")
        self.assertEqual((await mind.load()).identity.pronouns, "she/her")

    async def test_required_endpoint_validation_is_bounded_and_fails_closed(self):
        mind, _, service, hosts = await self.runtime(1999)
        service.complete_interaction = AsyncMock()
        dispatcher = SimpleNamespace(
            assignment=AsyncMock(return_value=SimpleNamespace(provider="configured", fallbacks=[])),
            complete_chat=AsyncMock(side_effect=["not JSON", "null"]),
        )
        with patch("aicognitive_mind.host_runtime.TaskModelDispatcher", return_value=dispatcher):
            with self.assertRaisesRegex(RuntimeError, "valid identity choice"):
                await HostAwareCore(SimpleNamespace(), hosts, allow_standalone_fallback=True).interact("Continue.")
        self.assertEqual(dispatcher.complete_chat.await_count, 2)
        service.complete_interaction.assert_not_awaited()
        self.assertIsNone((await mind.load()).identity.self_name)
