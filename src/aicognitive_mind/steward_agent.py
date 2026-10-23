"""Model-backed memory assessment; storage lookup is a tool, not the decision maker."""

from __future__ import annotations

import asyncio
import json
from importlib.resources import files
from typing import Annotated, Any, Literal

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


class ModelMemorySteward(MemoryStewardTool):
    """Use the configured Memory Recall model and fallbacks for both lifecycle decisions."""

    def __init__(self, *args: Any, runtime: Any, **kwargs: Any) -> None:
        super().__init__(*args, runtime=runtime, **kwargs)
        self.runtime = runtime
        self._records: dict[str, DurableMemory | JournalEntry] = {}
        self._search_count = 0
        self.assessment: dict[str, Any] = {}
        self._public_context: dict[str, Any] = {}

    async def _run(self, phase: Literal["recall", "review"], result: dict[str, Any]) -> Any:
        adapter = RECALL_STEPS if phase == "recall" else REVIEW_STEPS
        skill = files("aicognitive_mind").joinpath("skills/memory-steward/SKILL.md").read_text()
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
                "content": skill + "\n\nPHASE SCHEMA:\n" + json.dumps(adapter.json_schema()),
            },
            {"role": "user", "content": json.dumps(context, default=str)},
        ]
        try:
            async with asyncio.timeout(60):
                for _ in range(4):
                    raw = await self.runtime.execute(
                        TaskExecutionContext(task="memory_recall"),
                        {"operation": "chat", "messages": messages, "temperature": 0},
                    )
                    if not isinstance(raw, str):
                        raise StewardProtocolError("Memory Steward returned non-text content.")
                    text = raw.strip()
                    if text.startswith("```") and text.endswith("```"):
                        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
                    try:
                        step = adapter.validate_json(text)
                    except ValidationError as exc:
                        raise StewardProtocolError(
                            "Memory Steward returned invalid phase JSON."
                        ) from exc
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

    def _select(self, references: tuple[str, ...], summary: str) -> None:
        if len(set(references)) != len(references) or any(
            reference not in self._records for reference in references
        ):
            raise StewardProtocolError("Memory Steward selected an unknown or repeated source.")
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
        finished = await self._run(
            "review",
            {
                "response_text": response_text,
                "host_proposals": data(proposed_memories),
                "current_evidence": evidence_data,
                "belief_transitions": data(belief_transitions),
                "belief_reframes": data(belief_reframes),
            },
        )
        self._select(finished.references, "")
        self.assessment = {"outcome": "reviewed", "reason": finished.reason}
        self._public_context = {**self.assessment, "searches": self._search_count}
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
        for candidate in finished.memories:
            if candidate.memory_class not in {
                MemoryClass.SEMANTIC,
                MemoryClass.PROCEDURAL,
                MemoryClass.REFLECTIVE,
            }:
                raise StewardProtocolError("Memory Steward cannot revise identity or values.")
            for support in candidate.support:
                if not support.quote.strip() or not any(
                    support.quote in text for text in sources[support.source]
                ):
                    raise StewardProtocolError(
                        "Memory Steward learning has no matching evidence quote."
                    )
                if (
                    support.source == "response_text"
                    and candidate.memory_class == MemoryClass.SEMANTIC
                ):
                    raise StewardProtocolError(
                        "An answer alone cannot ground an external semantic fact."
                    )
            value = candidate.model_dump(exclude={"support"})
            value["grounding"] = tuple(
                f"{support.source}: {support.quote}" for support in candidate.support
            )
            memories.append(ProposeMemoryCall.model_validate(value))

        def selected(indices: tuple[int, ...], items: tuple[Any, ...]) -> tuple[Any, ...]:
            if len(set(indices)) != len(indices) or any(i < 0 or i >= len(items) for i in indices):
                raise StewardProtocolError("Memory Steward selected an invalid review item.")
            return tuple(items[i] for i in indices)

        return {
            "proposed_memories": tuple(memories),
            "current_evidence": selected(finished.evidence_indices, current_evidence),
            "belief_transitions": selected(finished.transition_indices, belief_transitions),
            "belief_reframes": selected(finished.reframe_indices, belief_reframes),
        }
