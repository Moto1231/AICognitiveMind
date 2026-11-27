"""Model-backed memory assessment; storage lookup is a tool, not the decision maker."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from importlib.resources import files
from typing import Annotated, Any, Literal
from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from aicognitive_mind.domain import DurableMemory, JournalEntry, JournalKind, MemoryClass
from aicognitive_mind.memory_steward import MemoryStewardTool, ProposeMemoryCall, _tokens
from aicognitive_mind.retrieval import candidates
from aicognitive_mind.task_behaviors import TaskExecutionContext
from aicognitive_mind.task_dispatcher import (
    ProviderHTTPError, StewardProviderPoolExhausted, TaskDispatchError, _StewardAssessment,
)


class StewardProtocolError(TaskDispatchError):
    """The Steward could not produce a grounded, valid assessment."""


class MissingTargetedSearchQuery(StewardProtocolError):
    """A targeted search did not contain any searchable words."""


class StewardAssessmentExhausted(StewardProtocolError):
    """Every eligible candidate failed this assessment; no cognitive writes commit."""

    def __init__(
        self, last_error: Exception | None = None, *, missing_query: bool = False,
    ) -> None:
        self.last_error = last_error
        self.missing_query = missing_query
        detail = f" Last failure: {last_error}" if last_error is not None else ""
        super().__init__("Memory Steward assessment exhausted its eligible provider pool." + detail)


class StewardAssessmentTimeout(StewardProtocolError):
    """The assessment's overall deadline expired, independently of its candidate pool."""

    def __init__(
        self, last_error: Exception | None = None, *, missing_query: bool = False,
    ) -> None:
        self.last_error = last_error
        self.missing_query = missing_query
        detail = f" Last failure: {last_error}" if last_error is not None else ""
        super().__init__("Memory Steward assessment timed out." + detail)


def recall_failure_message(error: StewardAssessmentExhausted | StewardAssessmentTimeout) -> str:
    """Give the host the known cause without provider bodies or user content."""
    if isinstance(error, StewardAssessmentTimeout):
        message = "Memory Steward recall timed out."
    else:
        message = "Memory Steward recall exhausted its available providers."
    if error.missing_query:
        message += " A targeted memory search was missing its query."
    if isinstance(error.last_error, ProviderHTTPError):
        message += f" The last provider returned HTTP {error.last_error.status_code}."
    elif isinstance(error.last_error, StewardProtocolError) and not error.missing_query:
        message += " The last provider returned an invalid recall decision."
    return message


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Search(Step):
    action: Literal["search"]
    source: Literal["memory", "journal", "recent"]
    query: str = Field(default="", max_length=1000)
    limit: int = Field(default=6, ge=1, le=8)
    meanings: tuple[str, ...] = Field(default=(), max_length=3)
    depth: Literal["quick", "deep"] = "quick"
    escalation_evidence: str = Field(default="", max_length=500)


# Supplied by the runtime even when an administrator customizes the skill. These
# are search protocol semantics, not canonical identity or learned personality.
RECALL_SEARCH_PROTOCOL = """
Recall search protocol:
Separate a reference to a prior decision from any new question (such as prices).
Interpret its intended meaning in the conversation, not just its literal words.
For a quick search, put up to three distinct plausible related search phrases in
meanings. These are hypotheses, never evidence. Keep unrelated interpretations
separate. A first miss is a limited search result, not proof nothing was recorded.
If the user challenges an earlier miss, choose depth=deep and quote exact evidence
from the current user message in escalation_evidence. Use working context only
to resolve the subject, never to reuse an older pushback as a new escalation. Do not
escalate merely because there was a first miss. Deep mode remains active for this
assessment. Reformulate the unresolved intent, search both memory and journal,
and evaluate the bounded unfiltered sample as well as targeted results by meaning.
When a question depends on who said something, search for the person's name
and check the source's journal_speaker artifact or journal interaction_speaker.
This identifies the source, not who the statement describes. Do not infer a
speaker from an unattributed memory or collapse two speakers into one.
Do not invent source facts, merge distinct plans, or demand an exact date.
No-recall remains valid when the supplied context already answers the question.
Searches remain bounded to three actions, each with at most four targeted queries
and one recent sample. A recent sample is not a global semantic index; disclose
unresolved recall, rather than claiming that all history was searched.
"""


class RecallFinish(Step):
    action: Literal["finish"]
    outcome: Literal["no_recall_needed", "no_relevant_memory", "recalled"]
    reason: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=3000)
    references: tuple[str, ...] = Field(default=(), max_length=6)


class Support(Step):
    source: Literal["user_message", "current_evidence", "response_text"]
    quote: str = Field(min_length=1, max_length=1500)


class ReviewedMemory(ProposeMemoryCall):
    model_config = ConfigDict(extra="forbid")
    # These legacy proposal fields are optional for the independent reviewer.
    # Grounding is derived from validated support, never from model assertions.
    action: Literal["propose_memory"] = "propose_memory"
    grounding: tuple[str, ...] = ()
    support: tuple[Support, ...] = Field(min_length=1, max_length=6)


class ReviewFinish(Step):
    action: Literal["finish"]
    reason: str = Field(min_length=1, max_length=500)
    memories: tuple[ReviewedMemory, ...] = Field(default=(), max_length=6)
    references: tuple[str, ...] = Field(default=(), max_length=6)
    evidence_indices: tuple[int, ...] = Field(default=(), max_length=24)
    transition_indices: tuple[int, ...] = Field(default=(), max_length=12)
    reframe_indices: tuple[int, ...] = Field(default=(), max_length=12)


RECALL_STEPS = TypeAdapter(Annotated[Search | RecallFinish, Field(discriminator="action")])
REVIEW_STEPS = TypeAdapter(Annotated[Search | ReviewFinish, Field(discriminator="action")])


class RecallAction(Step):
    decision: Annotated[Search | RecallFinish, Field(discriminator="action")]


class ReviewAction(Step):
    decision: Annotated[Search | ReviewFinish, Field(discriminator="action")]


class RecallFinishAction(Step):
    decision: RecallFinish


class ReviewFinishAction(Step):
    decision: ReviewFinish


def inline_action_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Inline local schema references without exposing model labels to the provider."""
    def walk(node: Any, active: tuple[str, ...] = ()) -> Any:
        if isinstance(node, bool):
            return node
        if not isinstance(node, dict):
            raise StewardProtocolError("Memory Steward provider schema contains an invalid node.")
        result = {
            key: value for key, value in node.items()
            if key not in {"$ref", "$defs", "definitions", "title", "discriminator"}
        }
        for key in ("properties", "patternProperties", "dependentSchemas"):
            if key in result:
                result[key] = {name: walk(value, active) for name, value in result[key].items()}
        for key in (
            "additionalProperties", "unevaluatedProperties", "propertyNames", "contains",
            "items", "additionalItems", "unevaluatedItems", "not", "if", "then", "else",
            "contentSchema",
        ):
            if key in result:
                value = result[key]
                result[key] = (
                    [walk(item, active) for item in value] if isinstance(value, list)
                    else walk(value, active)
                )
        for key in ("allOf", "anyOf", "oneOf", "prefixItems"):
            if key in result:
                result[key] = [walk(value, active) for value in result[key]]
        if "dependencies" in result:
            result["dependencies"] = {
                name: walk(value, active) if isinstance(value, (dict, bool)) else value
                for name, value in result["dependencies"].items()
            }
        if "$ref" not in node:
            return result
        reference = node["$ref"]
        if not isinstance(reference, str) or not (reference == "#" or reference.startswith("#/")):
            raise StewardProtocolError("Memory Steward provider schema requires local references.")
        if reference in active:
            raise StewardProtocolError("Memory Steward provider schema has a cyclic reference.")
        target: Any = schema
        try:
            for part in unquote(reference[2:]).split("/") if reference != "#" else ():
                part = part.replace("~1", "/").replace("~0", "~")
                if isinstance(target, list):
                    if not part.isdigit() or str(int(part)) != part:
                        raise ValueError("Invalid schema array pointer")
                    target = target[int(part)]
                else:
                    target = target[part]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise StewardProtocolError(
                "Memory Steward provider schema has an unresolvable reference."
            ) from exc
        resolved = walk(target, (*active, reference))
        return {**result, "allOf": [resolved, *result.get("allOf", [])]} if result else resolved

    return walk(schema)


def steward_action_tools(phase: str, *, finish_only: bool = False) -> list[dict[str, Any]]:
    """Expose one fixed provider function containing the existing phase decision."""
    if phase not in {"recall", "review"}:
        raise ValueError("Unknown Memory Steward phase")
    if finish_only:
        wrapper = RecallFinishAction if phase == "recall" else ReviewFinishAction
    else:
        wrapper = RecallAction if phase == "recall" else ReviewAction
    return [{"type": "function", "function": {
        "name": "steward_action",
        "description": (
            "Finish this assessment with one validated decision; no search calls remain."
            if finish_only else "Submit one validated search or finish decision for this assessment."
        ),
        "parameters": inline_action_schema(wrapper.model_json_schema()),
    }}]


class ModelMemorySteward(MemoryStewardTool):
    """Use the configured Memory Recall model and fallbacks for both lifecycle decisions."""

    def __init__(self, *args: Any, runtime: Any, **kwargs: Any) -> None:
        super().__init__(*args, runtime=runtime, **kwargs)
        self.runtime = runtime
        self.skill_records: Any | None = None
        self._records: dict[str, DurableMemory | JournalEntry] = {}
        self._search_count = 0
        self._search_budget_start = 0
        self.assessment: dict[str, Any] = {}
        self._public_context: dict[str, Any] = {}
        self._validation_corrections = 0
        self.assessment_timeout_seconds = 60.0
        self._recall_depth = "quick"
        self._search_sources: set[str] = set()
        self._search_trace: list[dict[str, Any]] = []

    async def _run(
        self, phase: Literal["recall", "review"], result: dict[str, Any],
        *, validate_finish: Callable[[Any], None] | None = None,
        function_override: str | None = None,
    ) -> Any:
        provider_session: Any = None
        last_rejection: StewardProtocolError | None = None
        missing_query = False
        deadline = asyncio.timeout(self.assessment_timeout_seconds)
        try:
            async with deadline:
                adapter = RECALL_STEPS if phase == "recall" else REVIEW_STEPS
                finish_adapter = TypeAdapter(RecallFinish if phase == "recall" else ReviewFinish)
                native_actions = getattr(self.runtime, "supports_steward_action_tools", False) is True
                provider_session = (
                    self.runtime.steward_assessment()
                    if native_actions and getattr(self.runtime, "supports_steward_failover", False) is True
                    else None
                )
                records = self.skill_records
                if records is None:
                    records = getattr(getattr(self.runtime, "assignments", None), "records", None)
                skill_enabled = True
                if records is None:
                    # Standalone test/custom runtimes without Mind storage retain defaults.
                    skill = files("aicognitive_mind").joinpath("skills/memory-steward/SKILL.md").read_text()
                else:
                    from aicognitive_mind.effective_skills import EffectiveSkillRegistry

                    configured = await EffectiveSkillRegistry(records).get("memory-steward")
                    skill_enabled = bool(configured and configured["enabled"])
                    skill = configured["content"] if skill_enabled else ""
                from aicognitive_mind.cognitive_configuration import (
                    CognitiveConfigurationRegistry, function_defaults, steward_instruction_parts,
                )

                function_id = function_override or ("recall" if phase == "recall" else "save")
                overrides = {}
                if records is None:
                    functions = {}
                else:
                    configuration = await CognitiveConfigurationRegistry(records).effective()
                    functions = configuration["functions"]
                    overrides = configuration["function_overrides"]
                if skill_enabled and function_override is None:
                    common, recall_text, save_text = steward_instruction_parts(skill)
                    phase_text = (
                        functions[function_id] if function_id in overrides else
                        (recall_text if phase == "recall" else save_text)
                    )
                    skill = "\n\n".join(part for part in (common, phase_text) if part)
                elif function_override is None and function_id in overrides:
                    skill = functions[function_id]
                if function_override is not None:
                    common = steward_instruction_parts(skill)[0] if skill_enabled else ""
                    policy = functions[function_id] if functions else function_defaults()[function_id]
                    skill = "\n\n".join(part for part in (common, policy) if part)
                if phase == "recall" and skill_enabled:
                    skill += "\n\n" + RECALL_SEARCH_PROTOCOL
                context = {
                    "phase": phase,
                    "identity": self._mind.identity.model_dump(mode="json"),
                    "current_state": self._current_state,
                    "host_working_context": self._working_context,
                    "user_message": self._input_text,
                    **result,
                }
                messages = [
                    {
                        "role": "system",
                        "content": skill + (
                            "\n\nCall steward_action with one decision matching its parameter schema."
                            if native_actions else "\n\nPHASE SCHEMA:\n" + json.dumps(adapter.json_schema())
                        ),
                    },
                    {"role": "user", "content": json.dumps(context, default=str)},
                ]
                self._validation_corrections = 0
                if provider_session is not None:
                    await provider_session.prepare()
                # Only the real dispatcher owns a trusted finite candidate snapshot.
                # A custom session claiming endless failover must still stop promptly.
                finite_pool = type(provider_session) is _StewardAssessment
                candidate_count = provider_session.candidate_count if finite_pool else None
                searches_at_start = self._search_count
                self._search_budget_start = searches_at_start
                singleton_review = phase == "review" and (
                    provider_session is None or provider_session.single_provider
                )
                recall_correction = phase == "recall"
                decision_limit = (
                    candidate_count + 3 + int(singleton_review or recall_correction)
                    if finite_pool else 5
                )
                for decision_index in range(decision_limit):
                    if not finite_pool and recall_correction and decision_index >= 4 and not missing_query:
                        break
                    searches_completed = self._search_count - searches_at_start
                    searches_remaining = max(0, 3 - searches_completed)
                    finish_only = searches_remaining == 0
                    round_adapter = finish_adapter if finish_only else adapter
                    review_corrections = int(singleton_review and not self._validation_corrections)
                    recall_corrections = int(recall_correction and not missing_query and not finish_only)
                    corrections_remaining = review_corrections + recall_corrections
                    remaining_candidates = provider_session.remaining_candidates if finite_pool else None
                    decisions_remaining = decision_limit - decision_index
                    if finite_pool:
                        decisions_remaining = min(
                            decisions_remaining,
                            searches_remaining + remaining_candidates + corrections_remaining,
                        )
                    elif phase == "recall":
                        decisions_remaining = min(
                            decisions_remaining, searches_remaining + 1 + recall_corrections,
                        )
                    context["recall_search_state"] = {
                        "depth": self._recall_depth,
                        "sources_checked": sorted(self._search_sources),
                        "search_trace": self._search_trace,
                    }
                    context["assessment_budget"] = {
                        "decision_attempts_remaining": decisions_remaining,
                        "provider_candidates_total": candidate_count,
                        "provider_candidates_remaining": remaining_candidates,
                        "searches_remaining": searches_remaining,
                        "search_allowed": not finish_only,
                        "searches_completed": searches_completed,
                        "review_corrections_remaining": review_corrections,
                    }
                    if recall_corrections:
                        context["assessment_budget"]["recall_corrections_remaining"] = recall_corrections
                    messages[1]["content"] = json.dumps(context, default=str)
                    if not native_actions:
                        messages[0]["content"] = (
                            skill + "\n\nPHASE SCHEMA:\n" + json.dumps(round_adapter.json_schema())
                        )
                    payload: dict[str, Any] = {
                        "operation": "chat", "messages": messages, "temperature": 0,
                    }
                    if native_actions:
                        payload["steward_action_phase"] = phase
                        payload["steward_finish_only"] = finish_only
                    else:
                        payload["response_format"] = {"type": "json_object"}
                    runtime = provider_session if provider_session is not None else self.runtime
                    raw = await runtime.execute(
                        TaskExecutionContext(task="memory_recall"), payload,
                    )
                    try:
                        if not isinstance(raw, str):
                            raise StewardProtocolError("Memory Steward returned non-text content.")
                        response = raw.strip()
                        if response.startswith("```") and response.endswith("```"):
                            response = response.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                        step = round_adapter.validate_json(response)
                        if isinstance(step, Search):
                            self._validate_search(step, phase)
                        elif validate_finish is not None:
                            validate_finish(step)
                    except (ValidationError, StewardProtocolError) as exc:
                        if isinstance(exc, ValidationError):
                            detail = "; ".join(
                                f"{'.'.join(map(str, error['loc'])) or 'response'}: "
                                f"{error['msg']}"
                                for error in exc.errors(include_input=False, include_url=False)[:5]
                            )[:1000]
                        else:
                            detail = str(exc)
                        last_rejection = StewardProtocolError(detail)
                        is_missing_query = isinstance(exc, MissingTargetedSearchQuery)
                        can_correct_recall = bool(is_missing_query and recall_corrections)
                        if phase == "recall" and is_missing_query:
                            missing_query = True
                        can_correct = bool(review_corrections or can_correct_recall)
                        has_fallback = False
                        if provider_session is not None and not can_correct:
                            has_fallback = provider_session.reject_response(last_rejection)
                        if not (can_correct or has_fallback):
                            if finite_pool:
                                raise StewardAssessmentExhausted(last_rejection, missing_query=missing_query) from exc
                            raise StewardProtocolError(
                                f"Memory Steward {phase} validation failed: {detail}"
                            ) from exc
                        if phase == "review":
                            self._validation_corrections += 1
                        messages.extend([
                            {"role": "assistant", "content": raw if isinstance(raw, str) else str(raw)},
                            {"role": "user", "content": json.dumps({
                                "validation_error": detail,
                                "correction": (
                                    "Return one corrected recall action. Supply a searchable query "
                                    "for a targeted memory or journal search."
                                    if can_correct_recall else
                                    f"Return one corrected {phase} matching the phase schema. "
                                    "Preserve supported decisions and their classifications; "
                                    "do not invent evidence or silently discard valid learning. "
                                    "Explain any changed decision in the review reason."
                                ),
                            })},
                        ])
                        continue
                    if not isinstance(step, Search):
                        return step
                    found = await self._search(step)
                    messages.extend([
                        {"role": "assistant", "content": raw},
                        {"role": "user", "content": json.dumps({"search_results": found})},
                    ])
                detail = f" Last failure: {last_rejection}" if last_rejection is not None else ""
                raise StewardProtocolError(
                    "Memory Steward exceeded its bounded custom-runtime decision budget." + detail
                )
        except StewardProviderPoolExhausted as exc:
            raise StewardAssessmentExhausted(exc.last_error, missing_query=missing_query) from exc
        except TimeoutError as exc:
            if not deadline.expired():
                raise
            last_error = getattr(provider_session, "last_error", None) or last_rejection
            raise StewardAssessmentTimeout(last_error, missing_query=missing_query) from exc

    def _validate_search(self, step: Search, phase: str = "recall") -> None:
        if step.source != "recent" and not _tokens(step.query):
            raise MissingTargetedSearchQuery("A targeted memory search requires a query.")
        if any(not _tokens(phrase) or len(phrase) > 300 for phrase in step.meanings):
            raise StewardProtocolError("Meaning queries require searchable words and at most 300 characters.")
        if phase != "recall" and (step.meanings or step.depth != "quick"):
            raise StewardProtocolError("Meaning expansion and deep mode are recall-only.")
        if step.depth == "deep" and self._recall_depth != "deep":
            evidence = step.escalation_evidence.strip()
            if not evidence or evidence not in self._input_text:
                raise StewardProtocolError("Deep recall requires an exact current-user-message quote.")

    async def _search(self, step: Search) -> list[dict[str, Any]]:
        self._validate_search(step)
        if self._search_count - self._search_budget_start >= 3:
            raise StewardProtocolError("Recall search budget exhausted.")
        if step.depth == "deep":
            self._recall_depth = "deep"
        source = "journal" if step.source == "recent" else step.source
        self._search_sources.add(source)
        store = self._memory if source == "memory" else self._journal
        date = "formed_at" if source == "memory" else "occurred_at"
        phrases = ([step.query] if step.source == "recent" else
                   list(dict.fromkeys((step.query, *step.meanings))))
        buckets: list[list[DurableMemory | JournalEntry]] = []
        for phrase in phrases:
            bucket: list[DurableMemory | JournalEntry] = []
            tokens = set() if step.source == "recent" else _tokens(phrase)
            rows = await candidates(store, tokens, limit=step.limit * 2)
            rows = sorted(rows, key=lambda row: getattr(row, date), reverse=True)
            for row in rows:
                if isinstance(row, JournalEntry) and row.kind == JournalKind.CHECKPOINT:
                    continue
                encoded = row.model_dump_json()
                if tokens and not tokens.intersection(_tokens(encoded)):
                    continue
                if row not in bucket:
                    bucket.append(row)
            buckets.append(bucket)
        # Interleave interpretations: literal-word distractors must not consume
        # every slot before an alternative meaning has any chance to contribute.
        matched: list[DurableMemory | JournalEntry] = []
        for index in range(step.limit * 2):
            for bucket in buckets:
                if index < len(bucket) and bucket[index] not in matched:
                    matched.append(bucket[index])
        # A bounded unfiltered sample lets the model evaluate records whose words
        # differ from every query. This deliberately does not promise all-history
        # semantic retrieval. Reserve half the result slots so lexical distractors
        # cannot crowd that sample out; preserve existing mind-scoped store reads.
        sample: list[DurableMemory | JournalEntry] = []
        if self._recall_depth == "deep" and step.source != "recent":
            rows = await candidates(store, set(), limit=step.limit * 2)
            rows = sorted(rows, key=lambda row: getattr(row, date), reverse=True)
            sample = [row for row in rows if row not in matched and not (
                isinstance(row, JournalEntry) and row.kind == JournalKind.CHECKPOINT
            )][:max(1, step.limit // 2)]
        selected = matched[:step.limit - len(sample)] + sample
        found = []
        for row in selected:
            payload = row.model_dump(mode="json")
            encoded = json.dumps(payload, default=str)
            reference = next((ref for ref, known in self._records.items() if known == row), None)
            if reference is None:
                reference = f"record_{len(self._records) + 1}"
                self._records[reference] = row
            found.append({
                "reference": reference,
                "record": payload if len(encoded) <= 12000 else encoded[:12000],
                "truncated": len(encoded) > 12000,
            })
        self._search_count += 1
        self._search_trace.append({
            "source": source, "queries": phrases, "depth": self._recall_depth,
            "returned": len(found), "unfiltered_sample": len(sample),
        })
        return found

    def _validate_references(self, references: tuple[str, ...]) -> None:
        if len(set(references)) != len(references) or any(
            reference not in self._records for reference in references
        ):
            raise StewardProtocolError("Memory Steward selected an unknown or repeated source.")

    def _select(self, references: tuple[str, ...], summary: str) -> None:
        self._validate_references(references)
        selected = [self._records[reference] for reference in references]
        self._brief = self._build_brief(
            focus=self._input_text,
            memories=tuple(row for row in selected if isinstance(row, DurableMemory)),
            experiences=tuple(row for row in selected if isinstance(row, JournalEntry)),
        ).model_copy(update={"summary": summary})

    def _validate_recall(self, finished: RecallFinish) -> None:
        """Validate the whole decision before accepting its provider's result."""
        if finished.outcome == "no_recall_needed" and self._search_count:
            raise StewardProtocolError(
                "No-recall assessment cannot claim a search was skipped after searching."
            )
        if finished.outcome == "no_relevant_memory" and not self._search_count:
            raise StewardProtocolError("No-relevant-memory requires an actual search.")
        if (finished.outcome == "no_relevant_memory" and self._recall_depth == "deep"
                and not {"memory", "journal"}.issubset(self._search_sources)):
            raise StewardProtocolError("Deep recall must check memory and journal before a miss.")
        if finished.outcome == "recalled":
            if not finished.references or not finished.summary.strip():
                raise StewardProtocolError("A recalled brief requires sources and a summary.")
        elif finished.references or finished.summary:
            raise StewardProtocolError("An empty recall outcome cannot include recalled content.")
        self._validate_references(finished.references)

    async def _recall(self, requested_focus: str) -> Any:
        finished = await self._run("recall", {}, validate_finish=self._validate_recall)
        self._select(finished.references, finished.summary)
        self.assessment = {"outcome": finished.outcome, "reason": finished.reason}
        self._public_context = {
            **self.assessment, "summary": finished.summary,
            "search_depth": self._recall_depth, "search_trace": self._search_trace,
        }
        if finished.references:
            self._public_context["sources"] = [
                self._source(reference) for reference in finished.references
            ]
        return self._brief

    def _source(self, reference: str) -> dict[str, Any]:
        row = self._records[reference]
        result: dict[str, Any] = {"reference": reference}
        if isinstance(row, DurableMemory):
            result.update(kind=row.memory_class.value, occurred_at=row.formed_at.isoformat())
            speakers = list(dict.fromkeys(
                item.payload["name"] for item in row.artifacts
                if item.kind == "journal_speaker" and isinstance(item.payload.get("name"), str)
            ))
            if speakers:
                result["journal_speakers"] = speakers[:8]
        else:
            from aicognitive_mind.memory_steward import _experience_evidence_references

            result.update(kind=row.kind.value, occurred_at=row.occurred_at.isoformat())
            evidence = _experience_evidence_references(row)
            if evidence:
                result["evidence_references"] = evidence
        return result

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        result = await super().invoke(arguments)
        if arguments.get("action") == "recall":
            result["status"] = self.assessment["outcome"]
            result["context"] = self.host_context()
        return result

    def host_context(self) -> dict[str, Any]:
        return dict(self._public_context)

    def state_context(self) -> dict[str, Any]:
        return {**super().state_context(), "recall_outcome": self.assessment.get("outcome")}

    async def review_interaction(
        self,
        response_text: str,
        proposed_memories: tuple[Any, ...],
        current_evidence: tuple[Any, ...],
        belief_transitions: tuple[Any, ...],
        belief_reframes: tuple[Any, ...],
        *, journal_review: bool = False,
    ) -> dict[str, Any]:
        def data(items: tuple[Any, ...]) -> list[dict[str, Any]]:
            return [item.model_dump(mode="json") for item in items]

        evidence_data = data(current_evidence)

        def validate(finished: ReviewFinish) -> None:
            self._validate_review(
                finished, response_text, current_evidence, belief_transitions, belief_reframes,
            )

        finished = await self._run(
            "review",
            {
                "response_text": response_text,
                "host_proposals": data(proposed_memories),
                "current_evidence": evidence_data,
                "belief_transitions": data(belief_transitions),
                "belief_reframes": data(belief_reframes),
            },
            validate_finish=validate,
            function_override="memory_review" if journal_review else None,
        )
        reviewed = self._validate_review(
            finished, response_text, current_evidence, belief_transitions, belief_reframes,
        )
        self._select(finished.references, "")
        self.assessment = {"outcome": "reviewed", "reason": finished.reason}
        if self._validation_corrections:
            self.assessment["validation_corrections"] = self._validation_corrections
        self._public_context = {**self.assessment, "searches": self._search_count}
        return reviewed

    def _validate_review(
        self, finished: ReviewFinish, response_text: str,
        current_evidence: tuple[Any, ...], belief_transitions: tuple[Any, ...],
        belief_reframes: tuple[Any, ...],
    ) -> dict[str, Any]:
        self._validate_references(finished.references)
        sources = {
            "user_message": [self._input_text],
            "response_text": [response_text],
            "current_evidence": [
                text
                for evidence in current_evidence
                for text in [evidence.response, *[a.relevant_content for a in evidence.articles]]
            ],
        }
        memories = []
        for index, candidate in enumerate(finished.memories):
            for support in candidate.support:
                if not support.quote.strip() or not any(
                    support.quote in text for text in sources[support.source]
                ):
                    raise StewardProtocolError(
                        f"Reviewed memory {index} ({candidate.memory_class.value}) has no "
                        f"matching {support.source} evidence quote."
                    )
                if (
                    support.source == "response_text"
                    and candidate.memory_class in {MemoryClass.SEMANTIC, MemoryClass.IDENTITY}
                ):
                    raise StewardProtocolError(
                        f"Reviewed memory {index} ({candidate.memory_class.value}) cannot use "
                        "response_text as factual grounding; use user_message or current_evidence."
                    )
            value = candidate.model_dump(exclude={"support"})
            value["grounding"] = tuple(
                f"{support.source}: {support.quote}" for support in candidate.support
            )
            memories.append(ProposeMemoryCall.model_validate(value))

        def selected(
            field: str, indices: tuple[int, ...], items: tuple[Any, ...],
        ) -> tuple[Any, ...]:
            if len(set(indices)) != len(indices) or any(i < 0 or i >= len(items) for i in indices):
                raise StewardProtocolError(
                    f"Memory Steward {field} contains an out-of-range or repeated index."
                )
            return tuple(items[i] for i in indices)

        return {
            "proposed_memories": tuple(memories),
            "current_evidence": selected(
                "evidence_indices", finished.evidence_indices, current_evidence,
            ),
            "belief_transitions": selected(
                "transition_indices", finished.transition_indices, belief_transitions,
            ),
            "belief_reframes": selected("reframe_indices", finished.reframe_indices, belief_reframes),
        }
