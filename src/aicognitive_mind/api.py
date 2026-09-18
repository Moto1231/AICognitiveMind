from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aicognitive_mind.config import get_settings
from aicognitive_mind.core import CognitiveCore, MindNotInitializedError
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    InteractionResult,
    JournalEntry,
)
from aicognitive_mind.engines import EchoReasoningEngine, OpenAIReasoningEngine
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.mongo_storage import (
    MongoDiagnosticStore,
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
    MongoRuntime,
)
from aicognitive_mind.storage import MindAlreadyInitializedError


STATIC_DIR = Path(__file__).with_name("static")


class InitializeMindRequest(BaseModel):
    self_name: str = Field(min_length=1, max_length=120)
    foundational_values: tuple[str, ...] = ()


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
    app.state.diagnostics = MongoDiagnosticStore(runtime.database)
    mind_store = MongoMindStore(runtime.database)
    journal_store = MongoJournalStore(runtime.database)
    memory_store = MongoMemoryStore(runtime.database)
    app.state.mcp_service = CognitiveMcpService(
        mind=mind_store,
        journal=journal_store,
        memory=memory_store,
    )
    engine = (
        OpenAIReasoningEngine(settings.openai_api_key, settings.openai_model)
        if settings.openai_api_key
        else EchoReasoningEngine()
    )
    app.state.core = CognitiveCore(
        mind=mind_store,
        journal=journal_store,
        memory=memory_store,
        diagnostics=app.state.diagnostics,
        engine=engine,
    )
    yield
    await runtime.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def portal() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.runtime.ping()
    return {"status": "healthy"}


@app.get("/v1/portal/status")
async def portal_status(request: Request) -> dict[str, Any]:
    service = cast(CognitiveMcpService, request.app.state.mcp_service)
    try:
        return await service.status()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.post(
    "/v1/mind/initialize",
    response_model=CognitiveMind,
    status_code=status.HTTP_201_CREATED,
)
async def initialize_mind(body: InitializeMindRequest, request: Request) -> CognitiveMind:
    try:
        return await get_core(request).initialize(body.self_name, body.foundational_values)
    except MindAlreadyInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This instance already contains its mind",
        ) from exc


@app.get("/v1/mind", response_model=CognitiveMind)
async def load_mind(request: Request) -> CognitiveMind:
    try:
        return await get_core(request).load_mind()
    except MindNotInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The mind has not been initialized",
        ) from exc


@app.post("/v1/mind/interactions", response_model=InteractionResult)
async def interact(body: InteractionRequest, request: Request) -> InteractionResult:
    try:
        return await get_core(request).interact(body.message)
    except MindNotInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The mind has not been initialized",
        ) from exc


@app.get("/v1/mind/journal", response_model=list[JournalEntry])
async def read_journal(request: Request) -> list[JournalEntry]:
    try:
        return await get_core(request).read_journal()
    except MindNotInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The mind has not been initialized",
        ) from exc


@app.get("/v1/mind/memory", response_model=list[DurableMemory])
async def read_memory(request: Request) -> list[DurableMemory]:
    try:
        return await get_core(request).read_memory()
    except MindNotInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The mind has not been initialized",
        ) from exc


@app.get("/debug/diagnostics", response_model=list[DiagnosticObservation])
async def read_diagnostics(request: Request) -> list[DiagnosticObservation]:
    diagnostics = cast(MongoDiagnosticStore, request.app.state.diagnostics)
    return await diagnostics.read()
