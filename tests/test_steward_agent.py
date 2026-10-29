"""Exercise model decisions, conditional lookup and autonomous completion review offline."""

import asyncio
import json
import unittest
from unittest.mock import AsyncMock, call, patch

import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError

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
    RECALL_STEPS,
    REVIEW_STEPS,
    ModelMemorySteward,
    RecallAction,
    ReviewAction,
    StewardAssessmentExhausted,
    StewardAssessmentTimeout,
    StewardProtocolError,
    inline_action_schema,
    steward_action_tools,
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


class NativeScriptedModel(ScriptedModel):
    supports_steward_action_tools = True


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
    def test_final_provider_decision_schema_permits_only_the_phase_finish(self):
        for phase, finish in (("recall", BRIEF), ("review", NOTHING)):
            tool = steward_action_tools(phase, finish_only=True)[0]["function"]
            self.assertEqual(tool["name"], "steward_action")
            schema = tool["parameters"]
            Draft202012Validator.check_schema(schema)
            validator = Draft202012Validator(schema)
            self.assertTrue(validator.is_valid({"decision": finish}))
            self.assertFalse(validator.is_valid({"decision": SEARCH}))
            self.assertEqual(schema["properties"]["decision"]["properties"]["action"]["const"], "finish")

    def test_provider_schema_preserves_phase_validation_without_model_labels(self):
        arbitrary = self.learning(artifacts=[{
            "kind": "project", "payload": {"title": "Keep data", "nested": {"anything": [1, True]}},
        }])
        decisions = [
            SEARCH, {**SEARCH, "limit": 1}, {**SEARCH, "limit": 8},
            {**SEARCH, "limit": 0}, {**SEARCH, "limit": 9},
            {**SEARCH, "query": "x" * 1001}, {**SEARCH, "source": "other"},
            {**SEARCH, "extra": True}, {key: value for key, value in SEARCH.items() if key != "action"},
            SKIP, BRIEF, NOTHING, arbitrary, {**SKIP, "reason": ""},
            {"action": "finish"}, self.learning(memory_class="unknown"),
        ]
        for phase, model, adapter in (
            ("recall", RecallAction, RECALL_STEPS), ("review", ReviewAction, REVIEW_STEPS),
        ):
            original = model.model_json_schema()
            provider = steward_action_tools(phase)[0]["function"]["parameters"]
            Draft202012Validator.check_schema(provider)
            before, after = Draft202012Validator(original), Draft202012Validator(provider)
            for label in ("$ref", "$defs", '"title"', "discriminator", "RecallFinish", "ReviewFinish"):
                self.assertNotIn(label, json.dumps(provider))
            for decision in decisions:
                with self.subTest(phase=phase, decision=decision):
                    try:
                        adapter.validate_python(decision)
                        valid = True
                    except ValidationError:
                        valid = False
                    wrapped = {"decision": decision}
                    self.assertEqual(before.is_valid(wrapped), valid)
                    self.assertEqual(after.is_valid(wrapped), valid)
            for wrapped in ({}, {"decision": SEARCH, "extra": True}, {"decision": []}):
                self.assertFalse(before.is_valid(wrapped))
                self.assertFalse(after.is_valid(wrapped))

    def test_schema_inlining_preserves_property_names_data_and_reference_siblings(self):
        data = {"title": "Keep", "$ref": "literal", "$defs": {"title": 1}, "discriminator": False}
        schema = {
            "type": "object", "title": "Remove this annotation",
            "properties": {
                "title": {"type": "string", "title": "Remove this annotation too"},
                "discriminator": {"const": data}, "$defs": {"type": "boolean"},
            },
            "required": ["title", "discriminator", "$defs"], "additionalProperties": False,
            "default": data, "examples": [data],
        }
        provider = inline_action_schema(schema)
        self.assertEqual(set(provider["properties"]), {"title", "discriminator", "$defs"})
        self.assertEqual(provider["properties"]["discriminator"]["const"], data)
        self.assertEqual(provider["default"], data)
        self.assertEqual(provider["examples"], [data])
        self.assertNotIn("title", provider)
        self.assertNotIn("title", provider["properties"]["title"])
        self.assertIn("title", schema)
        self.assertTrue(Draft202012Validator(provider).is_valid({
            "title": "Value", "discriminator": data, "$defs": True,
        }))

        sibling_schema = {
            "$defs": {"Thing": {
                "type": "object", "properties": {"value": {"type": "integer", "minimum": 0, "maximum": 10}},
            }},
            "$ref": "#/$defs/Thing", "properties": {"value": {"minimum": -5, "maximum": 20}},
            "allOf": [{"required": ["value"]}], "unevaluatedProperties": False,
        }
        nested_schema = {
            "$defs": {"Outer": {"$defs": {"Inner": {"type": "integer", "minimum": 2}}}},
            "type": "array", "items": {"$ref": "#/$defs/Outer/$defs/Inner"},
        }
        legacy_schema = {"definitions": {"Legacy": {"type": "number", "minimum": 0}}, "$ref": "#/definitions/Legacy"}
        for original, values in (
            (sibling_schema, [{"value": 0}, {"value": 10}, {"value": -1}, {"value": 11}, {}, {"value": 1, "extra": 0}]),
            (nested_schema, [[2], [1], ["wrong"]]),
            (legacy_schema, [0, -1, "wrong"]),
        ):
            provider = inline_action_schema(original)
            self.assertNotIn("definitions", provider)
            before, after = Draft202012Validator(original), Draft202012Validator(provider)
            for value in values:
                self.assertEqual(before.is_valid(value), after.is_valid(value))

    def test_schema_inlining_fails_on_unresolvable_or_cyclic_references(self):
        for schema, error in (
            ({"$ref": "#/$defs/missing"}, "unresolvable"),
            ({"$defs": {"A": {"$ref": "#/$defs/B"}, "B": {"$ref": "#/$defs/A"}}, "$ref": "#/$defs/A"}, "cyclic"),
            ({"$ref": "https://external.example/schema"}, "local references"),
        ):
            with self.subTest(error=error), self.assertRaisesRegex(StewardProtocolError, error):
                inline_action_schema(schema)

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

    async def configured_steward_pool(self, service, count=3):
        records = RuntimeRecords(service._mind)
        await ProviderEndpointRegistry(records).replace([
            ProviderEndpoint(
                id=f"provider-{index}", name=f"Provider {index}",
                base_url=f"https://provider-{index}.example/v1", model=f"model-{index}",
            )
            for index in range(count)
        ])
        assignments = TaskModelAssignmentRegistry(records)
        await assignments.replace([
            item.model_copy(update={
                "provider": "provider-0", "provider_rotation": "ordered",
                "fallbacks": [
                    TaskFallbackAssignment(provider=f"provider-{index}")
                    for index in range(1, count)
                ],
            }) if item.task == "memory_recall" else item
            for item in await assignments.list()
        ])
        return records

    async def test_rejected_review_advances_provider_and_commits_only_grounded_learning(self):
        rejected = [
            self.learning(support=[{"source": "user_message", "quote": "Never supplied"}]),
            self.learning(support=[{"source": "current_evidence", "quote": "Never supplied"}]),
            self.learning(support=[{"source": "response_text", "quote": "Atlas uses SurrealDB"}]),
            self.learning(memory_class="identity", support=[
                {"source": "response_text", "quote": "Atlas uses SurrealDB"},
            ]),
            self.learning(memory_class="unknown"),
            {**self.learning(), "references": ["missing_record"]},
            {**self.learning(), "evidence_indices": [0]},
        ]
        for review in rejected:
            with self.subTest(review=review):
                service, journal, memory = await self.service(None)
                records = await self.configured_steward_pool(service)
                calls = []

                def handle(request):
                    calls.append(request.url.host)
                    decision = review if request.url.host == "provider-0.example" else self.learning()
                    return httpx.Response(200, json={
                        "choices": [{"message": native_message(decision)}],
                    })

                async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                    service._steward_runtime = TaskModelDispatcher(records, client=client)
                    completed = await service.complete_interaction(
                        "Atlas uses SurrealDB.", "Atlas uses SurrealDB.",
                    )
                self.assertEqual(calls, ["provider-0.example", "provider-1.example"])
                self.assertEqual(completed["status"], "interaction_committed")
                learned = await memory.read()
                self.assertEqual(len(learned), 1)
                self.assertEqual(learned[0].memory_class, MemoryClass.SEMANTIC)
                self.assertEqual(learned[0].grounding, ("user_message: Atlas uses SurrealDB",))
                self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)

    async def test_review_validation_failure_then_rate_limit_reaches_next_valid_provider(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        calls = []
        invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])

        def handle(request):
            calls.append(request.url.host)
            if request.url.host == "provider-1.example":
                return httpx.Response(429, json={"error": "busy"}, headers={"retry-after": "20"})
            decision = invalid if request.url.host == "provider-0.example" else self.learning()
            return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            dispatcher = TaskModelDispatcher(records, client=client)
            service._steward_runtime = dispatcher
            with patch("aicognitive_mind.task_dispatcher.asyncio.sleep", new_callable=AsyncMock) as sleep:
                completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
            sleep.assert_not_awaited()
        self.assertEqual(calls, ["provider-0.example", "provider-1.example", "provider-2.example"])
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)
        pool = (await dispatcher.routing_status())["tasks"]
        memory_pool = next(item for item in pool if item["task"] == "memory_recall")
        self.assertEqual(memory_pool["candidates"][1]["cooldown_reason"], "rate_limited")

    async def test_all_rejected_review_providers_fail_closed_without_partial_writes(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        original, before = await service._mind.load(), await journal.read()
        invalid = self.learning()
        invalid["memories"].append(self.learning(
            content="An unsupported second decision", support=[
                {"source": "user_message", "quote": "Never supplied"},
            ],
        )["memories"][0])
        calls = []

        def handle(request):
            calls.append(request.url.host)
            return httpx.Response(200, json={"choices": [{"message": native_message(invalid)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with self.assertRaises(TaskDispatchError):
                await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
        self.assertEqual(calls, ["provider-0.example", "provider-1.example", "provider-2.example"])
        self.assertEqual(await memory.read(), [])
        self.assertEqual(await journal.read(), before)
        self.assertEqual(await service._mind.load(), original)

    async def test_review_search_does_not_restart_a_rejected_provider(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        calls = []
        backup_steps = iter([SEARCH, self.learning()])
        invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])

        def handle(request):
            calls.append(request.url.host)
            decision = invalid if request.url.host == "provider-0.example" else next(backup_steps)
            return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock, return_value=[]) as search:
                completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
            search.assert_awaited_once()
        self.assertEqual(calls, ["provider-0.example", "provider-1.example", "provider-1.example"])
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)
        self.assertEqual(len([e for e in await journal.read() if e.kind == "interaction"]), 1)

    async def test_review_failure_exclusion_is_local_and_healthy_primary_does_not_rotate(self):
        service, _, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        calls = []
        invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])

        def handle(request):
            calls.append(request.url.host)
            decision = invalid if len(calls) == 1 else self.learning()
            return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            for _ in range(3):
                completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(calls, [
            "provider-0.example", "provider-1.example", "provider-0.example", "provider-0.example",
        ])
        self.assertEqual(len(await memory.read()), 1)

    async def test_later_review_providers_get_a_chance_beyond_four_rejected_decisions(self):
        for healthy in (4, 5):
            with self.subTest(healthy=healthy):
                service, journal, memory = await self.service(None)
                records = await self.configured_steward_pool(service, count=6)
                calls = []
                invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])

                def handle(request):
                    calls.append(request.url.host)
                    decision = self.learning() if request.url.host == f"provider-{healthy}.example" else invalid
                    return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

                async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                    service._steward_runtime = TaskModelDispatcher(records, client=client)
                    completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                self.assertEqual(calls, [f"provider-{index}.example" for index in range(healthy + 1)])
                self.assertEqual(completed["status"], "interaction_committed")
                self.assertEqual(len(await memory.read()), 1)
                self.assertEqual(len([entry for entry in await journal.read() if entry.kind == "interaction"]), 1)

    async def test_failed_finish_after_three_searches_reaches_backup_and_successful_retry_is_cached(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service, count=2)
        steps = iter([SEARCH, SEARCH, SEARCH, self.learning(memory_class="unknown"), self.learning()])
        calls, bodies = [], []

        def handle(request):
            calls.append(request.url.host)
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": native_message(next(steps))}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock, return_value=[]) as search:
                args = {
                    "user_message": "Atlas uses SurrealDB.", "response_text": "Understood.",
                    "idempotency_key": "backup-after-three-searches",
                }
                completed = await service.complete_interaction(**args)
                committed_journal = await journal.read()
                self.assertEqual(await service.complete_interaction(**args), completed)
                self.assertEqual(await journal.read(), committed_journal)
            self.assertEqual(search.await_count, 3)
        self.assertEqual(calls, ["provider-0.example"] * 4 + ["provider-1.example"])
        for body in bodies[-2:]:
            schema = body["tools"][0]["function"]["parameters"]
            self.assertFalse(Draft202012Validator(schema).is_valid({"decision": SEARCH}))
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)
        self.assertEqual(len([entry for entry in committed_journal if entry.kind == "interaction"]), 1)

    async def test_search_budget_is_global_across_provider_switches_and_forces_finish_only(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        await memory.remember(DurableMemory(
            memory_class=MemoryClass.SEMANTIC, content="Atlas uses SurrealDB.",
            grounding=("Earlier project decision",),
        ), recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD)
        invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])
        steps = iter([SEARCH, SEARCH, invalid, SEARCH, SEARCH,
                      {**self.learning(), "references": ["record_1"]}])
        calls, bodies = [], []

        def handle(request):
            calls.append(request.url.host)
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": native_message(next(steps))}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.steward_agent.candidates", wraps=candidates) as search:
                completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
            self.assertEqual(search.await_count, 3)
        self.assertEqual(calls, ["provider-0.example"] * 3 + ["provider-1.example"] * 2 + ["provider-2.example"])
        for index, body in enumerate(bodies):
            schema = body["tools"][0]["function"]["parameters"]
            self.assertEqual(Draft202012Validator(schema).is_valid({"decision": SEARCH}), index < 4)
        prior_results = [json.loads(message["content"])["search_results"]
                         for message in bodies[-1]["messages"]
                         if message["role"] == "user" and "search_results" in json.loads(message["content"])]
        self.assertEqual(len(prior_results), 3)
        self.assertTrue(all(result[0]["reference"] == "record_1" for result in prior_results))
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)
        self.assertEqual(len([entry for entry in await journal.read() if entry.kind == "interaction"]), 1)

    async def test_exhausted_review_is_warning_only_with_open_breaker_and_no_partial_writes(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service, count=6)
        before, original = await journal.read(), await service._mind.load()
        calls = []
        invalid = self.learning()
        invalid["memories"].append(self.learning(support=[
            {"source": "user_message", "quote": "Never supplied"},
        ])["memories"][0])

        for index in range(65):
            await service._continuity_health.record(f"prior-success-{index}", succeeded=True)
        for index in range(35):
            prior_health = await service._continuity_health.record(
                f"prior-failure-{index}",
                succeeded=False,
                failure_class="StorageTimeout",
            )
        self.assertTrue(prior_health["circuit_open"])

        def handle(request):
            calls.append(request.url.host)
            index = int(request.url.host.split(".", 1)[0].split("-")[-1])
            if index in (0, 4):
                return httpx.Response(429 if index == 0 else 503, json={"error": "Unavailable"},
                                      headers={"retry-after": "1"})
            if index == 1:
                raise httpx.ConnectError("Offline provider", request=request)
            if index == 2:
                return httpx.Response(200, json={"choices": []})
            decision = self.learning(memory_class="unknown") if index == 3 else invalid
            return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch(
                "aicognitive_mind.task_dispatcher.asyncio.sleep", new_callable=AsyncMock
            ) as sleep:
                completed = await service.complete_interaction(
                    "Atlas uses SurrealDB.", "Understood.", idempotency_key="exhausted-review",
                )
                retried = await service.complete_interaction(
                    "Atlas uses SurrealDB.", "Understood.", idempotency_key="exhausted-review",
                )
            sleep.assert_not_awaited()
        self.assertEqual(calls, [f"provider-{index}.example" for index in range(6)])
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(completed["memory_review"]["outcome"], "unavailable")
        self.assertEqual(
            completed["memory_review"]["failure_class"], "StewardAssessmentExhausted"
        )
        self.assertTrue(completed["presentation"]["allowed"])
        self.assertEqual(completed, retried)
        self.assertTrue(completed["continuity_health"]["circuit_open"])
        self.assertEqual(completed["continuity_health"]["rolling_failures"], 35)
        self.assertEqual(completed["continuity_health"]["consecutive_failures"], 0)
        self.assertEqual(completed["continuity_health"]["degraded_reviews"], 1)
        self.assertEqual(
            completed["continuity_health"]["last_degradation_class"],
            "StewardAssessmentExhausted",
        )
        self.assertEqual(
            completed["presentation"]["reason"],
            "journal_committed_memory_review_degraded",
        )
        self.assertEqual(await memory.read(), [])
        self.assertEqual(len(await journal.read()), len(before) + 1)
        self.assertEqual(await service._mind.load(), original)

    async def test_assessment_deadline_stops_before_untried_models_without_reporting_pool_exhaustion(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        before, original = await journal.read(), await service._mind.load()
        calls = []
        real_timeout = asyncio.timeout

        async def handle(request):
            calls.append(request.url.host)
            await asyncio.Event().wait()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch(
                "aicognitive_mind.steward_agent.asyncio.timeout",
                side_effect=lambda _: real_timeout(0.05),
            ):
                completed = await service.complete_interaction(
                    "Atlas uses SurrealDB.", "Understood.", idempotency_key="timed-out-review",
                )
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(
            completed["memory_review"]["failure_class"], "StewardAssessmentTimeout"
        )
        self.assertEqual(calls, ["provider-0.example"])
        self.assertEqual(await memory.read(), [])
        self.assertEqual(len(await journal.read()), len(before) + 1)
        self.assertEqual(await service._mind.load(), original)

    async def test_provider_raised_timeout_is_not_misreported_as_assessment_deadline(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        before, original = await journal.read(), await service._mind.load()
        calls = []

        async def handle(request):
            calls.append(request.url.host)
            raise TimeoutError("Provider-raised timeout before assessment expiry")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            completed = await service.complete_interaction(
                "Atlas uses SurrealDB.", "Understood.", idempotency_key="provider-timeout",
            )
        self.assertEqual(completed["status"], "interaction_persistence_failed")
        self.assertEqual(completed["persistence_outcome"]["failure_class"], "TimeoutError")
        self.assertTrue(completed["presentation"]["allowed"])
        self.assertFalse(completed["presentation"]["report_persistence_error"])
        self.assertEqual(completed["continuity_health"]["rolling_failures"], 1)
        self.assertEqual(calls, ["provider-0.example"])
        self.assertEqual(await memory.read(), [])
        self.assertEqual(await journal.read(), before)
        self.assertEqual(await service._mind.load(), original)

    async def test_external_cancellation_propagates_without_fallback_or_partial_writes(self):
        service, journal, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        before, original = await journal.read(), await service._mind.load()
        started, calls = asyncio.Event(), []

        async def handle(request):
            calls.append(request.url.host)
            started.set()
            await asyncio.Event().wait()

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            pending = asyncio.create_task(service.complete_interaction("Atlas uses SurrealDB.", "Understood."))
            try:
                await asyncio.wait_for(started.wait(), timeout=1)
                pending.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await pending
            finally:
                if not pending.done():
                    pending.cancel()
                    await asyncio.gather(pending, return_exceptions=True)
        self.assertEqual(calls, ["provider-0.example"])
        self.assertEqual(await memory.read(), [])
        self.assertEqual(await journal.read(), before)
        self.assertEqual(await service._mind.load(), original)

    async def test_single_provider_review_can_use_its_one_repair_after_three_searches(self):
        for mode in ("plain", "native-custom", "native-provider"):
            with self.subTest(mode=mode):
                steps = [SEARCH, SEARCH, SEARCH, self.learning(memory_class="unknown"), self.learning()]
                model_type = NativeScriptedModel if mode == "native-custom" else ScriptedModel
                model = model_type(*steps)
                service, journal, memory = await self.service(model)
                records = await self.configured_recall_records(service)
                responses, bodies = iter(steps), []

                def handle(request):
                    bodies.append(json.loads(request.content))
                    return httpx.Response(200, json={"choices": [{"message": native_message(next(responses))}]})

                async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                    if mode == "native-provider":
                        service._steward_runtime = TaskModelDispatcher(records, client=client)
                    with patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock,
                               return_value=[]) as search:
                        completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                    self.assertEqual(search.await_count, 3)
                requests = bodies if mode == "native-provider" else [payload for _, payload in model.calls]
                self.assertEqual(len(requests), 5)
                budgets = [json.loads(request["messages"][1]["content"])["assessment_budget"]
                           for request in requests]
                self.assertEqual([budget["review_corrections_remaining"] for budget in budgets], [1, 1, 1, 1, 0])
                self.assertEqual([budget["search_allowed"] for budget in budgets], [True, True, True, False, False])
                self.assertEqual(completed["memory_review"]["validation_corrections"], 1)
                self.assertEqual(len(await memory.read()), 1)
                self.assertEqual(len([entry for entry in await journal.read() if entry.kind == "interaction"]), 1)

    async def test_custom_native_runtime_cannot_repeat_invalid_reviews_indefinitely(self):
        invalid = self.learning(memory_class="unknown")
        model = NativeScriptedModel(SEARCH, SEARCH, SEARCH, invalid, invalid, self.learning())
        service, journal, memory = await self.service(model)
        before, original = await journal.read(), await service._mind.load()
        with (
            patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock, return_value=[]) as search,
            self.assertRaisesRegex(StewardProtocolError, "memories.0.memory_class"),
        ):
            await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
        self.assertEqual(search.await_count, 3)
        self.assertEqual(len(model.calls), 5)
        self.assertEqual(await memory.read(), [])
        self.assertEqual(await journal.read(), before)
        self.assertEqual(await service._mind.load(), original)

    async def test_custom_session_claiming_unlimited_failover_still_has_a_finite_budget(self):
        for phase, limit in (("recall", 4), ("review", 5)):
            with self.subTest(phase=phase):
                invalid = {**SKIP, "summary": "Unsupported"} if phase == "recall" else self.learning(memory_class="unknown")
                valid = SKIP if phase == "recall" else self.learning()
                model = ScriptedModel(*([invalid] * limit), valid)
                rejected = []

                class UntrustedSession:
                    single_provider = False
                    candidate_count = 10**12
                    remaining_candidates = 10**12

                    async def prepare(self):
                        pass

                    async def execute(self, context, payload):
                        return await model.execute(context, payload)

                    def reject_response(self, error):
                        rejected.append(error)
                        return True

                class CustomRuntime:
                    supports_steward_action_tools = True
                    supports_steward_failover = True

                    def steward_assessment(self):
                        return UntrustedSession()

                service, journal, memory = await self.service(CustomRuntime())
                before, original = await journal.read(), await service._mind.load()
                with self.assertRaisesRegex(StewardProtocolError, "bounded custom-runtime decision budget"):
                    if phase == "recall":
                        await service.begin_interaction("Please format the supplied text.")
                    else:
                        await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                self.assertEqual(len(model.calls), limit)
                self.assertEqual(len(rejected), limit)
                budgets = [json.loads(payload["messages"][1]["content"])["assessment_budget"]
                           for _, payload in model.calls]
                self.assertTrue(all(budget["provider_candidates_total"] is None for budget in budgets))
                self.assertTrue(all(budget["provider_candidates_remaining"] is None for budget in budgets))
                self.assertEqual(await memory.read(), [])
                self.assertEqual(await journal.read(), before)
                self.assertEqual(await service._mind.load(), original)

    async def test_transport_failures_can_reach_later_provider_without_consuming_decisions(self):
        service, _, memory = await self.service(None)
        records = await self.configured_steward_pool(service, count=6)
        calls, bodies = [], []

        def handle(request):
            calls.append(request.url.host)
            bodies.append(json.loads(request.content))
            if request.url.host != "provider-5.example":
                return httpx.Response(429, json={"error": "busy"}, headers={"retry-after": "20"})
            return httpx.Response(200, json={"choices": [{"message": native_message(self.learning())}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.task_dispatcher.asyncio.sleep", new_callable=AsyncMock) as sleep:
                completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
            sleep.assert_not_awaited()
        self.assertEqual(calls, [f"provider-{index}.example" for index in range(6)])
        budgets = [json.loads(body["messages"][1]["content"])["assessment_budget"] for body in bodies]
        self.assertEqual([budget["provider_candidates_remaining"] for budget in budgets], [6, 5, 4, 3, 2, 1])
        self.assertEqual([budget["decision_attempts_remaining"] for budget in budgets], [9, 8, 7, 6, 5, 4])
        self.assertTrue(all(budget["provider_candidates_total"] == 6 for budget in budgets))
        self.assertTrue(all(budget["searches_completed"] == 0 for budget in budgets))
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)

    async def test_review_validation_failover_skips_an_existing_provider_cooldown(self):
        service, _, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        calls = []
        invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])

        def handle(request):
            calls.append(request.url.host)
            decision = invalid if request.url.host == "provider-0.example" else self.learning()
            return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            dispatcher = TaskModelDispatcher(records, client=client)
            endpoints = await dispatcher.endpoints.list()
            await dispatcher.routing.record_http_failure(
                endpoints[1], "model-1", 429, {"retry-after": "20"},
            )
            service._steward_runtime = dispatcher
            completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
        self.assertEqual(calls, ["provider-0.example", "provider-2.example"])
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)

    async def test_review_search_rechecks_new_cooldown_before_continuing_provider(self):
        service, _, memory = await self.service(None)
        records = await self.configured_steward_pool(service)
        calls = []
        invalid = self.learning(support=[{"source": "user_message", "quote": "Never supplied"}])

        def handle(request):
            calls.append(request.url.host)
            if request.url.host == "provider-0.example":
                decision = invalid
            elif request.url.host == "provider-1.example":
                decision = SEARCH
            else:
                decision = self.learning()
            return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            dispatcher = TaskModelDispatcher(records, client=client)
            endpoints = await dispatcher.endpoints.list()
            service._steward_runtime = dispatcher

            async def cool_backup(*args, **kwargs):
                await dispatcher.routing.record_http_failure(
                    endpoints[1], "model-1", 429, {"retry-after": "20"},
                )
                return []

            with patch("aicognitive_mind.steward_agent.candidates", side_effect=cool_backup):
                completed = await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
        self.assertEqual(calls, ["provider-0.example", "provider-1.example", "provider-2.example"])
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(await memory.read()), 1)

    async def test_invalid_recall_finish_advances_without_unsupported_recalled_content(self):
        for invalid in ({**SKIP, "summary": "An unsupported brief"}, BRIEF):
            with self.subTest(invalid=invalid):
                service, _, memory = await self.service(None)
                records = await self.configured_steward_pool(service)
                calls = []

                def handle(request):
                    calls.append(request.url.host)
                    decision = invalid if request.url.host == "provider-0.example" else SKIP
                    return httpx.Response(200, json={"choices": [{"message": native_message(decision)}]})

                async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                    service._steward_runtime = TaskModelDispatcher(records, client=client)
                    begun = await service.begin_interaction("Please format this text.")
                self.assertEqual(calls, ["provider-0.example", "provider-1.example"])
                self.assertEqual(begun["memory_assessment"]["outcome"], "no_recall_needed")
                self.assertEqual(begun["recalled_context"]["summary"], "")
                self.assertEqual(await memory.read(), [])

    async def test_http_search_budget_finishes_grounded_recall_and_corrects_review(self):
        service, journal, memory = await self.service(None)
        await memory.remember(DurableMemory(
            memory_class=MemoryClass.SEMANTIC, content="Atlas uses SurrealDB.",
            grounding=("Earlier project decision",),
        ), recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD)
        records = await self.configured_recall_records(service)
        steps = iter([
            SEARCH, SEARCH, SEARCH, BRIEF,
            SEARCH, SEARCH, self.learning(memory_class="unknown"), self.learning(),
        ])
        calls = []

        def handle(request):
            calls.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": native_message(next(steps))}]})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            service._steward_runtime = TaskModelDispatcher(records, client=client)
            with patch("aicognitive_mind.steward_agent.candidates", wraps=candidates) as search:
                begun = await service.begin_interaction("Atlas uses SurrealDB.")
                args = {
                    "user_message": "Atlas uses SurrealDB.", "response_text": "Understood.",
                    "idempotency_key": begun["idempotency_key"],
                }
                completed = await service.complete_interaction(**args)
                self.assertEqual(await service.complete_interaction(**args), completed)
        self.assertEqual(search.await_count, 5)
        self.assertEqual(len(calls), 8)
        self.assertEqual(begun["recalled_context"]["summary"], "Atlas uses SurrealDB.")
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(completed["memory_review"]["validation_corrections"], 1)
        self.assertEqual(len([entry for entry in await journal.read() if entry.kind == "interaction"]), 1)
        budgets = [json.loads(call["messages"][1]["content"])["assessment_budget"] for call in calls]
        self.assertEqual([budget["decision_attempts_remaining"] for budget in budgets],
                         [4, 3, 2, 1, 5, 4, 3, 2])
        self.assertTrue(all(budget["provider_candidates_total"] == 1 for budget in budgets))
        self.assertTrue(all(budget["provider_candidates_remaining"] == 1 for budget in budgets))
        self.assertEqual(budgets[7]["review_corrections_remaining"], 0)
        for index, call in enumerate(calls):
            searches_exhausted = index == 3
            self.assertEqual(budgets[index]["search_allowed"], not searches_exhausted)
            validator = Draft202012Validator(call["tools"][0]["function"]["parameters"])
            self.assertEqual(validator.is_valid({"decision": SEARCH}), not searches_exhausted)

    async def test_plain_runtime_final_schema_finishes_after_three_searches(self):
        model = ScriptedModel(SEARCH, SEARCH, SEARCH, BRIEF, NOTHING)
        service, _, memory = await self.service(model)
        await memory.remember(DurableMemory(
            memory_class=MemoryClass.SEMANTIC, content="Atlas uses SurrealDB.",
            grounding=("Earlier project decision",),
        ), recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD)
        begun = await service.begin_interaction("What database does Atlas use?")
        completed = await service.complete_interaction(
            "What database does Atlas use?", "Atlas uses SurrealDB.",
            idempotency_key=begun["idempotency_key"],
        )
        self.assertEqual(begun["recalled_context"]["summary"], "Atlas uses SurrealDB.")
        self.assertEqual(completed["status"], "interaction_committed")
        self.assertEqual(len(model.calls), 5)
        payload = model.calls[3][1]
        schema = json.loads(payload["messages"][0]["content"].split("PHASE SCHEMA:\n", 1)[1])
        self.assertTrue(Draft202012Validator(schema).is_valid(BRIEF))
        self.assertFalse(Draft202012Validator(schema).is_valid(SEARCH))
        self.assertEqual(json.loads(payload["messages"][1]["content"])["assessment_budget"], {
            "decision_attempts_remaining": 1, "provider_candidates_total": None,
            "provider_candidates_remaining": None, "searches_remaining": 0,
            "search_allowed": False, "searches_completed": 3,
            "review_corrections_remaining": 0,
        })

    async def test_fourth_search_is_rejected_before_lookup_without_state_changes(self):
        for native in (False, True):
            for phase in ("recall", "review"):
                with self.subTest(native=native, phase=phase):
                    model = ScriptedModel(SEARCH, SEARCH, SEARCH, SEARCH, SEARCH)
                    service, journal, memory = await self.service(model)
                    records = await self.configured_recall_records(service)
                    before, original = await journal.read(), await service._mind.load()
                    calls = []

                    def handle(request):
                        calls.append(json.loads(request.content))
                        return httpx.Response(200, json={"choices": [{"message": native_message(SEARCH)}]})

                    async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
                        if native:
                            service._steward_runtime = TaskModelDispatcher(records, client=client)
                        with (
                            patch("aicognitive_mind.steward_agent.candidates", new_callable=AsyncMock, return_value=[]) as search,
                            self.assertRaisesRegex(
                                StewardAssessmentExhausted if native else StewardProtocolError,
                                "exhaust" if native else "validation failed",
                            ),
                        ):
                            if phase == "recall":
                                await service.begin_interaction("What database does Atlas use?")
                            else:
                                await service.complete_interaction("Atlas uses SurrealDB.", "Understood.")
                    self.assertEqual(search.await_count, 3)
                    self.assertEqual(len(calls) if native else len(model.calls), 5 if phase == "review" else 4)
                    self.assertEqual(await journal.read(), before)
                    self.assertEqual(await service._mind.load(), original)
                    self.assertEqual(await memory.read(), [])

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
            self.assertEqual({
                branch["properties"]["action"]["const"]
                for branch in parameters["properties"]["decision"]["oneOf"]
            }, {"search", "finish"})
            self.assertNotIn("PHASE SCHEMA", call["messages"][0]["content"])
            self.assertTrue(all(
                "tool_calls" not in message and "tool_call_id" not in message
                for message in call["messages"]
            ))
        recall_branches = calls[0]["tools"][0]["function"]["parameters"]["properties"]["decision"]["oneOf"]
        review_branches = calls[2]["tools"][0]["function"]["parameters"]["properties"]["decision"]["oneOf"]
        recall_finish = next(branch for branch in recall_branches if branch["properties"]["action"]["const"] == "finish")
        review_finish = next(branch for branch in review_branches if branch["properties"]["action"]["const"] == "finish")
        self.assertIn("outcome", recall_finish["properties"])
        self.assertNotIn("memories", recall_finish["properties"])
        self.assertIn("memories", review_finish["properties"])
        self.assertNotIn("outcome", review_finish["properties"])
        artifact = review_finish["properties"]["memories"]["items"]["properties"]["artifacts"]["items"]
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
            ("name", "RecallFinish"), ("name", "ReviewFinish"),
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
        self.assertIn("AXIOM TASK FOUNDATION", calls[1]["messages"][0]["content"])
        self.assertEqual(result["memory_assessment"]["outcome"], "no_recall_needed")


if __name__ == "__main__":
    unittest.main()
