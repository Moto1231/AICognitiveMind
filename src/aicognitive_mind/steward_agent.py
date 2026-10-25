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
from aicognitive_mind.task_dispatcher import TaskDispatchError


class StewardProtocolError(TaskDispatchError):
    """The Steward could not produce a grounded, valid assessment."""


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Search(Step):
    action: Literal["search"]
    source: Literal["memory", "journal", "recent"]
    query: str = Field(default="", max_length=1000)
    limit: int = Field(default=6, ge=1, le=8)


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
        self.assessment: dict[str, Any] = {}
        self._public_context: dict[str, Any] = {}
        self._validation_corrections = 0

    async def _run(
        self, phase: Literal["recall", "review"], result: dict[str, Any],
        *, validate_finish: Callable[[Any], None] | None = None,
    ) -> Any:
        adapter = RECALL_STEPS if phase == "recall" else REVIEW_STEPS
        finish_adapter = TypeAdapter(RecallFinish if phase == "recall" else ReviewFinish)
        native_actions = getattr(self.runtime, "supports_steward_action_tools", False) is True
        records = self.skill_records
        if records is None:
            records = getattr(getattr(self.runtime, "assignments", None), "records", None)
        if records is None:
            # Standalone test/custom runtimes without Mind storage retain defaults.
            skill = files("aicognitive_mind").joinpath("skills/memory-steward/SKILL.md").read_text()
        else:
            from aicognitive_mind.effective_skills import EffectiveSkillRegistry

            configured = await EffectiveSkillRegistry(records).get("memory-steward")
            skill = configured["content"] if configured and configured["enabled"] else ""
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
        try:
            async with asyncio.timeout(60):
                for round_index in range(4):
                    final_round = round_index == 3
                    round_adapter = finish_adapter if final_round else adapter
                    context["assessment_budget"] = {
                        "model_calls_remaining": 4 - round_index,
                        "search_allowed": not final_round,
                        "searches_completed": self._search_count,
                        "review_corrections_remaining": (
                            min(1 - self._validation_corrections, 3 - round_index)
                            if phase == "review" else 0
                        ),
                    }
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
                        payload["steward_finish_only"] = final_round
                    else:
                        payload["response_format"] = {"type": "json_object"}
                    raw = await self.runtime.execute(
                        TaskExecutionContext(task="memory_recall"), payload,
                    )
                    if not isinstance(raw, str):
                        raise StewardProtocolError("Memory Steward returned non-text content.")
                    text = raw.strip()
                    if text.startswith("```") and text.endswith("```"):
                        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    try:
                        step = round_adapter.validate_json(text)
                        if not isinstance(step, Search) and validate_finish is not None:
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
                        if phase != "review" or self._validation_corrections or final_round:
                            raise StewardProtocolError(
                                f"Memory Steward {phase} validation failed"
                                f"{' on final call' if final_round else ''}: {detail}"
                            ) from exc
                        self._validation_corrections += 1
                        messages.extend([
                            {"role": "assistant", "content": raw},
                            {"role": "user", "content": json.dumps({
                                "validation_error": detail,
                                "correction": (
                                    "Return one corrected review matching the phase schema. "
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
                    messages.extend(
                        [
                            {"role": "assistant", "content": raw},
                            {"role": "user", "content": json.dumps({"search_results": found})},
                        ]
                    )
        except TimeoutError as exc:
            raise StewardProtocolError("Memory Steward assessment timed out.") from exc
        raise StewardProtocolError("Memory Steward exceeded its assessment round limit.")

    async def _search(self, step: Search) -> list[dict[str, Any]]:
        if step.source != "recent" and not _tokens(step.query):
            raise StewardProtocolError("A targeted memory search requires a query.")
        store = self._memory if step.source == "memory" else self._journal
        tokens = set() if step.source == "recent" else _tokens(step.query)
        rows = await candidates(store, tokens, limit=step.limit * 2)
        date = "formed_at" if step.source == "memory" else "occurred_at"
        rows = sorted(rows, key=lambda row: getattr(row, date), reverse=True)
        self._search_count += 1
        found = []
        for row in rows:
            if isinstance(row, JournalEntry) and row.kind == JournalKind.CHECKPOINT:
                continue
            payload = row.model_dump(mode="json")
            encoded = json.dumps(payload, default=str)
            if tokens and not tokens.intersection(_tokens(encoded)):
                continue
            reference = next((ref for ref, known in self._records.items() if known == row), None)
            if reference is None:
                reference = f"record_{len(self._records) + 1}"
                self._records[reference] = row
            found.append(
                {
                    "reference": reference,
                    "record": payload if len(encoded) <= 12000 else encoded[:12000],
                    "truncated": len(encoded) > 12000,
                }
            )
            if len(found) >= step.limit:
                break
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

    async def _recall(self, requested_focus: str) -> Any:
        finished = await self._run("recall", {})
        if finished.outcome == "no_recall_needed" and self._search_count:
            raise StewardProtocolError(
                "No-recall assessment cannot claim a search was skipped after searching."
            )
        if finished.outcome == "no_relevant_memory" and not self._search_count:
            raise StewardProtocolError("No-relevant-memory requires an actual search.")
        if finished.outcome == "recalled":
            if not finished.references or not finished.summary.strip():
                raise StewardProtocolError("A recalled brief requires sources and a summary.")
        elif finished.references or finished.summary:
            raise StewardProtocolError("An empty recall outcome cannot include recalled content.")
        self._select(finished.references, finished.summary)
        self.assessment = {"outcome": finished.outcome, "reason": finished.reason}
        self._public_context = {**self.assessment, "summary": finished.summary}
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
