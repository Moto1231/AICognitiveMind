import secrets
import subprocess
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from aicognitive_mind.config import get_settings
from aicognitive_mind.core import (
    CognitiveCore,
    FoundationNotInitializedError,
    MindNotInitializedError,
)
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    FoundationalMemory,
    InteractionResult,
    JournalEntry,
)
from aicognitive_mind.engines import (
    EchoReasoningEngine,
    OllamaReasoningEngine,
    OpenAIReasoningEngine,
    ReasoningEngine,
)
from aicognitive_mind.expression import ReasoningExpressionRenderer
from aicognitive_mind.foundation import (
    CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
    CONSCIOUS_EXPRESSION_FOUNDATION_SEED,
    CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
    CONSCIOUS_WORKSPACE_FOUNDATION_SEED,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
    MEMORY_STEWARD_SYNTHESIS_FOUNDATION_SEED,
)
from aicognitive_mind.knowledge import ReasoningKnowledgeSynthesizer
from aicognitive_mind.mongo_storage import (
    MongoDiagnosticStore,
    MongoFoundationStore,
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
    MongoRuntime,
)
from aicognitive_mind.storage import (
    DiagnosticStore,
    FoundationStore,
    JournalStore,
    MemoryStore,
    MindAlreadyInitializedError,
    MindStore,
)
from aicognitive_mind.surreal_storage import (
    SurrealDiagnosticStore,
    SurrealFoundationStore,
    SurrealJournalStore,
    SurrealMemoryStore,
    SurrealMindStore,
    SurrealRuntime,
)


class InitializeMindRequest(BaseModel):
    self_name: str = Field(min_length=1, max_length=120)
    foundational_values: tuple[str, ...] = ()


class InteractionRequest(BaseModel):
    message: str = Field(min_length=1)


class FoundationRevisionRequest(BaseModel):
    content: str = Field(min_length=1)


def get_core(request: Request) -> CognitiveCore:
    return cast(CognitiveCore, request.app.state.core)


def get_foundation(request: Request) -> FoundationStore:
    return cast(FoundationStore, request.app.state.foundation)


def get_runtime_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return completed.stdout.strip() or "unknown"


def authorize_admin(authorization: str | None) -> None:
    expected = get_settings().admin_token
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Administrative access is not configured",
        )
    scheme, separator, supplied = (authorization or "").partition(" ")
    valid = (
        separator == " "
        and scheme.lower() == "bearer"
        and bool(supplied)
        and secrets.compare_digest(supplied, expected)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrative authorization required",
            headers={"WWW-Authenticate": "Bearer"},
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    app.state.runtime_revision = get_runtime_revision()

    runtime: MongoRuntime | SurrealRuntime
    mind_store: MindStore
    foundation: FoundationStore
    journal_store: JournalStore
    memory_store: MemoryStore
    diagnostic_store: DiagnosticStore

    storage_provider = settings.storage_provider.lower()
    if storage_provider == "mongo":
        runtime = MongoRuntime(settings.mongodb_uri, settings.mongodb_database)
        await runtime.initialize()
        mind_store = MongoMindStore(runtime.database)
        foundation = MongoFoundationStore(runtime.database)
        journal_store = MongoJournalStore(runtime.database)
        memory_store = MongoMemoryStore(runtime.database)
        diagnostic_store = MongoDiagnosticStore(runtime.database)
    elif storage_provider == "surreal":
        runtime = SurrealRuntime(
            settings.surrealdb_uri,
            settings.surrealdb_namespace,
            settings.surrealdb_database,
            settings.surrealdb_username,
            settings.surrealdb_password,
        )
        await runtime.initialize()
        mind_store = SurrealMindStore(runtime.database)
        foundation = SurrealFoundationStore(runtime.database)
        journal_store = SurrealJournalStore(runtime.database)
        memory_store = SurrealMemoryStore(runtime.database)
        diagnostic_store = SurrealDiagnosticStore(runtime.database)
    else:
        raise RuntimeError("STORAGE_PROVIDER must be one of: mongo, surreal")

    app.state.runtime = runtime
    app.state.diagnostics = diagnostic_store
    app.state.foundation = foundation

    await foundation.seed(
        CONSCIOUS_WORKSPACE_FOUNDATION_KEY,
        CONSCIOUS_WORKSPACE_FOUNDATION_SEED,
    )
    await foundation.seed(
        MEMORY_STEWARD_SYNTHESIS_FOUNDATION_KEY,
        MEMORY_STEWARD_SYNTHESIS_FOUNDATION_SEED,
    )
    await foundation.seed(
        CONSCIOUS_EXPRESSION_FOUNDATION_KEY,
        CONSCIOUS_EXPRESSION_FOUNDATION_SEED,
    )

    provider = settings.reasoning_provider.lower()
    engine: ReasoningEngine
    if provider == "ollama":
        engine = OllamaReasoningEngine(settings.ollama_base_url, settings.ollama_model)
    elif provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY is required when REASONING_PROVIDER=openai")
        engine = OpenAIReasoningEngine(settings.openai_api_key, settings.openai_model)
    elif provider == "echo":
        engine = EchoReasoningEngine()
    else:
        raise RuntimeError("REASONING_PROVIDER must be one of: echo, openai, ollama")

    app.state.core = CognitiveCore(
        mind=mind_store,
        foundation=foundation,
        journal=journal_store,
        memory=memory_store,
        diagnostics=diagnostic_store,
        engine=engine,
        knowledge_synthesizer=ReasoningKnowledgeSynthesizer(engine),
        expression_renderer=ReasoningExpressionRenderer(engine),
    )
    yield
    await runtime.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.3.0", lifespan=lifespan)


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.runtime.ping()
    return {"status": "healthy"}


@app.get("/debug/revision")
async def read_runtime_revision(request: Request) -> dict[str, str]:
    return {"revision": cast(str, request.app.state.runtime_revision)}


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
    except FoundationNotInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="A required governed foundation is unavailable",
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


@app.get(
    "/v1/admin/foundation/{key}",
    response_model=list[FoundationalMemory],
)
async def read_foundation_history(
    key: str,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> list[FoundationalMemory]:
    authorize_admin(authorization)
    return await get_foundation(request).read_history(key)


@app.put(
    "/v1/admin/foundation/{key}",
    response_model=FoundationalMemory,
)
async def revise_foundation(
    key: str,
    body: FoundationRevisionRequest,
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> FoundationalMemory:
    authorize_admin(authorization)
    return await get_foundation(request).revise(
        key=key,
        content=body.content,
        changed_by="administrator",
    )


@app.get("/debug/diagnostics", response_model=list[DiagnosticObservation])
async def read_diagnostics(request: Request) -> list[DiagnosticObservation]:
    diagnostics = cast(DiagnosticStore, request.app.state.diagnostics)
    return await diagnostics.read()
