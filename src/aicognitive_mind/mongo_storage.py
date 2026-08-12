from typing import Any
from uuid import UUID

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

from aicognitive_mind.domain import Being, CognitiveEvent
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy


class MongoRuntime:
    def __init__(self, uri: str, database_name: str) -> None:
        self.client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
            uri,
            uuidRepresentation="standard",
        )
        self.database: AsyncDatabase[dict[str, Any]] = self.client[database_name]

    async def initialize(self) -> None:
        await self.client.admin.command("ping")
        await self.database.beings.create_index("being_id", unique=True)
        await self.database.cognitive_events.create_index("event_id", unique=True)
        await self.database.cognitive_events.create_index(
            [("being_id", ASCENDING), ("occurred_at", ASCENDING)]
        )

    async def ping(self) -> None:
        await self.client.admin.command("ping")

    async def close(self) -> None:
        await self.client.close()


class MongoBeingStore:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.beings

    async def create(self, being: Being) -> Being:
        await self._collection.insert_one(being.model_dump(mode="python"))
        return being

    async def get(self, being_id: UUID) -> Being | None:
        document = await self._collection.find_one({"being_id": being_id}, {"_id": 0})
        return Being.model_validate(document) if document else None


class MongoEventStore:
    """Append/read-only repository: no update or delete operation is exposed."""

    def __init__(
        self,
        database: AsyncDatabase[dict[str, Any]],
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._collection = database.cognitive_events
        self._policy = policy or PermissionPolicy()

    async def append(self, event: CognitiveEvent) -> CognitiveEvent:
        self._policy.assert_allowed(event.recorded_by, CognitiveOperation.APPEND_EVENT)
        await self._collection.insert_one(event.model_dump(mode="python"))
        return event

    async def list_for_being(self, being_id: UUID) -> list[CognitiveEvent]:
        cursor = self._collection.find({"being_id": being_id}, {"_id": 0}).sort(
            "occurred_at", ASCENDING
        )
        return [CognitiveEvent.model_validate(document) async for document in cursor]
