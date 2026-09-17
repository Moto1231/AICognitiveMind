from typing import Any

from pymongo import ASCENDING, DESCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    FoundationalMemory,
    JournalEntry,
    WorkingMemoryState,
    utc_now,
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
        await self.database["foundation"].create_index(
            [("key", ASCENDING), ("version", ASCENDING)], unique=True
        )
        await self.database["foundation"].create_index(
            [("key", ASCENDING), ("active", ASCENDING)]
        )
        await self.database["diagnostics"].create_index([("observed_at", ASCENDING)])

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    async def close(self) -> None:
        await self.client.close()


class MongoMindStore:
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


class MongoFoundationStore:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["foundation"]

    async def seed(self, key: str, content: str) -> FoundationalMemory:
        existing = await self._collection.find_one(
            {"key": key}, {"_id": 0}, sort=[("version", DESCENDING)]
        )
        if existing is not None:
            return FoundationalMemory.model_validate(existing)
        record = FoundationalMemory(key=key, version=1, content=content, changed_by="bootstrap")
        await self._collection.insert_one(record.model_dump(mode="python"))
        return record

    async def revise(self, key: str, content: str, changed_by: str) -> FoundationalMemory:
        latest = await self._collection.find_one(
            {"key": key}, {"_id": 0, "version": 1}, sort=[("version", DESCENDING)]
        )
        next_version = int(latest["version"]) + 1 if latest is not None else 1
        await self._collection.update_many({"key": key, "active": True}, {"$set": {"active": False}})
        revised = FoundationalMemory(
            key=key, version=next_version, content=content, changed_by=changed_by
        )
        await self._collection.insert_one(revised.model_dump(mode="python"))
        return revised

    async def load_active(self, key: str) -> FoundationalMemory | None:
        document = await self._collection.find_one(
            {"key": key, "active": True}, {"_id": 0}, sort=[("version", DESCENDING)]
        )
        return FoundationalMemory.model_validate(document) if document else None

    async def read_history(self, key: str) -> list[FoundationalMemory]:
        cursor = self._collection.find({"key": key}, {"_id": 0}).sort("version", ASCENDING)
        return [FoundationalMemory.model_validate(document) async for document in cursor]


class MongoJournalStore:
    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["journal"]
        self._policy = policy or PermissionPolicy()

    async def append(self, entry: JournalEntry, recorded_by: CognitiveActor) -> JournalEntry:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        await self._collection.insert_one(entry.model_dump(mode="python"))
        return entry

    async def read(self) -> list[JournalEntry]:
        cursor = self._collection.find({}, {"_id": 0}).sort("occurred_at", ASCENDING)
        return [JournalEntry.model_validate(document) async for document in cursor]


class MongoDiagnosticStore:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["diagnostics"]

    async def record(self, observation: DiagnosticObservation) -> None:
        await self._collection.insert_one(observation.model_dump(mode="python"))

    async def read(self) -> list[DiagnosticObservation]:
        cursor = self._collection.find({}, {"_id": 0}).sort("observed_at", ASCENDING)
        return [DiagnosticObservation.model_validate(document) async for document in cursor]


class MongoMemoryStore:
    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database["memory"]
        self._policy = policy or PermissionPolicy()

    async def remember(
        self, memory: DurableMemory, recorded_by: CognitiveActor
    ) -> DurableMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        await self._collection.insert_one(memory.model_dump(mode="python"))
        return memory

    async def read(self) -> list[DurableMemory]:
        cursor = self._collection.find({}, {"_id": 0}).sort("formed_at", ASCENDING)
        return [DurableMemory.model_validate(document) async for document in cursor]


class MongoWorkingMemoryStore:
    """Single mutable present-context document, deliberately flushable at checkpoints."""

    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database["working_memory"]

    async def read(self) -> WorkingMemoryState:
        document = await self._collection.find_one({"slot": "current"}, {"_id": 0, "slot": 0})
        if document is None:
            return WorkingMemoryState()
        return WorkingMemoryState.model_validate(document)

    async def set_context(self, key: str, value: Any) -> WorkingMemoryState:
        now = utc_now()
        await self._collection.update_one(
            {"slot": "current"},
            {"$set": {f"context.{key}": value, "updated_at": now}},
            upsert=True,
        )
        return await self.read()

    async def clear(self) -> WorkingMemoryState:
        state = WorkingMemoryState(context={}, updated_at=utc_now())
        await self._collection.replace_one(
            {"slot": "current"},
            {"slot": "current", **state.model_dump(mode="python")},
            upsert=True,
        )
        return state
