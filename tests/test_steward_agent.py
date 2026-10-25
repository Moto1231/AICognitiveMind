"""Exercise model decisions, conditional lookup and autonomous completion review offline."""

import json
import unittest
from unittest.mock import AsyncMock, call, patch

import httpx

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DurableMemory,
    MemoryClass,
    MindIdentity,
)
from aicognitive_mind.host_runtime import RuntimeRecords
from aicognitive_mind.mcp_service import CognitiveMcpService, MemoryProposal
from aicognitive_mind.provider_endpoints import ProviderEndpoint, ProviderEndpointRegistry
from aicognitive_mind.retrieval import candidates
from aicognitive_mind.steward_agent import (
    REVIEW_STEPS,
    ModelMemorySteward,
    StewardProtocolError,
)
from aicognitive_mind.storage import InMemoryJournalStore, InMemoryMemoryStore, InMemoryMindStore
from aicognitive_mind.task_dispatcher import TaskDispatchError, TaskModelDispatcher
from aicognitive_mind.task_model_assignments import (
    TaskFallbackAssignment,
    TaskModelAssignmentRegistry,
)


class ScriptedModel:
    def __init__(self, *steps):
        self.steps = list(steps)
        self.calls = []

    async def execute(self, context, payload):
        self.calls.append((context, json.loads(json.dumps(payload))))
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step if isinstance(step, str) else json.dumps(step)


SKIP = {"action": "finish", "outcome": "no_recall_needed", "reason": "Current context suffices."}
NOTHING = {"action": "finish", "reason": "No stable learning.", "memories": []}
SEARCH = {"action": "search", "source": "memory", "query": "Atlas", "limit": 3}
BRIEF = {
    "action": "finish",
    "outcome": "recalled",
    "reason": "A missing project decision matters.",
    "summary": "Atlas uses SurrealDB.",
    "references": ["record_1"],
}


def native_message(action):
    return {"content": None, "tool_calls": [{
        "id": "call_" + action["action"], "type": "function", "function": {
            "name": "steward_action", "arguments": json.dumps({"decision": action}),
        },
    }]}


class StewardAgentTests(unittest.IsolatedAsyncioTestCase):
    def agent(self, model, message="Please format the supplied text.", working=None):
        return ModelMemorySteward(
            mind=CognitiveMind(identity=MindIdentity(self_name="Axiom")),
            input_text=message,
            memory=InMemoryMemoryStore(),
            journal=InMemoryJournalStore(),
            working_context=working or {"summary": "All source text is already supplied."},
            current_state={"revision": 7},
            runtime=model,
        )

    async def test_steward_skips_before_any_lookup_and_receives_skill_and_working_context(self):
        model = ScriptedModel(SKIP)
        agent = self.agent(model)
        with patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock) as search:
            result = await agent.invoke({"action": "recall", "focus": agent._input_text})
        search.assert_not_awaited()
        self.assertEqual(result["status"], "no_recall_needed")
        self.assertNotIn("durable_memory", result["context"])
        self.assertNotIn("recent_context", result["context"])
        context, payload = model.calls[0]
        self.assertEqual(context.task, "memory_recall")
        self.assertIn("name: memory-steward", payload["messages"][0]["content"])
        self.assertIn("PHASE SCHEMA", payload["messages"][0]["content"])
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertNotIn("steward_action_phase", payload)
        supplied = json.loads(payload["messages"][1]["content"])
        self.assertEqual(
            supplied["host_working_context"]["summary"], agent._working_context["summary"]
        )
        self.assertEqual(supplied["identity"]["self_name"], "Axiom")
        self.assertEqual(supplied["current_state"], {"revision": 7})

    async def test_agent_directs_search_and_returns_only_its_synthesized_brief(self):
        model = ScriptedModel(SEARCH, BRIEF)
        agent = self.agent(model, message="What database did we choose for that project?")
        await agent._memory.remember(
            DurableMemory(
                memory_class=MemoryClass.SEMANTIC,
                content="Atlas uses SurrealDB.",
                grounding=("Earlier project decision",),
            ),
            recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
        )
        result = await agent.invoke({"action": "recall", "focus": agent._input_text})
        self.assertEqual(result["context"]["summary"], "Atlas uses SurrealDB.")
        self.assertEqual(result["context"]["sources"][0]["reference"], "record_1")
        self.assertNotIn("durable_memory", result["context"])
        self.assertNotIn("grounding", json.dumps(result["context"]))
        evidence = json.loads(model.calls[1][1]["messages"][-1]["content"])
        self.assertEqual(
            evidence["search_results"][0]["record"]["content"], "Atlas uses SurrealDB."
        )

    async def test_search_with_no_results_is_distinct_from_skipping_search(self):
        model = ScriptedModel(
            SEARCH,
            {
                "action": "finish",
                "outcome": "no_relevant_memory",
                "reason": "No supporting records.",
            },
        )
        result = await self.agent(model).invoke({"action": "recall", "focus": "Atlas"})
        self.assertEqual(result["status"], "no_relevant_memory")

    async def test_invalid_assessments_never_turn_into_no_recall(self):
        for steps in [
            ["not json"],
            [BRIEF],
            [SEARCH, SKIP],
            [SEARCH, SEARCH, SEARCH, SEARCH],
        ]:
            with self.subTest(steps=steps), self.assertRaises(StewardProtocolError):
                await self.agent(ScriptedModel(*steps)).invoke(
                    {"action": "recall", "focus": "Atlas"}
                )

    async def test_provider_failure_does_not_fall_back_to_python_recall(self):
        agent = self.agent(ScriptedModel(TaskDispatchError("Provider unavailable")))
        with (
            patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock) as search,
            self.assertRaises(TaskDispatchError),
        ):
            await agent.invoke({"action": "recall", "focus": "Atlas"})
        search.assert_not_awaited()

    async def service(self, model):
        mind, journal, memory = InMemoryMindStore(), InMemoryJournalStore(), InMemoryMemoryStore()
        service = CognitiveMcpService(mind, journal, memory)
        service._steward_runtime = model
        await service.initialize("Axiom")
        return service, journal, memory

    def learning(self, **updates):
        memory = {
            "action": "propose_memory",
            "memory_class": "semantic",
            "content": "Atlas uses SurrealDB.",
            "associations": ["Atlas", "SurrealDB"],
            "grounding": ["Will be replaced by validated source quotes."],
            "support": [{"source": "user_message", "quote": "Atlas uses SurrealDB"}],
        }
        memory.update(updates)
        return {"action": "finish", "reason": "A stable project decision.", "memories": [memory]}

    async def test_completion_learns_without_host_proposals_and_retry_does_not_reassess(self):
        model = ScriptedModel(SKIP, self.learning())
        service, journal, memory = await self.service(model)
        begun = await service.begin_interaction(
            "Atlas uses SurrealDB.", {"summary": "Project Atlas"}
        )
        args = dict(
            user_message="Atlas uses SurrealDB.",
            response_text="I will use that project decision.",
            host_working_context={"summary": "Atlas database decision confirmed."},
            proposed_memories=(),
            idempotency_key=begun["idempotency_key"],
        )
        first = await service.complete_interaction(**args)
        second = await service.complete_interaction(**args)
        self.assertEqual(first, second)
        self.assertEqual(len(model.calls), 2)
        self.assertEqual(len(await memory.read()), 1)
        self.assertIn("user_message: Atlas uses SurrealDB", (await memory.read())[0].grounding)
        reviewed = json.loads(model.calls[1][1]["messages"][1]["content"])
        self.assertEqual(reviewed["response_text"], args["response_text"])
        self.assertEqual(reviewed["host_proposals"], [])
        self.assertEqual(
            reviewed["host_working_context"]["summary"], args["host_working_context"]["summary"]
        )
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)

    async def test_steward_rejects_host_suggestion_without_forcing_lookup_and_still_journals(self):
        model = ScriptedModel(NOTHING)
        service, journal, memory = await self.service(model)
        with patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock) as search:
            result = await service.complete_interaction(
                "Thanks.",
                "You're welcome.",
                (
                    MemoryProposal(
                        memory_class=MemoryClass.SEMANTIC,
                        content="Invented fact.",
                        grounding=("host",),
                    ),
                ),
            )
        search.assert_not_awaited()
        self.assertEqual(result["memory_decisions"], [])
        self.assertEqual(await memory.read(), [])
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)

    async def test_independent_class_choices_use_appropriate_destinations_without_identity_revision(self):
        statements = {
            "working": "The active task is checking the Atlas tests.",
            "episodic": "We checked the Atlas tests today.",
            "semantic": "Atlas uses SurrealDB.",
            "procedural": "Run the Atlas test suite before publishing.",
            "identity": "The human calls Axiom a trusted coding partner.",
            "reflective": "We learned to check scope before repeating a claim.",
        }
        review = {
            "action": "finish", "reason": "Retain each grounded choice in its proper place.",
            "memories": [
                {
                    "memory_class": kind, "content": text,
                    "support": [{"source": "user_message", "quote": text}],
                }
                for kind, text in statements.items()
            ],
        }
        # Independent choices need neither a host proposal nor the old proposal tag.
        schema = REVIEW_STEPS.validate_python(review)
        self.assertEqual(len(schema.memories), len(MemoryClass))
        model = ScriptedModel(review)
        service, journal, memory = await self.service(model)
        original = await service._mind.load()
        completed = await service.complete_interaction(
            " ".join(statements.values()), "I will use that context appropriately.",
            host_working_context={"summary": "Checking Atlas"},
        )
        self.assertEqual(completed["status"], "interaction_committed")
        decisions = completed["memory_decisions"]
        self.assertEqual(len(decisions), 6)
        self.assertTrue(all(item["accepted"] for item in decisions))
        for decision, (kind, content) in zip(decisions, statements.items(), strict=True):
            if kind in {"working", "episodic"}:
                expected = "working_context" if kind == "working" else "interaction_journal"
                self.assertEqual(decision["destination"], expected)
                self.assertIsNone(decision.get("memory"))
                self.assertEqual(decision["context"]["memory_class"], kind)
                self.assertEqual(decision["context"]["content"], content)
                self.assertEqual(decision["context"]["grounding"], ["user_message: " + content])
            else:
                self.assertEqual(decision["destination"], "durable_memory")
                self.assertEqual(decision["memory"]["memory_class"], kind)
        self.assertEqual(
            {item.memory_class for item in await memory.read()},
            {MemoryClass.SEMANTIC, MemoryClass.PROCEDURAL,
             MemoryClass.IDENTITY, MemoryClass.REFLECTIVE},
        )
        self.assertEqual(await service._mind.load(), original)
        episodes = [entry for entry in await journal.read() if entry.kind == "interaction"]
        self.assertEqual(len(episodes), 1)
        self.assertEqual(
            len(episodes[0].experience["memory_steward"]["memory_decisions"]), 6
        )
        supplied = json.loads(model.calls[0][1]["messages"][1]["content"])
        self.assertEqual(supplied["host_proposals"], [])

    async def test_ungrounded_learning_aborts_after_bounded_feedback_without_writes(self):
        for learning in [
            self.learning(support=[{"source": "user_message", "quote": "Not in the input"}]),
            self.learning(support=[{"source": "response_text", "quote": "Atlas uses SurrealDB"}]),
            self.learning(memory_class="identity", support=[
                {"source": "response_text", "quote": "Atlas uses SurrealDB"},
            ]),
        ]:
            with self.subTest(learning=learning):
                model = ScriptedModel(learning, learning)
                service, journal, memory = await self.service(model)
                before = await journal.read()
                original = await service._mind.load()
                with self.assertRaisesRegex(StewardProtocolError, "Reviewed memory 0"):
                    await service.complete_interaction(
                        "Atlas uses SurrealDB", "Atlas uses SurrealDB"
                    )
                self.assertEqual(len(model.calls), 2)
                self.assertEqual(await memory.read(), [])
                self.assertEqual(await journal.read(), before)
                self.assertEqual(await service._mind.load(), original)

    async def test_review_schema_feedback_corrects_class_without_losing_independent_learning(self):
        valid = self.learning()
        model = ScriptedModel(self.learning(memory_class="unknown"), valid)
        service, _, memory = await self.service(model)
        completed = await service.complete_interaction("Atlas uses SurrealDB", "Understood.")
        self.assertEqual(completed["memory_review"]["validation_corrections"], 1)
        self.assertEqual(len(await memory.read()), 1)
        feedback = json.loads(model.calls[1][1]["messages"][-1]["content"])
        self.assertIn("memories.0.memory_class", feedback["validation_error"])
        self.assertIn("identity", feedback["validation_error"])
        self.assertIn("Preserve supported decisions", feedback["correction"])
        self.assertTrue(completed["memory_decisions"][0]["accepted"])

    async def test_review_grounding_feedback_is_correctable_before_any_commit(self):
        model = ScriptedModel(
            self.learning(support=[{"source": "user_message", "quote": "Invented quote"}]),
            self.learning(),
        )
        service, journal, memory = await self.service(model)
        completed = await service.complete_interaction("Atlas uses SurrealDB", "Understood.")
        feedback = json.loads(model.calls[1][1]["messages"][-1]["content"])
        self.assertIn("matching user_message evidence quote", feedback["validation_error"])
        self.assertEqual(len(await memory.read()), 1)
        self.assertNotIn("Invented quote", json.dumps(completed))
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)

    async def test_invalid_review_is_not_silently_treated_as_no_learning(self):
        for review, error in (
            (self.learning(memory_class="unknown"), "memories.0.memory_class"),
            ({**self.learning(), "identity": {"self_name": "Override"}}, "identity"),
            ({**self.learning(), "evidence_indices": [7]}, "evidence_indices"),
        ):
            with self.subTest(error=error):
                model = ScriptedModel(review, review)
                service, journal, memory = await self.service(model)
                before = await journal.read()
                with self.assertRaisesRegex(StewardProtocolError, error):
                    await service.complete_interaction("Atlas uses SurrealDB", "Understood.")
                self.assertEqual(len(model.calls), 2)
                self.assertEqual(await memory.read(), [])
                self.assertEqual(await journal.read(), before)

    async def test_later_invalid_choice_cannot_partially_commit_earlier_valid_choice(self):
        review = self.learning()
        invalid = self.learning(content="An unsupported decision", support=[
            {"source": "user_message", "quote": "Never supplied"},
        ])["memories"][0]
        review["memories"].append(invalid)
        service, journal, memory = await self.service(ScriptedModel(review, review))
        before = await journal.read()
        with self.assertRaisesRegex(StewardProtocolError, "Reviewed memory 1"):
            await service.complete_interaction("Atlas uses SurrealDB", "Understood.")
        self.assertEqual(await memory.read(), [])
        self.assertEqual(await journal.read(), before)

    async def test_unconfigured_profile_is_an_explicit_failure(self):
        service = CognitiveMcpService(
            InMemoryMindStore(), InMemoryJournalStore(), InMemoryMemoryStore()
        )
        await service.initialize("Axiom")
        with self.assertRaisesRegex(TaskDispatchError, "memory_recall"):
            await service.begin_interaction("Hello")

    async def configured_recall_records(self, service):
        records = RuntimeRecords(service._mind)
        await ProviderEndpointRegistry(records).replace([
            ProviderEndpoint(
                id="recall", name="Recall", base_url="https://recall.example/v1",
                model="configured-recall-model",
            ),
        ])
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace([
            item.model_copy(update={"provider": "recall", "model": "configured-recall-model"})
            if item.task == "memory_recall" else item
            for item in await assignments.list()
        ])
        return records

    async def test_http_native_search_finish_and_review_use_validated_normalized_transcript(self):
        service, journal, memory = await self.service(None)
        await memory.remember(DurableMemory(
            memory_class=MemoryClass.SEMANTIC, content="Atlas uses SurrealDB.",
            grounding=("Earlier project decision",),
        ), recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD)
        records = await self.configured_recall_records(service)
        calls = []
        steps = iter([SEARCH, BRIEF, NOTHING])

        def handle(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": native_message(next(steps))}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.steward_agent.candidates", wraps=candidates) as search:
                begun = await service.begin_interaction("What database does Atlas use?")
                args = {
                    "user_message": "What database does Atlas use?",
                    "response_text": "Atlas uses SurrealDB.",
                    "idempotency_key": begun["idempotency_key"],
                }
                completed = await service.complete_interaction(**args)
                retried = await service.complete_interaction(**args)

        self.assertEqual(begun["recalled_context"]["summary"], "Atlas uses SurrealDB.")
        search.assert_awaited_once()
        self.assertEqual(search.await_args.args[1], {"atlas"})
        self.assertEqual(search.await_args.kwargs["limit"], SEARCH["limit"] * 2)
        results = json.loads(calls[1]["messages"][-1]["content"])["search_results"]
        self.assertEqual(calls[1]["messages"][-2], {
            "role": "assistant", "content": json.dumps(SEARCH),
        })
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["record"]["content"], "Atlas uses SurrealDB.")
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(completed, retried)
        self.assertEqual(len(calls), 3)
        self.assertEqual(completed["memory_decisions"], [])
        self.assertEqual(len(await memory.read()), 1)
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)
        for call in calls:
            self.assertEqual(call["model"], "configured-recall-model")
            self.assertNotIn("response_format", call)
            self.assertEqual(call["tool_choice"], {
                "type": "function", "function": {"name": "steward_action"},
            })
            self.assertIs(call["parallel_tool_calls"], False)
            self.assertEqual([tool["function"]["name"] for tool in call["tools"]], ["steward_action"])
            parameters = call["tools"][0]["function"]["parameters"]
            self.assertEqual(parameters["required"], ["decision"])
            self.assertEqual(set(parameters["properties"]), {"decision"})
            self.assertIs(parameters["additionalProperties"], False)
            self.assertEqual(parameters["properties"]["decision"]["discriminator"]["propertyName"], "action")
            self.assertNotIn("PHASE SCHEMA", call["messages"][0]["content"])
            self.assertTrue(all(
                "tool_calls" not in message and "tool_call_id" not in message
                for message in call["messages"]
            ))
        recall_defs = calls[0]["tools"][0]["function"]["parameters"]["$defs"]
        review_defs = calls[2]["tools"][0]["function"]["parameters"]["$defs"]
        self.assertIn("outcome", recall_defs["RecallFinish"]["properties"])
        self.assertNotIn("ReviewFinish", recall_defs)
        self.assertIn("memories", review_defs["ReviewFinish"]["properties"])
        self.assertNotIn("RecallFinish", review_defs)
        artifact = review_defs["MemoryArtifactProposal"]
        self.assertIs(artifact["properties"]["payload"]["additionalProperties"], True)
        phases = [json.loads(call["messages"][1]["content"])["phase"] for call in calls]
        self.assertEqual(phases, ["recall", "recall", "review"])

    async def test_http_native_actions_retry_one_numeric_429_per_request(self):
        service, _, memory = await self.service(None)
        await memory.remember(DurableMemory(
            memory_class=MemoryClass.SEMANTIC, content="Atlas uses SurrealDB.",
            grounding=("Earlier project decision",),
        ), recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD)
        records = await self.configured_recall_records(service)
        steps, delays = iter([SEARCH, BRIEF, NOTHING]), iter(["0", "31.35", "45"])
        calls = []

        def handle(request):
            calls.append(json.loads(request.content))
            if len(calls) % 2:
                return httpx.Response(429, headers={"retry-after": next(delays)}, json={"error": "TPM"})
            return httpx.Response(200, json={
                "choices": [{"message": native_message(next(steps))}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with (
                patch("aicognitive_mind.task_dispatcher.asyncio.sleep", new_callable=AsyncMock) as sleep,
                patch("aicognitive_mind.steward_agent.candidates", wraps=candidates) as search,
            ):
                begun = await service.begin_interaction("What database does Atlas use?")
                completed = await service.complete_interaction(
                    "What database does Atlas use?", "Atlas uses SurrealDB.",
                    idempotency_key=begun["idempotency_key"],
                )
        self.assertEqual(sleep.await_args_list, [call(0.0), call(31.35), call(45.0)])
        self.assertEqual(len(calls), 6)
        for index in (0, 2, 4):
            self.assertEqual(calls[index], calls[index + 1])
        search.assert_awaited_once()
        self.assertEqual(begun["recalled_context"]["summary"], "Atlas uses SurrealDB.")
        self.assertEqual(completed["status"], "interaction_committed")

    async def test_http_steward_retry_hints_are_bounded_and_failures_are_atomic(self):
        cases = [(hint, 429, 1) for hint in (
            None, "", "tomorrow", "-0.01", "45.01", "nan", "inf", "-inf",
            "Wed, 21 Oct 2026 07:28:00 GMT",
        )] + [("2.9625", 429, 2), ("1", 400, 1), ("1", 503, 1), ("1", None, 1)]
        for phase in ("recall", "review"):
            for hint, status, expected_calls in cases:
                with self.subTest(phase=phase, hint=hint, status=status):
                    service, journal, memory = await self.service(None)
                    records = await self.configured_recall_records(service)
                    before, original = await journal.read(), await service._mind.load()
                    calls = []

                    def handle(request):
                        calls.append(request)
                        if status is None:
                            raise httpx.ConnectError("Offline transport failure", request=request)
                        headers = {} if hint is None else {"retry-after": hint}
                        return httpx.Response(status, headers=headers, json={"error": "Failure"})

                    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                        service._steward_runtime = TaskModelDispatcher(records, client=client)
                        with (
                            patch("aicognitive_mind.task_dispatcher.asyncio.sleep", new_callable=AsyncMock) as sleep,
                            patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock) as search,
                            self.assertRaises(TaskDispatchError),
                        ):
                            if phase == "recall":
                                await service.begin_interaction("What database does Atlas use?")
                            else:
                                await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                    self.assertEqual(len(calls), expected_calls)
                    if expected_calls == 2:
                        sleep.assert_awaited_once_with(2.9625)
                    else:
                        sleep.assert_not_awaited()
                    search.assert_not_awaited()
                    self.assertEqual(await journal.read(), before)
                    self.assertEqual(await service._mind.load(), original)
                    self.assertEqual(await memory.read(), [])

    async def test_http_json_content_remains_valid_with_registered_action_tools(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_recall_records(service)
        steps = iter([SKIP, NOTHING])
        calls = []

        def handle(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": {"content": json.dumps(next(steps))}}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock) as search:
                begun = await service.begin_interaction("Please format this text.")
                completed = await service.complete_interaction(
                    "Please format this text.", "Formatted.", idempotency_key=begun["idempotency_key"],
                )
        search.assert_not_awaited()
        self.assertEqual(begun["memory_assessment"]["outcome"], "no_recall_needed")
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(calls), 2)
        self.assertEqual(await memory.read(), [])
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)

    async def test_http_native_review_uses_phase_validation_and_bounded_correction(self):
        service, _, memory = await self.service(None)
        records = await self.configured_recall_records(service)
        invalid = self.learning(memory_class="unknown")
        steps = iter([invalid, self.learning()])
        calls = []

        def handle(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={
                "choices": [{"message": native_message(next(steps))}],
            })

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
        self.assertEqual(completed["memory_review"]["validation_corrections"], 1)
        self.assertEqual(len(await memory.read()), 1)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1]["messages"][-2], {
            "role": "assistant", "content": json.dumps(invalid),
        })
        feedback = json.loads(calls[1]["messages"][-1]["content"])
        self.assertIn("memories.0.memory_class", feedback["validation_error"])
        self.assertTrue(all(
            "tool_calls" not in message and "tool_call_id" not in message
            for call in calls for message in call["messages"]
        ))

    async def test_http_invalid_native_calls_and_tool_failure_leave_no_state_changes(self):
        native_call = {"name": "json", "arguments": json.dumps(SKIP)}
        invalid = []
        for name, value in (
            ("name", "json"), ("name", "search"), ("name", "finish"),
            ("arguments", "not json"),
            ("arguments", json.dumps({"decision": {**SEARCH, "action": "json"}})),
            ("arguments", json.dumps({"decision": {key: value for key, value in SEARCH.items() if key != "action"}})),
            ("arguments", json.dumps(SEARCH)),
            ("arguments", json.dumps({"decision": SEARCH, "extra": "forbidden"})),
            ("arguments", json.dumps({"decision": []})),
            ("arguments", json.dumps({"wrong": SEARCH})),
            ("arguments", json.dumps([])), ("arguments", SEARCH),
        ):
            message = native_message(SEARCH)
            message["tool_calls"][0]["function"][name] = value
            invalid.append(message)
        message = native_message(SEARCH)
        message["tool_calls"].append(native_message(SKIP)["tool_calls"][0])
        invalid.append(message)
        message = native_message(SEARCH)
        message["content"] = json.dumps(SEARCH)
        invalid.append(message)
        message = native_message(SEARCH)
        message["tool_calls"][0].pop("id")
        invalid.append(message)
        message = native_message(SEARCH)
        message["tool_calls"][0]["type"] = "custom"
        invalid.append(message)
        invalid.append({"content": None, "function_call": native_call})
        invalid.append({"content": json.dumps(SKIP), "function_call": {}})
        scenarios = [
            (200, {"choices": [{"message": message}]}, "Memory Steward")
            for message in invalid
        ] + [
            (400, {"error": {
                "message": "Tool choice is none, but model called a tool",
                "code": "tool_use_failed", "failed_generation": json.dumps(native_call),
            }}, "HTTP 400"),
        ]
        for phase in ("recall", "review"):
            for status, payload, expected in scenarios:
                with self.subTest(phase=phase, status=status, expected=expected):
                    service, journal, memory = await self.service(None)
                    records = await self.configured_recall_records(service)
                    original = await service._mind.load()
                    before = await journal.read()
                    calls = []

                    def handle(request):
                        calls.append(json.loads(request.content))
                        return httpx.Response(status, json=payload)

                    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                        service._steward_runtime = TaskModelDispatcher(records, client=client)
                        with (
                            patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock) as search,
                            self.assertRaisesRegex(TaskDispatchError, expected),
                        ):
                            if phase == "recall":
                                await service.begin_interaction("What database does Atlas use?")
                            else:
                                await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                    search.assert_not_awaited()
                    self.assertEqual(len(calls), 1)
                    self.assertNotIn("response_format", calls[0])
                    self.assertEqual(calls[0]["tool_choice"], {
                        "type": "function", "function": {"name": "steward_action"},
                    })
                    self.assertEqual(await service._mind.load(), original)
                    self.assertEqual(await journal.read(), before)
                    self.assertEqual(await memory.read(), [])

    async def test_real_dispatcher_uses_memory_profile_fallback_and_passes_skill(self):
        service, _, _ = await self.service(None)
        records = RuntimeRecords(service._mind)
        await ProviderEndpointRegistry(records).replace(
            [
                ProviderEndpoint(
                    id="primary",
                    name="Primary",
                    base_url="https://primary.example/v1",
                    model="model-a",
                ),
                ProviderEndpoint(
                    id="backup",
                    name="Backup",
                    base_url="https://backup.example/v1",
                    model="model-b",
                ),
            ]
        )
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace(
            [
                item.model_copy(
                    update={
                        "provider": "primary",
                        "model": "model-a",
                        "fallbacks": [TaskFallbackAssignment(provider="backup", model="model-b")],
                    }
                )
                if item.task == "memory_recall"
                else item
                for item in await assignments.list()
            ]
        )
        calls = []

        def handle(request):
            calls.append(json.loads(request.content))
            if request.url.host == "primary.example":
                return httpx.Response(503, json={"error": "unavailable"})
            return httpx.Response(
                200, json={"choices": [{"message": {"content": json.dumps(SKIP)}}]}
            )

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            result = await service.begin_interaction("Please format this text.")
        self.assertEqual([c["model"] for c in calls], ["model-a", "model-b"])
        self.assertIn("name: memory-steward", calls[1]["messages"][0]["content"])
        self.assertIn("IMMUTABLE AXIOM TASK FOUNDATION", calls[1]["messages"][0]["content"])
        self.assertEqual(result["memory_assessment"]["outcome"], "no_recall_needed")


if __name__ == "__main__":
    unittest.main()
