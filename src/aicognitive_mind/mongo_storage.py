from typing import Any

from pymongo import ASCENDING, AsyncMongoClient
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
