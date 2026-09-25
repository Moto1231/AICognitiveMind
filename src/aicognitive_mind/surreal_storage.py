# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

from __future__ import annotations

from typing import Any

from surrealdb import AsyncSurreal

from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    SensoryEvidenceArtifact,
)
from aicognitive_mind.permissions import CognitiveOperation, PermissionPolicy
from aicognitive_mind.storage import (
    MindAlreadyInitializedError,
    _journal_matches,
    _memory_matches,
)


class SurrealRuntime:
    """SurrealDB runtime supporting embedded and remote database URLs."""

    def __init__(
        self,
        uri: str,
        namespace: str,
        database_name: str,
        username: str | None = None,
        password: str | None = None,
        auth_level: str = "database",
        legacy_mind_id: str = "axiom",
    ) -> None:
        resolved_username = username.strip() if username and username.strip() else None
        resolved_password = password if password else None
        if (resolved_username is None) != (resolved_password is None):
            raise ValueError("SurrealDB username and password must be supplied together")
        self.database: Any = AsyncSurreal(uri)
        self._namespace = namespace
        self._database_name = database_name
        resolved_auth_level = auth_level.strip().lower()
        if resolved_auth_level not in {"root", "namespace", "database"}:
            raise ValueError(
                "SurrealDB auth level must be one of: root, namespace, database"
            )
        self._username = resolved_username
        self._password = resolved_password
        self._auth_level = resolved_auth_level
        self.legacy_mind_id = legacy_mind_id

    async def _migrate_legacy_scope(self) -> None:
        """Attach existing single-mind records to the configured first mind."""
        for table in (
            "mind",
            "journal",
            "memory",
            "diagnostics",
            "evidence",
            "runtime_records",
            "commit_receipts",
        ):
            await self.database.query(
                f"UPDATE {table} SET mind_id = $mind_id WHERE mind_id = NONE;",
                {"mind_id": self.legacy_mind_id},
            )

        from surrealdb import RecordID

        legacy_state_id = RecordID("commit_state", "root")
        scoped_state_id = RecordID("commit_state", self.legacy_mind_id)
        legacy_state = _records(await self.database.select(legacy_state_id))
        scoped_state = _records(await self.database.select(scoped_state_id))
        if (
            self.legacy_mind_id != "root"
            and legacy_state
            and not scoped_state
        ):
            value = _document(legacy_state[0])
            value["mind_id"] = self.legacy_mind_id
            await self.database.create(scoped_state_id, value)

    async def initialize(self) -> None:
        await self.database.connect()
        await self.database.use(self._namespace, self._database_name)
        if self._username is not None and self._password is not None:
            credentials: dict[str, str] = {
                "username": self._username,
                "password": self._password,
            }
            if self._auth_level in {"namespace", "database"}:
                credentials["namespace"] = self._namespace
            if self._auth_level == "database":
                credentials["database"] = self._database_name
            await self.database.signin(credentials)
        await self.ping()
        await self._migrate_legacy_scope()

    async def ping(self) -> None:
        await self.database.version()

    async def close(self) -> None:
        await self.database.close()


def _records(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    raise RuntimeError(f"Unexpected SurrealDB record result: {type(value).__name__}")


def _document(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if key not in {"id", "mind_id"}
    }


class SurrealMindStore:
    """Stores one root cognitive document for one mind_id."""

    def __init__(
        self,
        database: Any,
        mind_id: str = "axiom",
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._database = database
        self.mind_id = mind_id
        self._policy = policy or PermissionPolicy()

    async def initialize(self, mind: CognitiveMind) -> CognitiveMind:
        from aicognitive_mind.commit import commit
        try:
            await commit({"mind": self}, [("mind", "initialize", None, mind)], None, {})
        except Exception as exc:
            if await self.load() is not None:
                raise MindAlreadyInitializedError("This instance already contains its mind") from exc
            raise
        return mind

    async def load(self) -> CognitiveMind | None:
        records = _records(
            await self._database.query(
                "SELECT * FROM mind WHERE mind_id = $mind_id LIMIT 1;",
                {"mind_id": self.mind_id},
            )
        )
        if not records:
            return None
        return CognitiveMind.model_validate(_document(records[0]))

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
        changed = await self._database.query(
            "UPDATE mind CONTENT $replacement "
            "WHERE mind_id = $mind_id AND "
            + " AND ".join(
                f"{field} = $original.{field}"
                for field in type(original).model_fields
            )
            + " RETURN AFTER;",
            {
                "mind_id": self.mind_id,
                "original": original.model_dump(mode="json"),
                "replacement": {
                    "mind_id": self.mind_id,
                    **replacement.model_dump(mode="json"),
                },
            },
        )
        return replacement if changed else None


class SurrealJournalStore:
    """Append/read-only cognitive journal behind the provider-neutral contract."""

    def __init__(
        self,
        database: Any,
        mind_id: str = "axiom",
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._database = database
        self.mind_id = mind_id
        self._policy = policy or PermissionPolicy()

    async def append(
        self,
        entry: JournalEntry,
        recorded_by: CognitiveActor,
    ) -> JournalEntry:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        await self._database.create(
            "journal",
            {"mind_id": self.mind_id, **entry.model_dump(mode="json")},
        )
        return entry

    async def read(self) -> list[JournalEntry]:
        records = _records(
            await self._database.query(
                "SELECT * FROM journal WHERE mind_id = $mind_id;",
                {"mind_id": self.mind_id},
            )
        )
        entries = [JournalEntry.model_validate(_document(record)) for record in records]
        return sorted(entries, key=lambda entry: entry.occurred_at)

    async def query_page(
        self,
        *,
        offset: int,
        limit: int,
        newest_first: bool,
        kind: str | None = None,
        search: str | None = None,
        occurred_from: Any = None,
        occurred_to: Any = None,
    ) -> tuple[list[JournalEntry], int]:
        from aicognitive_mind.retrieval import surreal_page
        return await surreal_page(
            self._database,
            "journal",
            JournalEntry,
            offset=offset,
            limit=limit,
            newest_first=newest_first,
            search=search,
            mind_id=self.mind_id,
            kind=kind,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
        )


    async def find_exact(
        self,
        *,
        kind: str,
        occurred_at: Any,
    ) -> JournalEntry | None:
        for entry in await self.read():
            if entry.kind.value == kind and entry.occurred_at == occurred_at:
                return entry
        return None


class SurrealDiagnosticStore:
    """Implementation observations isolated per mind."""

    def __init__(self, database: Any, mind_id: str = "axiom") -> None:
        self._database = database
        self.mind_id = mind_id

    async def record(self, observation: DiagnosticObservation) -> None:
        await self._database.create(
            "diagnostics",
            {"mind_id": self.mind_id, **observation.model_dump(mode="json")},
        )

    async def read(self) -> list[DiagnosticObservation]:
        records = _records(
            await self._database.query(
                "SELECT * FROM diagnostics WHERE mind_id = $mind_id;",
                {"mind_id": self.mind_id},
            )
        )
        observations = [
            DiagnosticObservation.model_validate(_document(record)) for record in records
        ]
        return sorted(observations, key=lambda observation: observation.observed_at)


class SurrealMemoryStore:
    """Whole durable memories curated by the Memory Steward, isolated per mind."""

    def __init__(
        self,
        database: Any,
        mind_id: str = "axiom",
        policy: PermissionPolicy | None = None,
    ) -> None:
        self._database = database
        self.mind_id = mind_id
        self._policy = policy or PermissionPolicy()

    async def remember(
        self,
        memory: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        await self._database.create(
            "memory",
            {"mind_id": self.mind_id, **memory.model_dump(mode="json")},
        )
        return memory

    async def read(self) -> list[DurableMemory]:
        records = _records(
            await self._database.query(
                "SELECT * FROM memory WHERE mind_id = $mind_id;",
                {"mind_id": self.mind_id},
            )
        )
        memories = [DurableMemory.model_validate(_document(record)) for record in records]
        return sorted(memories, key=lambda memory: memory.formed_at)

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
        formed_from: Any = None,
        formed_to: Any = None,
    ) -> tuple[list[DurableMemory], int]:
        from aicognitive_mind.retrieval import surreal_page
        return await surreal_page(
            self._database,
            "memory",
            DurableMemory,
            offset=offset,
            limit=limit,
            newest_first=newest_first,
            search=search,
            mind_id=self.mind_id,
            memory_class=memory_class,
            association=association,
            grounding=grounding,
            formed_from=formed_from,
            formed_to=formed_to,
        )


    async def replace_exact(
        self,
        original: DurableMemory,
        replacement: DurableMemory,
        recorded_by: CognitiveActor,
    ) -> DurableMemory | None:
        self._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        changed = await self._database.query(
            "UPDATE memory CONTENT $replacement "
            "WHERE mind_id = $mind_id AND "
            + " AND ".join(
                f"{field} = $original.{field}"
                for field in type(original).model_fields
            )
            + " RETURN AFTER;",
            {
                "mind_id": self.mind_id,
                "original": original.model_dump(mode="json"),
                "replacement": {
                    "mind_id": self.mind_id,
                    **replacement.model_dump(mode="json"),
                },
            },
        )
        return replacement if changed else None



class SurrealEvidenceStore:
    """Provider-neutral sensory evidence store isolated per mind."""

    def __init__(self, database: Any, mind_id: str = "axiom") -> None:
        self._database = database
        self.mind_id = mind_id

    async def preserve(self, artifact: SensoryEvidenceArtifact) -> SensoryEvidenceArtifact:
        records = _records(
            await self._database.query(
                "SELECT * FROM evidence WHERE mind_id = $mind_id;",
                {"mind_id": self.mind_id},
            )
        )
        for record in records:
            existing = SensoryEvidenceArtifact.model_validate(_document(record))
            if (
                existing.sha256 == artifact.sha256
                and existing.captured_at == artifact.captured_at
            ):
                return existing
        await self._database.create(
            "evidence",
            {"mind_id": self.mind_id, **artifact.model_dump(mode="json")},
        )
        return artifact

    async def read(self) -> list[SensoryEvidenceArtifact]:
        records = _records(
            await self._database.query(
                "SELECT * FROM evidence WHERE mind_id = $mind_id;",
                {"mind_id": self.mind_id},
            )
        )
        artifacts = [
            SensoryEvidenceArtifact.model_validate(_document(record))
            for record in records
        ]
        return sorted(
            artifacts,
            key=lambda artifact: artifact.captured_at,
        )

    async def find_exact(
        self,
        *,
        sha256: str,
        captured_at: Any,
    ) -> SensoryEvidenceArtifact | None:
        from aicognitive_mind.retrieval import json_time
        records = await self._database.query(
            "SELECT * FROM evidence WHERE mind_id = $mind_id "
            "AND sha256 = $sha AND captured_at = $captured LIMIT 1;",
            {
                "mind_id": self.mind_id,
                "sha": sha256,
                "captured": json_time(captured_at),
            },
        )
        return SensoryEvidenceArtifact.model_validate(_document(records[0])) if records else None
