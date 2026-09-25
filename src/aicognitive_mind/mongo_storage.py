# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

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
    SensoryEvidenceArtifact,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import MindAlreadyInitializedError


class MongoRuntime:
    def __init__(
        self,
        uri: str,
        database_name: str,
        *,
        legacy_mind_id: str = "axiom",
    ) -> None:
        self.client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(uri)
        self.database: AsyncDatabase[dict[str, Any]] = self.client[database_name]
        self.legacy_mind_id = legacy_mind_id

    async def _migrate_legacy_scope(self) -> None:
        """Attach the existing single-mind deployment to its first mind_id."""
        legacy = await self.database["mind"].find_one(
            {"mind_id": {"$exists": False}}
        )
        if legacy is not None:
            scoped = {key: value for key, value in legacy.items() if key != "_id"}
            scoped["mind_id"] = self.legacy_mind_id
            if await self.database["mind"].find_one(
                {"mind_id": self.legacy_mind_id},
                {"_id": 1},
            ) is None:
                await self.database["mind"].insert_one(
                    {"_id": self.legacy_mind_id, **scoped}
                )
            await self.database["mind"].delete_one({"_id": legacy["_id"]})

        for name in ("journal", "memory", "diagnostics", "evidence"):
            await self.database[name].update_many(
                {"mind_id": {"$exists": False}},
                {"$set": {"mind_id": self.legacy_mind_id}},
            )

        for name in ("runtime_records", "commit_receipts"):
            await self.database[name].update_many(
                {"mind_id": {"$exists": False}},
                [
                    {
                        "$set": {
                            "mind_id": self.legacy_mind_id,
                            "key": {"$toString": "$_id"},
                        }
                    }
                ],
            )

        await self.database["commit_state"].update_many(
            {"mind_id": {"$exists": False}},
            {"$set": {"mind_id": self.legacy_mind_id}},
        )

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self._migrate_legacy_scope()

        evidence_indexes = await self.database["evidence"].index_information()
        for name, info in evidence_indexes.items():
            if info.get("key") == [("sha256", 1), ("captured_at", 1)]:
                await self.database["evidence"].drop_index(name)

        await self.database["journal"].create_index(
            [("mind_id", ASCENDING), ("occurred_at", ASCENDING)]
        )
        await self.database["memory"].create_index(
            [("mind_id", ASCENDING), ("formed_at", ASCENDING)]
        )
        await self.database["memory"].create_index(
            [("mind_id", ASCENDING), ("associations", ASCENDING)]
        )
        await self.database["diagnostics"].create_index(
            [("mind_id", ASCENDING), ("observed_at", ASCENDING)]
        )
        await self.database["evidence"].create_index(
            [
                ("mind_id", ASCENDING),
                ("sha256", ASCENDING),
                ("captured_at", ASCENDING),
            ],
            unique=True,
        )
        await self.database["runtime_records"].create_index(
            [("mind_id", ASCENDING), ("key", ASCENDING)],
            unique=True,
        )
        await self.database["commit_state"].create_index(
            [("mind_id", ASCENDING)],
            unique=True,
        )
        await self.database["commit_receipts"].create_index(
            [("mind_id", ASCENDING), ("key", ASCENDING)],
            unique=True,
        )

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    async def close(self) -> None:
        await self.client.close()


class MongoMindStore:
    """Stores one root cognitive document for one mind_id."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        mind_id: str,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["mind"]
        self.mind_id = mind_id
        self._policy = policy or PermissionPolicy()

    async def initialize(self, mind: CognitiveMind) -> CognitiveMind:
        if await self._collection.find_one(
            {"mind_id": self.mind_id},
            {"_id": 1},
        ) is not None:
            raise MindAlreadyInitializedError("This mind is already initialized")
        from pymongo.errors import DuplicateKeyError
        try:
            await self._collection.insert_one(
                {
                    "_id": self.mind_id,
                    "mind_id": self.mind_id,
                    **mind.model_dump(mode="python"),
                }
            )
        except DuplicateKeyError as exc:
            raise MindAlreadyInitializedError("This mind is already initialized") from exc
        return mind

    async def load(self) -> CognitiveMind | None:
        document = await self._collection.find_one(
            {"mind_id": self.mind_id},
            {"_id": 0, "mind_id": 0},
        )
        return CognitiveMind.model_validate(document) if document else None

    async def replace_exact(
        self,
        original: CognitiveMind,
        replacement: CognitiveMind,
        recorded_by: CognitiveActor,
    ) -> CognitiveMind | None:
        self._policy.assert_allowed(
            recorded_by,
            CognitiveOperation.APPROVE_IDENTITY_REVISION,
        )
        result = await self._collection.replace_one(
            {"mind_id": self.mind_id, **original.model_dump(mode="python")},
            {
                "_id": self.mind_id,
                "mind_id": self.mind_id,
                **replacement.model_dump(mode="python"),
            },
        )
        return replacement if result.modified_count == 1 else None


class MongoJournalStore:
    """Append/read-only cognitive journal with no domain keys or references."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        mind_id: str,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["journal"]
        self.mind_id = mind_id
        self._policy = policy or PermissionPolicy()

    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        await self._collection.insert_one(
            {"mind_id": self.mind_id, **entry.model_dump(mode="python")}
        )
        return entry

    async def read(self) -> list[JournalEntry]:
        cursor = self._collection.find(
            {"mind_id": self.mind_id},
            {"_id": 0, "mind_id": 0},
        ).sort("occurred_at", ASCENDING)
        return [JournalEntry.model_validate(document) async for document in cursor]

    def _portal_filter(
        self,
        *,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: datetime | None = None,
        occurred_to: datetime | None = None,
    ) -> dict[str, Any]:
        query: dict[str, Any] = {"mind_id": self.mind_id}
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
                {"experience.before.self_name": {"$regex": literal, "$options": "i"}},
                {"experience.after.self_name": {"$regex": literal, "$options": "i"}},
                {"experience.self_name": {"$regex": literal, "$options": "i"}},
                {"experience.foundational_values": {"$regex": literal, "$options": "i"}},
                {"experience.subject": {"$regex": literal, "$options": "i"}},
                {"experience.attribute": {"$regex": literal, "$options": "i"}},
                {"experience.scope.kind": {"$regex": literal, "$options": "i"}},
                {"experience.scope.label": {"$regex": literal, "$options": "i"}},
                {"experience.phase": {"$regex": literal, "$options": "i"}},
                {"experience.from_value": {"$regex": literal, "$options": "i"}},
                {"experience.to_value": {"$regex": literal, "$options": "i"}},
                {"experience.status": {"$regex": literal, "$options": "i"}},
                {"experience.relationship": {"$regex": literal, "$options": "i"}},
                {"experience.existing_value": {"$regex": literal, "$options": "i"}},
                {"experience.existing_scope": {"$regex": literal, "$options": "i"}},
                {"experience.proposed_value": {"$regex": literal, "$options": "i"}},
                {"experience.proposed_scope": {"$regex": literal, "$options": "i"}},
                {"experience.basis": {"$regex": literal, "$options": "i"}},
                {"experience.existing_evidence": {"$regex": literal, "$options": "i"}},
                {"experience.proposed_evidence": {"$regex": literal, "$options": "i"}},
                {"experience.readiness_basis": {"$regex": literal, "$options": "i"}},
                {"experience.candidate_evidence": {"$regex": literal, "$options": "i"}},
                {"experience.superseded_evidence": {"$regex": literal, "$options": "i"}},
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
                {"experience.deliberation.scope.kind": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.scope.label": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.appraisal_gaps": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.context_observations": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.investigation_questions": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.status": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.candidate_side": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.candidate_value": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.blockers": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.resolution_readiness.basis": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.provenance_independence": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.temporal_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.contextual_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.basis": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.scope.kind": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.scope.label": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.existing_scope": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.tension_finding.proposed_scope": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.query": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.response_excerpt": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.appraisal.provenance.source": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.appraisal.provenance.context": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.appraisal.provenance.condition": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.semantic_interpretation.subject": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.semantic_interpretation.attribute": {"$regex": literal, "$options": "i"}},
                {"experience.deliberation.current_evidence_history.semantic_interpretation.value": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.query": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.response": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.appraisal.provenance.source": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.appraisal.provenance.context": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.appraisal.provenance.condition": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.subject": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.attribute": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.value": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.scope.kind": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.semantic_interpretation.scope.label": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.provenance_independence": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.temporal_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.contextual_relationship": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.basis": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.existing_scope": {"$regex": literal, "$options": "i"}},
                {"experience.current_evidence.tension_finding.proposed_scope": {"$regex": literal, "$options": "i"}},
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
            "experience.scope": 1,
            "experience.from_value": 1,
            "experience.to_value": 1,
            "experience.readiness_basis": 1,
            "experience.candidate_evidence": 1,
            "experience.superseded_evidence": 1,
            "experience.deliberation_revision": 1,
            "experience.relationship": 1,
            "experience.existing_value": 1,
            "experience.existing_scope": 1,
            "experience.proposed_value": 1,
            "experience.proposed_scope": 1,
            "experience.basis": 1,
            "experience.existing_evidence": 1,
            "experience.proposed_evidence": 1,
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
            {
                "mind_id": self.mind_id,
                "kind": kind,
                "occurred_at": occurred_at,
            },
            {"_id": 0, "mind_id": 0},
        )
        return JournalEntry.model_validate(document) if document else None


class MongoDiagnosticStore:
    """Implementation observations deliberately isolated per mind."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        mind_id: str,
    ) -> None:
        self._collection = database["diagnostics"]
        self.mind_id = mind_id

    async def record(self, observation: DiagnosticObservation) -> None:
        await self._collection.insert_one(
            {"mind_id": self.mind_id, **observation.model_dump(mode="python")}
        )

    async def read(self) -> list[DiagnosticObservation]:
        cursor = self._collection.find(
            {"mind_id": self.mind_id},
            {"_id": 0, "mind_id": 0},
        ).sort("observed_at", ASCENDING)
        return [DiagnosticObservation.model_validate(document) async for document in cursor]


class MongoMemoryStore:
    """Whole durable memories, curated by a Memory Steward without domain keys."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        mind_id: str,
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["memory"]
        self.mind_id = mind_id
        self._policy = policy or PermissionPolicy()

    async def remember(
        self,
        memory: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        await self._collection.insert_one(
            {"mind_id": self.mind_id, **memory.model_dump(mode="python")}
        )
        return memory

    async def read(self) -> list[DurableMemory]:
        cursor = self._collection.find(
            {"mind_id": self.mind_id},
            {"_id": 0, "mind_id": 0},
        ).sort("formed_at", ASCENDING)
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
        query: dict[str, Any] = {"mind_id": self.mind_id}
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
                    {"artifacts.payload.scope.kind": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.scope.label": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.proposed_scope.kind": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.proposed_scope.label": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.existing_scope.kind": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.existing_scope.label": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.status": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.from_value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.to_value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.readiness_basis": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.scope": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.relationship": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.existing_value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.existing_scope": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.proposed_value": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.proposed_scope": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.basis": {"$regex": literal, "$options": "i"}},
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
                    {"artifacts.payload.tension_finding.provenance_independence": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.tension_finding.temporal_relationship": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.tension_finding.contextual_relationship": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.tension_finding.basis": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.tension_finding.existing_scope": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.tension_finding.proposed_scope": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.query": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.response_excerpt": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.appraisal.provenance.source": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.appraisal.provenance.context": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.appraisal.provenance.condition": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.semantic_interpretation.subject": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.semantic_interpretation.attribute": {"$regex": literal, "$options": "i"}},
                    {"artifacts.payload.current_evidence_history.semantic_interpretation.value": {"$regex": literal, "$options": "i"}},
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
        selector = {
            "mind_id": self.mind_id,
            **original.model_dump(mode="python"),
        }
        if not original.artifacts:
            selector.pop("artifacts", None)
            selector["$or"] = [
                {"artifacts": {"$exists": False}},
                {"artifacts": []},
            ]
        result = await self._collection.replace_one(
            selector,
            {
                "mind_id": self.mind_id,
                **replacement.model_dump(mode="python"),
            },
        )
        return replacement if result.matched_count == 1 else None



class MongoEvidenceStore:
    """Immutable content-addressed sensory evidence, isolated per mind."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        mind_id: str,
    ) -> None:
        self._collection = database["evidence"]
        self.mind_id = mind_id

    async def preserve(self, artifact: SensoryEvidenceArtifact) -> SensoryEvidenceArtifact:
        selector = {
            "mind_id": self.mind_id,
            "sha256": artifact.sha256,
            "captured_at": artifact.captured_at,
        }
        existing = await self._collection.find_one(
            selector,
            {"_id": 0, "mind_id": 0},
        )
        if existing is not None:
            return SensoryEvidenceArtifact.model_validate(existing)
        await self._collection.insert_one(
            {"mind_id": self.mind_id, **artifact.model_dump(mode="python")}
        )
        return artifact

    async def read(self) -> list[SensoryEvidenceArtifact]:
        cursor = self._collection.find(
            {"mind_id": self.mind_id},
            {"_id": 0, "mind_id": 0},
        ).sort("captured_at", ASCENDING)
        return [
            SensoryEvidenceArtifact.model_validate(document)
            async for document in cursor
        ]

    async def find_exact(
        self,
        *,
        sha256: str,
        captured_at: datetime,
    ) -> SensoryEvidenceArtifact | None:
        document = await self._collection.find_one(
            {
                "mind_id": self.mind_id,
                "sha256": sha256,
                "captured_at": captured_at,
            },
            {"_id": 0, "mind_id": 0},
        )
        return SensoryEvidenceArtifact.model_validate(document) if document else None
