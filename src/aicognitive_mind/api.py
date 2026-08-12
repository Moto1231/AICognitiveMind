from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel, Field

from aicognitive_mind.config import get_settings
from aicognitive_mind.core import BeingNotFoundError, CognitiveCore
from aicognitive_mind.domain import Being, CognitiveEvent, InteractionResult
from aicognitive_mind.engines import EchoReasoningEngine
from aicognitive_mind.mongo_storage import MongoBeingStore, MongoEventStore, MongoRuntime


class CreateBeingRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    host_id: str = Field(min_length=1, max_length=200)
    values: tuple[str, ...] = ()


class InteractionRequest(BaseModel):
    message: str = Field(min_length=1)


def get_core(request: Request) -> CognitiveCore:
    return cast(CognitiveCore, request.app.state.core)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    runtime = MongoRuntime(settings.mongodb_uri, settings.mongodb_database)
    await runtime.initialize()
    app.state.runtime = runtime
    app.state.core = CognitiveCore(
        beings=MongoBeingStore(runtime.database),
        events=MongoEventStore(runtime.database),
        engine=EchoReasoningEngine(),
    )
    yield
    await runtime.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.runtime.ping()
    return {"status": "healthy"}


@app.post("/v1/beings", response_model=Being, status_code=status.HTTP_201_CREATED)
async def create_being(body: CreateBeingRequest, request: Request) -> Being:
    return await get_core(request).create_being(body.name, body.host_id, body.values)


@app.post("/v1/beings/{being_id}/interactions", response_model=InteractionResult)
async def interact(being_id: UUID, body: InteractionRequest, request: Request) -> InteractionResult:
    try:
        return await get_core(request).interact(being_id, body.message)
    except BeingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Being not found",
        ) from exc


@app.get("/v1/beings/{being_id}/events", response_model=list[CognitiveEvent])
async def history(being_id: UUID, request: Request) -> list[CognitiveEvent]:
    try:
        return await get_core(request).history(being_id)
    except BeingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Being not found",
        ) from exc
