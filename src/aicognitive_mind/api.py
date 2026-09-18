from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aicognitive_mind.config import Settings, get_settings
from aicognitive_mind.core import CognitiveCore, MindNotInitializedError
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    InteractionResult,
    JournalEntry,
)
from aicognitive_mind.engines import EchoReasoningEngine, OpenAIReasoningEngine, ReasoningEngine
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


class EngineSelectionRequest(BaseModel):
    provider: Literal["openai", "echo"]
    model: str | None = None


class RuntimeStatus(BaseModel):
    provider: str
    model: str
    available_models: tuple[str, ...] = ()
    openai_available: bool = False
    admin_pin_required: bool = False


def get_core(request: Request) -> CognitiveCore:
    return cast(CognitiveCore, request.app.state.core)


def initial_engine(settings: Settings) -> tuple[ReasoningEngine, str, str]:
    if settings.openai_api_key:
        return (
            OpenAIReasoningEngine(settings.openai_api_key, settings.openai_model),
            "openai",
            settings.openai_model,
        )
    return EchoReasoningEngine(), "echo", "deterministic-echo"


def get_runtime_status(request: Request) -> RuntimeStatus:
    settings = get_settings()
    return RuntimeStatus(
        provider=cast(str, request.app.state.engine_provider),
        model=cast(str, request.app.state.engine_model),
        available_models=settings.openai_model_options,
        openai_available=bool(settings.openai_api_key),
        admin_pin_required=bool(settings.admin_pin),
    )


def require_admin(request: Request) -> None:
    configured_pin = get_settings().admin_pin
    if configured_pin and request.headers.get("x-admin-pin") != configured_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin PIN was not accepted",
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    runtime = MongoRuntime(settings.mongodb_uri, settings.mongodb_database)
    await runtime.initialize()
    app.state.runtime = runtime
    app.state.diagnostics = MongoDiagnosticStore(runtime.database)

    engine, provider, model = initial_engine(settings)
    app.state.engine_provider = provider
    app.state.engine_model = model
    app.state.core = CognitiveCore(
        mind=MongoMindStore(runtime.database),
        journal=MongoJournalStore(runtime.database),
        memory=MongoMemoryStore(runtime.database),
        diagnostics=app.state.diagnostics,
        engine=engine,
    )
    yield
    await runtime.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.4.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def demo_console() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.runtime.ping()
    return {"status": "healthy"}


@app.get("/v1/runtime", response_model=RuntimeStatus)
async def runtime_status(request: Request) -> RuntimeStatus:
    return get_runtime_status(request)


@app.get("/v1/admin/status", response_model=RuntimeStatus)
async def admin_status(request: Request) -> RuntimeStatus:
    require_admin(request)
    return get_runtime_status(request)


@app.post("/v1/admin/engine", response_model=RuntimeStatus)
async def switch_engine(body: EngineSelectionRequest, request: Request) -> RuntimeStatus:
    require_admin(request)
    settings = get_settings()

    if body.provider == "openai":
        if not settings.openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="OpenAI is not configured for this runtime",
            )
        model = (body.model or settings.openai_model).strip()
        if model not in settings.openai_model_options:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model is not in the configured OPENAI_MODELS list",
            )
        engine: ReasoningEngine = OpenAIReasoningEngine(settings.openai_api_key, model)
    else:
        model = "deterministic-echo"
        engine = EchoReasoningEngine(diagnostic_name="echo-demo", prefix="I heard")

    get_core(request).replace_engine(engine)
    request.app.state.engine_provider = body.provider
    request.app.state.engine_model = model
    return get_runtime_status(request)


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
