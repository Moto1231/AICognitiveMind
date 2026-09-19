import re
from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import MindAlreadyInitializedError


class MongoRuntime:
    def __init__(self, uri: str, database_name: str) -> None:
        self.client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri)
        self.database: AsyncDatabase[dict[str, Any]] = self.client[database_name]

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self.database["journal"].create_index([("occurred_at", ASCENDING)])
        await self.database["memory"].create_index([("formed_at", ASCENDING)])
        await self.database["memory"].create_index([("associations", ASCENDING)])
        await self.database["diagnostics"].create_index([("observed_at", ASCENDING)])

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    async def close(self) -> None:
        await self.client.close()


class MongoMindStore:
    """Stores exactly one root cognitive document for this deployment."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["mind"]

    async def initialize(self, mind: CognitiveMind) -> CognitiveMind:
        if await self._collection.find_one({}, {"_id": 1}) is not None:
            raise MindAlreadyInitializedError("This instance already contains its mind")
        await self._collection.insert_one(mind.model_dump(mode="python"))
        return mind

    async def load(self) -> CognitiveMind | None:
        document = await self._collection.find_one({}, {"_id": 0})
        return CognitiveMind.model_validate(document) if document else None


class MongoJournalStore:
    """Append/read-only cognitive journal with no domain keys or references."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["journal"]
        self._policy = policy or PermissionPolicy()

    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        await self._collection.insert_one(entry.model_dump(mode="python"))
        return entry

    async def read(self) -> list[JournalEntry]:
        cursor = self._collection.find({}, {"_id": 0}).sort("occurred_at", ASCENDING)
        return [JournalEntry.model_validate(document) async for document in cursor]

    def _portal_filter(
        self,
        *,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if kind:
            query["kind"] = kind

        if occurred_from or occurred_to:
            occurred: dict[str, datetime] = {}
            if occurred_from:
                occurred["$gte"] = occurred_from
            if occurred_to:
                occurred["$lte"] = occurred_to
            query["occurred_at"] = occurred

        if search:
            literal = re.escape(search)
            query["$or"] = [
                {"experience.input.content": {"$regex": literal, "$options": "i"}},
                {"experience.expression.content": {"$regex": literal, "$options": "i"}},
                {"experience.before.content": {"$regex": literal, "$options": "i"}},
                {"experience.after.content": {"$regex": literal, "$options": "i"}},
                {"experience.self_name": {"$regex": literal, "$options": "i"}},
                {"experience.foundational_values": {"$regex": literal, "$options": "i"}},
                {"experience.subject": {"$regex": literal, "$options": "i"}},
                {"experience.attribute": {"$regex": literal, "$options": "i"}},
                {"experience.phase": {"$regex": literal, "$options": "i"}},
                {"experience.competing_values.existing": {"$regex": literal, "$options": "i"}},
                {"experience.competing_values.proposed": {"$regex": literal, "$options": "i"}},
                {"experience.evidence.existing": {"$regex": literal, "$options": "i"}},
                {"experience.evidence.proposed": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.existing.provenance.source": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.existing.provenance.context": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.existing.provenance.condition": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.existing.basis": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.proposed.provenance.source": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.proposed.provenance.context": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.proposed.provenance.condition": {"$regex": literal, "$options": "i"}},
                {"experience.appraisals.proposed.basis": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.provenance_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.trigger": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.appraisal_gaps": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.context_observations": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.investigation_questions": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.status": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.candidate_side": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.candidate_value": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.blockers": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.basis": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.query": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.response": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.appraisal.provenance.source": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.appraisal.provenance.context": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.appraisal.provenance.condition": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.subject": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.attribute": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.value": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.provenance_independence": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.temporal_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.contextual_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.basis": {"$regex": literal, "$options": "i"}},
            ]
        return query

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> tuple[list[JournalEntry], int]:
        query = self._portal_filter(
            kind=kind,
            search=search,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )
        projection = {
            "_id": 0,
            "kind": 1,
            "occurred_at": 1,
            "experience.input.content": 1,
            "experience.expression.content": 1,
            "experience.before.content": 1,
            "experience.after.content": 1,
            "experience.self_name": 1,
            "experience.foundational_values": 1,
            "experience.subject": 1,
            "experience.attribute": 1,
            "experience.competing_values": 1,
            "experience.evidence": 1,
            "experience.appraisals": 1,
            "experience.deliberation": 1,
            "experience.current_evidence": 1,
            "experience.phase": 1,
            "experience.status": 1,
        }
        direction = DESCENDING if newest_first else ASCENDING
        cursor = (
            self._collection.find(query, projection)
            .sort("occurred_at", direction)
            .skip(offset)
            .limit(limit)
        )
        entries = [JournalEntry.model_validate(document) async for document in cursor]
        total = await self._collection.count_documents(query)
        return entries, total

    async def find_exact(
        self,
        *,
        kind: str,
        occurred_at: datetime,
    ) -> JournalEntry | None:
        document = await self._collection.find_one(
            {"kind": kind, "occurred_at": occurred_at},
            {"_id": 0},
        )
        return JournalEntry.model_validate(document) if document else None


class MongoDiagnosticStore:
    """Implementation observations deliberately isolated from cognitive documents."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["diagnostics"]

    async def record(self, observation: DiagnosticObservation) -> None:
        await self._collection.insert_one(observation.model_dump(mode="python"))

    async def read(self) -> list[DiagnosticObservation]:
        cursor = self._collection.find({}, {"_id": 0}).sort("observed_at", ASCENDING)
        return [DiagnosticObservation.model_validate(document) async for document in cursor]


class MongoMemoryStore:
    """Whole durable memories, curated by a Memory Steward without domain keys."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["memory"]
        self._policy = policy or PermissionPolicy()

    async def remember(
        self,
        memory: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        await self._collection.insert_one(memory.model_dump(mode="python"))
        return memory

    async def read(self) -> list[DurableMemory]:
        cursor = self._collection.find({}, {"_id": 0}).sort("formed_at", ASCENDING)
        return [DurableMemory.model_validate(document) async for document in cursor]

    def _portal_filter(
        self,
        *,
        memory_class: str | None = None,
        search: str | None = None,
        association: str | None = None,
        grounding: str | None = None,
        formed_from: datetime | None = None,
        formed_to: datetime | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {}
        if memory_class:
            query["memory_class"] = memory_class

        if formed_from or formed_to:
            formed: dict[str, datetime] = {}
            if formed_from:
                formed["$gte"] = formed_from
            if formed_to:
                formed["$lte"] = formed_to
            query["formed_at"] = formed

        clauses: list[dict[str, Any]] = []
        if search:
            literal = re.escape(search)
            clauses.append({
                "$or": [
                    {"content": {"$regex": literal, "$options": "i"}},
                    {"associations": {"$regex": literal, "$options": "i"}},
                    {"grounding": {"$regex": literal, "$options": "i"}},
                    {"artifacts.kind": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.subject": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.attribute": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.provenance.source": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.provenance.context": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.provenance.condition": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.basis": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.provenance_relationship": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.trigger": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.appraisal_gaps": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.context_observations": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.investigation_questions": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.resolution_readiness.status": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.resolution_readiness.candidate_side": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.resolution_readiness.candidate_value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.resolution_readiness.blockers": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.resolution_readiness.basis": {"$regex": literal, "$options": "i"}},
                ]
            })
        if association:
            clauses.append({
                "associations": {"$regex": re.escape(association), "$options": "i"}
            })
        if grounding:
            clauses.append({
                "grounding": {"$regex": re.escape(grounding), "$options": "i"}
            })
        if clauses:
            query["$and"] = clauses

        return query

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        memory_class: str | None = None,
        search: str | None = None,
        association: str | None = None,
        grounding: str | None = None,
        formed_from: datetime | None = None,
        formed_to: datetime | None = None,
    ) -> tuple[list[DurableMemory], int]:
        query = self._portal_filter(
            memory_class=memory_class,
            search=search,
            association=association,
            grounding=grounding,
            formed_from=formed_from,
            formed_to=formed_to,
        )
        direction = DESCENDING if newest_first else ASCENDING
        cursor = (
            self._collection.find(query, {"_id": 0})
            .sort("formed_at", direction)
            .skip(offset)
            .limit(limit)
        )
        memories = [DurableMemory.model_validate(document) async for document in cursor]
        total = await self._collection.count_documents(query)
        return memories, total

    async def replace_exact(
        self,
        original: DurableMemory,
        replacement: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory | None:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        selector = original.model_dump(mode="python")
        if not original.artifacts:
            selector.pop("artifacts", None)
            selector["$or"] = [
                {"artifacts": {"$exists": False}},
                {"artifacts": []},
            ]
        result = await self._collection.replace_one(
            selector,
            replacement.model_dump(mode="python"),
        )
        return replacement if result.matched_count == 1 else None
