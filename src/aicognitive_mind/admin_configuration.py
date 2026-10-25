"""Administrator-authorized identity and cognitive settings HTTP routes."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from aicognitive_mind.cognitive_configuration import CognitiveConfigurationRegistry
from aicognitive_mind.commit import CommitConflict, atomic
from aicognitive_mind.domain import CognitiveActor, CognitiveMind, JournalEntry, JournalKind, MindIdentity


class IdentityNotInitializedError(LookupError):
    pass


class IdentityFields(MindIdentity):
    model_config = ConfigDict(extra="forbid")


class IdentityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    identity: IdentityFields = Field(default_factory=IdentityFields)
    developmental_state: str = Field(default="genesis", min_length=1, max_length=120)


class CognitiveConfigurationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=0, strict=True)
    base_contract: str = Field(default="", max_length=200_000)
    startup_instructions: str = Field(default="", max_length=200_000)
    task_foundations: dict[str, str] = Field(default_factory=dict)


def identity_snapshot(mind: CognitiveMind) -> dict[str, Any]:
    encoded = json.dumps(mind.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return {
        "revision": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "identity": mind.identity.model_dump(mode="json"),
        "developmental_state": mind.developmental_state,
        "created_at": mind.created_at.isoformat(),
    }


class AdministratorIdentityService:
    def __init__(self, mind: Any, journal: Any) -> None:
        self._mind = mind
        self._journal = journal

    async def read(self) -> dict[str, Any]:
        mind = await self._mind.load()
        if mind is None:
            raise IdentityNotInitializedError("The Mind has not been initialized")
        return identity_snapshot(mind)

    @atomic
    async def save(self, payload: IdentityUpdate) -> dict[str, Any]:
        original = await self._mind.load()
        if original is None:
            raise IdentityNotInitializedError("The Mind has not been initialized")
        if identity_snapshot(original)["revision"] != payload.expected_revision:
            raise CommitConflict("Mind identity changed; refresh before saving")
        changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if "identity" in changes:
            changes["identity"] = original.identity.model_dump() | payload.identity.model_dump(exclude_unset=True)
        replacement = CognitiveMind.model_validate(original.model_dump() | changes)
        if replacement == original:
            return identity_snapshot(original)
        revised = await self._mind.replace_exact(
            original, replacement, recorded_by=CognitiveActor.ADMINISTRATOR,
        )
        if revised is None:
            raise CommitConflict("Mind identity changed; refresh before saving")
        await self._journal.append(JournalEntry(
            kind=JournalKind.IDENTITY_REVISION,
            experience={
                "authority": "administrator", "operation": "update_identity",
                "before": original.model_dump(mode="json"),
                "after": revised.model_dump(mode="json"),
                "changed_fields": list(changes),
            },
        ), recorded_by=CognitiveActor.ADMINISTRATOR)
        return identity_snapshot(revised)


def create_admin_configuration_router(
    require_admin: Callable[[Request], None], request_runtime: Callable[[Request], Any],
) -> APIRouter:
    router = APIRouter()

    def identity_service(request: Request) -> AdministratorIdentityService:
        runtime = request_runtime(request)
        return AdministratorIdentityService(runtime.mind_store, runtime.journal_store)

    def handle_error(error: Exception) -> HTTPException:
        if isinstance(error, IdentityNotInitializedError):
            return HTTPException(status_code=404, detail=str(error))
        if isinstance(error, CommitConflict):
            return HTTPException(status_code=409, detail=str(error))
        return HTTPException(status_code=422, detail=str(error))

    @router.get("/v1/admin/identity")
    async def get_identity(request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            return await identity_service(request).read()
        except IdentityNotInitializedError as exc:
            raise handle_error(exc) from exc

    @router.put("/v1/admin/identity")
    async def save_identity(payload: IdentityUpdate, request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            return await identity_service(request).save(payload)
        except (IdentityNotInitializedError, CommitConflict, ValueError, ValidationError) as exc:
            raise handle_error(exc) from exc

    @router.get("/v1/admin/cognitive-configuration")
    async def get_configuration(request: Request) -> dict[str, Any]:
        require_admin(request)
        return await CognitiveConfigurationRegistry(request_runtime(request).runtime_records).effective()

    @router.put("/v1/admin/cognitive-configuration")
    async def save_configuration(payload: CognitiveConfigurationUpdate, request: Request) -> dict[str, Any]:
        require_admin(request)
        try:
            changes = payload.model_dump(exclude_unset=True, exclude={"expected_revision"})
            return await CognitiveConfigurationRegistry(request_runtime(request).runtime_records).save(
                changes, expected_revision=payload.expected_revision,
            )
        except (CommitConflict, ValueError) as exc:
            raise handle_error(exc) from exc

    return router
