# Copyright (c) 2026 William Enright. All rights reserved.
# Use, reproduction, modification, distribution, or commercial exploitation
# of this file is prohibited without prior written permission from the
# copyright holder.

import base64
import binascii
import hmac
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Any, cast

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from aicognitive_mind.accounts import AccountService
from aicognitive_mind.backup import (
    backup_filename,
    build_backup_archive,
    evidence_references_from_journal,
)
from aicognitive_mind.body import (
    BodyRuntime,
    BrowserAudioIngress,
    BrowserAvatarOutput,
    BrowserVisionIngress,
    BrowserVoiceOutput,
    DeviceStatus,
    ExpressionIntent,
    ExpressionModality,
    Percept,
)
from aicognitive_mind.body.genesis_avatar import build_genesis_vrm
from aicognitive_mind.body_sessions import BodyQueue, body_session
from aicognitive_mind.config import get_settings
from aicognitive_mind.core import CognitiveCore, MindNotInitializedError
from aicognitive_mind.domain import (
    CognitiveActor,
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    InteractionResult,
    JournalEntry,
    JournalKind,
    MemoryClass,
    SensoryEvidenceReference,
)
from aicognitive_mind.embodiment import (
    EmbodiedInteractionResult,
    MindBodyBridge,
)
from aicognitive_mind.evidence_review import SensoryEvidenceReviewTool
from aicognitive_mind.host_runtime import (
    HostAwareCore,
    HostAwareInterpreter,
    HostRuntime,
    RuntimeRecords,
)
from aicognitive_mind.mcp_service import CognitiveMcpService
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.standalone import ProviderUnavailable, StandaloneRuntime
from aicognitive_mind.storage import (
    DiagnosticStore,
    EvidenceStore,
    JournalStore,
    MemoryStore,
    MindAlreadyInitializedError,
    MindStore,
)

STATIC_DIR = Path(__file__).with_name("static")


class InitializeMindRequest(BaseModel):
    self_name: str = Field(min_length=1, max_length=120)
    foundational_values: tuple[str, ...] = ()


class InteractionRequest(BaseModel):
    message: str = Field(min_length=1)


class AdminMemoryRevisionRequest(BaseModel):
    original: DurableMemory
    replacement: DurableMemory


class DesktopAdminMemoryRevisionRequest(BaseModel):
    original_memory_class: MemoryClass
    original_formed_at: datetime
    original_content: str = Field(min_length=1)
    original_associations: tuple[str, ...] = ()
    original_grounding: tuple[str, ...] = ()
    replacement_memory_class: MemoryClass
    replacement_content: str = Field(min_length=1)
    replacement_associations: tuple[str, ...] = ()
    replacement_grounding: tuple[str, ...] = ()


class JournalDetailRequest(BaseModel):
    kind: JournalKind
    occurred_at: datetime


class BrowserVisionObservationRequest(BaseModel):
    image_data_url: str = Field(min_length=32, max_length=8_000_000)
    width: int = Field(gt=0, le=10_000)
    height: int = Field(gt=0, le=10_000)
    source: str = Field(default="browser-camera", min_length=1, max_length=120)


class BrowserAudioObservationRequest(BaseModel):
    audio_data_url: str = Field(min_length=32, max_length=12_000_000)
    duration_ms: int = Field(gt=0, le=30_000)
    source: str = Field(default="browser-microphone", min_length=1, max_length=120)


class FaceExpressionRequest(BaseModel):
    expression: str = Field(default="neutral", min_length=1, max_length=80)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    text: str | None = Field(default=None, max_length=500)


class MouthSpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    rate: float = Field(default=1.0, ge=0.1, le=10.0)
    pitch: float = Field(default=1.0, ge=0.0, le=2.0)
    volume: float = Field(default=1.0, ge=0.0, le=1.0)
    voice_name: str | None = Field(default=None, max_length=200)


def _journal_summary(entry: JournalEntry) -> dict[str, Any]:
    experience = entry.experience
    summary: dict[str, Any] = {
        "kind": entry.kind,
        "occurred_at": entry.occurred_at,
        "title": entry.kind.value.replace("_", " ").title(),
        "search_text": "",
        "preview": "",
    }

    if entry.kind == JournalKind.INTERACTION:
        input_text = str(experience.get("input", {}).get("content", ""))
        response_text = str(experience.get("expression", {}).get("content", ""))
        summary["title"] = "Interaction"
        summary["preview"] = input_text or response_text
        summary["search_text"] = f"{input_text} {response_text}".strip()
    elif entry.kind == JournalKind.IDENTITY_REVISION:
        before = experience.get("before", {})
        after = experience.get("after", {})
        before_name = str(before.get("self_name", ""))
        after_name = str(after.get("self_name", ""))
        rationale = str(experience.get("rationale", ""))
        summary["title"] = "Identity Revision"
        summary["preview"] = f"{before_name} → {after_name}".strip(" →")
        summary["search_text"] = f"{before_name} {after_name} {rationale}".strip()
    elif entry.kind == JournalKind.MEMORY_REVISION:
        before = experience.get("before", {})
        after = experience.get("after", {})
        before_content = str(before.get("content", ""))
        after_content = str(after.get("content", ""))
        summary["title"] = "Memory Revision"
        summary["preview"] = after_content or before_content
        summary["search_text"] = f"{before_content} {after_content}".strip()
    elif entry.kind == JournalKind.BELIEF_REFRAME:
        subject = str(experience.get("subject", ""))
        attribute = str(experience.get("attribute", ""))
        existing_value = str(experience.get("existing_value", ""))
        proposed_value = str(experience.get("proposed_value", ""))
        existing_scope = str(experience.get("existing_scope", ""))
        proposed_scope = str(experience.get("proposed_scope", ""))
        relationship = str(experience.get("relationship", ""))
        summary["title"] = "Belief Reframe"
        summary["preview"] = (
            f"{subject} · {attribute}: {existing_value} [{existing_scope}] ; "
            f"{proposed_value} [{proposed_scope}]"
        ).strip()
        summary["search_text"] = " ".join(
            str(value)
            for value in (
                subject,
                attribute,
                relationship,
                existing_value,
                existing_scope,
                proposed_value,
                proposed_scope,
                experience.get("status", ""),
                experience.get("deliberation_revision", ""),
                experience.get("basis", []),
                experience.get("existing_evidence", []),
                experience.get("proposed_evidence", []),
            )
            if value
        )
    elif entry.kind == JournalKind.BELIEF_TRANSITION:
        subject = str(experience.get("subject", ""))
        attribute = str(experience.get("attribute", ""))
        from_value = str(experience.get("from_value", ""))
        to_value = str(experience.get("to_value", ""))
        scope = experience.get("scope") or {}
        scope_label = str(scope.get("label", "")) if isinstance(scope, dict) else ""
        scope_suffix = f" [{scope_label}]" if scope_label else ""
        summary["title"] = "Belief Transition"
        summary["preview"] = (
            f"{subject} · {attribute}: {from_value} → {to_value}{scope_suffix}".strip()
        )
        summary["search_text"] = " ".join(
            str(value)
            for value in (
                subject,
                attribute,
                from_value,
                to_value,
                scope_label,
                experience.get("status", ""),
                experience.get("deliberation_revision", ""),
                experience.get("readiness_basis", []),
                experience.get("candidate_evidence", []),
                experience.get("superseded_evidence", []),
            )
            if value
        )
    elif entry.kind == JournalKind.TENSION:
        subject = str(experience.get("subject", ""))
        attribute = str(experience.get("attribute", ""))
        values = experience.get("competing_values", {})
        existing_value = str(values.get("existing", ""))
        proposed_value = str(values.get("proposed", ""))
        phase = str(experience.get("phase", "detected"))
        scope = experience.get("scope") or {}
        scope_label = str(scope.get("label", "")) if isinstance(scope, dict) else ""
        scope_suffix = f" [{scope_label}]" if scope_label else ""
        summary["title"] = (
            "Tension Reassessment" if phase == "reassessment" else "Semantic Tension"
        )
        summary["preview"] = (
            f"{subject} · {attribute}: {existing_value} ↔ {proposed_value}{scope_suffix}".strip()
        )
        evidence = experience.get("evidence", {})
        deliberation = experience.get("deliberation") or {}
        current_evidence = experience.get("current_evidence", [])
        readiness = deliberation.get("resolution_readiness") or {}
        guidance = " ".join(
            str(value)
            for value in (
                *deliberation.get("appraisal_gaps", []),
                *deliberation.get("context_observations", []),
                *deliberation.get("investigation_questions", []),
            )
        )
        summary["search_text"] = " ".join(
            value
            for value in (
                subject,
                attribute,
                existing_value,
                proposed_value,
                scope_label,
                str(evidence.get("existing", "")),
                str(evidence.get("proposed", "")),
                str(deliberation.get("provenance_relationship", "")),
                str(deliberation.get("trigger", "")),
                str(readiness.get("status", "")),
                str(readiness.get("candidate_side", "")),
                str(readiness.get("candidate_value", "")),
                str(readiness.get("blockers", "")),
                str(readiness.get("basis", "")),
                str(deliberation.get("tension_finding", "")),
                str(deliberation.get("current_evidence_history", "")),
                guidance,
                str(current_evidence),
            )
            if value
        )
    elif entry.kind == JournalKind.EVIDENCE_REVIEW:
        evidence = experience.get("evidence", {})
        focus = str(experience.get("focus", ""))
        interpretation = str(experience.get("interpretation", ""))
        sha256 = str(evidence.get("sha256", ""))
        summary["title"] = "Evidence Review"
        summary["preview"] = (
            f"{focus} · {sha256[:12]}".strip(" ·")
        )
        summary["search_text"] = " ".join(
            value for value in (focus, interpretation, sha256) if value
        )
    elif entry.kind == JournalKind.SENSORY_EVIDENCE:
        evidence = experience.get("evidence", {})
        modality = str(evidence.get("modality", "sensory"))
        source = str(evidence.get("source", ""))
        sha256 = str(evidence.get("sha256", ""))
        media_type = str(evidence.get("media_type", ""))
        summary["title"] = "Sensory Evidence"
        summary["preview"] = (
            f"{modality} · {source} · {sha256[:12]}".strip(" ·")
        )
        summary["search_text"] = " ".join(
            value for value in (modality, source, sha256, media_type) if value
        )
    elif entry.kind == JournalKind.INITIALIZATION:
        self_name = str(experience.get("self_name", ""))
        values = " ".join(str(value) for value in experience.get("foundational_values", []))
        summary["title"] = "Initialization"
        summary["preview"] = self_name
        summary["search_text"] = f"{self_name} {values}".strip()
    else:
        keys = ", ".join(str(key) for key in experience)
        summary["preview"] = keys
        summary["search_text"] = keys

    return summary


def app_access_authorized(authorization: str | None) -> bool:
    settings = get_settings()
    expected_password = settings.app_access_password
    if not expected_password:
        return True
    if not authorization or not authorization.startswith("Basic "):
        return False

    try:
        decoded = base64.b64decode(
            authorization.removeprefix("Basic ").strip(),
            validate=True,
        ).decode("utf-8")
        username, password = decoded.split(":", 1)
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return False

    return hmac.compare_digest(username, settings.app_access_username) and hmac.compare_digest(
        password,
        expected_password,
    )


def require_admin(request: Request) -> None:
    configured_pin = get_settings().admin_pin
    if configured_pin and request.headers.get("x-admin-pin") != configured_pin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Administrator authorization was not accepted",
        )


def get_core(request: Request) -> CognitiveCore:
    return cast(CognitiveCore, request.app.state.core)


def _effective_standalone_reasoning_provider(settings: Any) -> str:
    explicit = getattr(settings, "standalone_reasoning_provider", None)
    legacy = getattr(settings, "reasoning_provider", "echo")
    return str(explicit or legacy or "echo").strip().lower()


def _reasoning_backend_error_detail(exc: Exception) -> str:
    if isinstance(exc, ProviderUnavailable):
        return str(exc)
    settings = get_settings()
    provider = _effective_standalone_reasoning_provider(settings)
    provider_label = (
        "Gemini"
        if provider == "gemini"
        else "OpenAI"
        if provider == "openai"
        else provider.title()
    )
    status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    class_name = exc.__class__.__name__

    if status_code in {401, 403} or class_name == "AuthenticationError":
        return (
            f"{provider_label} authentication or project permission failed. "
            f"Verify the configured API key for the {provider_label} project."
        )
    if status_code == 429 or class_name == "RateLimitError":
        return (
            f"{provider_label} rejected the request for quota or rate-limit reasons. "
            "Check the project's free-tier usage and limits."
        )
    if status_code == 404 or class_name == "NotFoundError":
        return (
            f"{provider_label} could not access the configured model or API resource. "
            "Check the model name and project permissions."
        )
    if status_code == 400 or class_name in {"BadRequestError", "ClientError"}:
        return (
            f"{provider_label} rejected the reasoning request as invalid. "
            "Check the Render logs for the request error."
        )
    if class_name in {"APIConnectionError", "ServerError"}:
        return f"The Mind could not connect to the {provider_label} API."
    if class_name == "ValidationError":
        return (
            "The reasoning model produced a cognitive tool call that did not match "
            "the tool's governed schema."
        )
    if isinstance(exc, RuntimeError) and "maximum number of tool rounds" in str(exc):
        return (
            "The reasoning process exhausted its cognitive tool rounds before "
            "reaching a final response."
        )

    return (
        "The reasoning backend failed unexpectedly. "
        "Check the Render logs for the exception."
    )


def _validate_reasoning_configuration(settings: Any) -> str:
    provider = _effective_standalone_reasoning_provider(settings)
    if provider not in {"gemini", "openai", "echo", "disabled"}:
        raise RuntimeError(
            "STANDALONE_REASONING_PROVIDER must be one of: gemini, openai, echo "
            "(legacy REASONING_PROVIDER is still accepted)"
        )

    if os.getenv("RENDER", "").lower() == "true":
        if provider == "gemini" and not settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured for Render. "
                "Set it in the Render service Environment."
            )
        if provider == "openai" and not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured for Render. "
                "Set it in the Render service Environment."
            )
        if provider == "echo":
            raise RuntimeError(
                "REASONING_PROVIDER=echo is not allowed on Render. "
                "This is the standalone fallback provider; configure "
                "STANDALONE_REASONING_PROVIDER=gemini or openai "
                "(legacy REASONING_PROVIDER is still accepted)."
            )
    return provider


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    provider = settings.effective_standalone_reasoning_provider
    app.state.standalone_reasoning_provider = provider
    storage = await create_storage(settings)
    app.state.runtime = storage.runtime
    app.state.diagnostics = storage.diagnostics
    app.state.evidence_store = storage.evidence
    app.state.mind_store = storage.mind
    app.state.journal_store = storage.journal
    app.state.memory_store = storage.memory
    app.state.mcp_service = CognitiveMcpService(
        mind=storage.mind,
        journal=storage.journal,
        memory=storage.memory,
    )
    records = RuntimeRecords(storage.mind)
    app.state.accounts = AccountService(settings, records)
    from aicognitive_mind.voice_settings import VoiceSettings

    app.state.voice_settings = VoiceSettings(storage.mind)
    browser_eyes = BodyQueue(records, "eyes", BrowserVisionIngress())
    browser_ears = BodyQueue(records, "ears", BrowserAudioIngress())
    browser_face = BodyQueue(records, "face", BrowserAvatarOutput())
    browser_mouth = BodyQueue(records, "mouth", BrowserVoiceOutput())
    app.state.browser_eyes = browser_eyes
    app.state.browser_ears = browser_ears
    app.state.browser_face = browser_face
    app.state.browser_mouth = browser_mouth
    app.state.body = BodyRuntime(
        vision=browser_eyes,
        audio=browser_ears,
        voice=browser_mouth,
        avatar=browser_face,
    )
    fallback = StandaloneRuntime(settings, records)
    app.state.standalone = fallback
    hosts = HostRuntime(storage.mind, app.state.mcp_service, settings.reasoning_timeout_seconds)
    app.state.hosts = hosts
    engine = fallback
    interpreter = HostAwareInterpreter(fallback, hosts)
    evidence_review = SensoryEvidenceReviewTool(
        evidence=storage.evidence,
        journal=storage.journal,
        interpreter=interpreter,
    )
    core = CognitiveCore(
        mind=storage.mind,
        journal=storage.journal,
        memory=storage.memory,
        diagnostics=storage.diagnostics,
        engine=engine,
        reasoning_tools=(evidence_review,),
    )
    core = HostAwareCore(core, hosts)
    app.state.core = core
    app.state.evidence_review = evidence_review
    app.state.mind_body = MindBodyBridge(
        core=core,
        body=app.state.body,
        interpreter=interpreter,
        evidence=storage.evidence,
        journal=storage.journal,
    )
    try:
        yield
    finally:
        await storage.runtime.close()


settings = get_settings()
app = FastAPI(title=settings.app_name, version="0.5.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def select_body_session(request: Request, call_next: Any) -> Response:
    import re
    session = request.headers.get("x-body-session", "legacy")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", session):
        return Response("Invalid Body session", status_code=400)
    token = body_session.set(session)
    try:
        return await call_next(request)
    finally:
        body_session.reset(token)


@app.middleware("http")
async def protect_remote_runtime(request: Request, call_next: Any) -> Response:
    authorization = request.headers.get("authorization")
    if request.url.path == "/health" or app_access_authorized(authorization):
        return await call_next(request)

    if authorization and authorization.startswith("Basic ") and hasattr(request.app.state, "accounts"):
        try:
            decoded = base64.b64decode(authorization.removeprefix("Basic ").strip(), validate=True).decode("utf-8")
            username, password = decoded.split(":", 1)
            account = await request.app.state.accounts.authenticate(username, password)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            account = None
        portal_path = request.url.path == "/" or request.url.path.startswith("/static/") or request.url.path.startswith("/v1/portal/")
        if account is not None and portal_path:
            tenant = await create_storage(get_settings(), mind_id=account.mind_id)
            request.state.tenant_storage = tenant
            try:
                return await call_next(request)
            finally:
                await tenant.runtime.close()

    return Response(
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": 'Basic realm="Axiom"'},
    )


@app.get("/", include_in_schema=False)
async def portal() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/body/live", include_in_schema=False)
async def live_body_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "live_body.html")


@app.get("/v1/body/voice/settings")
async def body_voice_settings(request: Request) -> dict[str, Any]:
    """Read voice preferences shared with Axiom's ChatGPT MCP host."""
    return await request.app.state.voice_settings.read()


@app.get("/body/avatar", include_in_schema=False)
async def avatar_editor_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "avatar_editor.html")


@app.post("/v1/mind/body/see", response_model=EmbodiedInteractionResult)
async def mind_see(
    request: Request,
    express: bool = True,
) -> EmbodiedInteractionResult:
    bridge = cast(MindBodyBridge, request.app.state.mind_body)
    try:
        return await bridge.see(express=express)
    except (MindNotInitializedError, RuntimeError, ValueError) as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, MindNotInitializedError)
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_reasoning_backend_error_detail(exc),
        ) from exc


@app.post("/v1/mind/body/hear", response_model=EmbodiedInteractionResult)
async def mind_hear(
    request: Request,
    express: bool = True,
) -> EmbodiedInteractionResult:
    bridge = cast(MindBodyBridge, request.app.state.mind_body)
    try:
        return await bridge.hear(express=express)
    except (MindNotInitializedError, RuntimeError, ValueError) as exc:
        code = (
            status.HTTP_404_NOT_FOUND
            if isinstance(exc, MindNotInitializedError)
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_reasoning_backend_error_detail(exc),
        ) from exc


@app.get(
    "/v1/evidence/{sha256}/metadata",
    response_model=SensoryEvidenceReference,
)
async def sensory_evidence_metadata(
    sha256: str,
    captured_at: datetime,
    request: Request,
) -> SensoryEvidenceReference:
    evidence_store = cast(EvidenceStore, request.app.state.evidence_store)
    artifact = await evidence_store.find_exact(
        sha256=sha256,
        captured_at=captured_at,
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensory evidence artifact was not found",
        )
    return artifact.reference()


@app.get("/v1/evidence/{sha256}", include_in_schema=False)
async def sensory_evidence_media(
    sha256: str,
    captured_at: datetime,
    request: Request,
) -> Response:
    evidence_store = cast(EvidenceStore, request.app.state.evidence_store)
    artifact = await evidence_store.find_exact(
        sha256=sha256,
        captured_at=captured_at,
    )
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sensory evidence artifact was not found",
        )
    try:
        payload = base64.b64decode(artifact.payload_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Stored sensory evidence is corrupted",
        ) from exc

    return Response(
        content=payload,
        media_type=artifact.media_type,
        headers={
            "Cache-Control": "private, no-store",
            "X-Evidence-SHA256": artifact.sha256,
            "X-Evidence-Captured-At": artifact.captured_at.isoformat(),
        },
    )


@app.get("/body/eyes", include_in_schema=False)
async def eyes_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "eyes.html")


@app.post("/v1/body/eyes/observe", response_model=Percept)
async def receive_browser_observation(
    body: BrowserVisionObservationRequest,
    request: Request,
) -> Percept:
    eyes = cast(BrowserVisionIngress, request.app.state.browser_eyes)
    try:
        return await eyes.accept(
            image_data_url=body.image_data_url,
            width=body.width,
            height=body.height,
            source=body.source,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@app.get("/v1/body/eyes/status")
async def eyes_status(request: Request) -> DeviceStatus:
    eyes = cast(BrowserVisionIngress, request.app.state.browser_eyes)
    return await eyes.status()


@app.get("/v1/body/eyes/see", response_model=Percept)
async def body_see(request: Request) -> Percept:
    runtime = cast(BodyRuntime, request.app.state.body)
    try:
        return await runtime.see()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.get("/body/ears", include_in_schema=False)
async def ears_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "ears.html")


@app.post("/v1/body/ears/observe", response_model=Percept)
async def receive_browser_audio_observation(
    body: BrowserAudioObservationRequest,
    request: Request,
) -> Percept:
    ears = cast(BrowserAudioIngress, request.app.state.browser_ears)
    try:
        return await ears.accept(
            audio_data_url=body.audio_data_url,
            duration_ms=body.duration_ms,
            source=body.source,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@app.get("/v1/body/ears/status")
async def ears_status(request: Request) -> DeviceStatus:
    ears = cast(BrowserAudioIngress, request.app.state.browser_ears)
    return await ears.status()


@app.get("/v1/body/ears/hear", response_model=Percept)
async def body_hear(request: Request) -> Percept:
    runtime = cast(BodyRuntime, request.app.state.body)
    try:
        return await runtime.hear()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@app.get("/body/face", include_in_schema=False)
async def face_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "face.html")


@app.post("/v1/body/face/expression", response_model=ExpressionIntent)
async def set_face_expression(
    body: FaceExpressionRequest,
    request: Request,
) -> ExpressionIntent:
    runtime = cast(BodyRuntime, request.app.state.body)
    intent = ExpressionIntent(
        modality=ExpressionModality.AVATAR,
        text=body.text,
        metadata={
            "expression": body.expression,
            "weight": body.weight,
        },
    )
    try:
        await runtime.present_intent(intent)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return intent


@app.get("/v1/body/face/avatar", include_in_schema=False)
async def default_face_avatar() -> Response:
    return Response(
        content=build_genesis_vrm(),
        media_type="model/gltf-binary",
        headers={"Content-Disposition": 'inline; filename="genesis.vrm"'},
    )


@app.get("/v1/body/face/status")
async def face_status(request: Request) -> DeviceStatus:
    face = cast(BrowserAvatarOutput, request.app.state.browser_face)
    return await face.status()


@app.get("/v1/body/face/next", response_model=ExpressionIntent | None)
async def next_face_intent(request: Request, response: Response) -> ExpressionIntent | None:
    face = cast(BrowserAvatarOutput, request.app.state.browser_face)
    if body_session.get() == "legacy":
        return await face.consume()
    intent, receipt = await face.deliver()
    if receipt:
        response.headers["X-Body-Delivery"] = receipt
    return intent


@app.get("/body/mouth", include_in_schema=False)
async def mouth_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "mouth.html")


@app.post("/v1/body/mouth/speak", response_model=ExpressionIntent)
async def speak_through_mouth(
    body: MouthSpeechRequest,
    request: Request,
) -> ExpressionIntent:
    runtime = cast(BodyRuntime, request.app.state.body)
    intent = ExpressionIntent(
        modality=ExpressionModality.VOICE,
        text=body.text,
        metadata={
            "rate": body.rate,
            "pitch": body.pitch,
            "volume": body.volume,
            "voice_name": body.voice_name,
        },
    )
    try:
        await runtime.speak_intent(intent)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return intent


@app.get("/v1/body/mouth/status")
async def mouth_status(request: Request) -> DeviceStatus:
    mouth = cast(BrowserVoiceOutput, request.app.state.browser_mouth)
    return await mouth.status()


@app.get("/v1/body/mouth/next", response_model=ExpressionIntent | None)
async def next_mouth_intent(request: Request, response: Response) -> ExpressionIntent | None:
    mouth = cast(BrowserVoiceOutput, request.app.state.browser_mouth)
    if body_session.get() == "legacy":
        return await mouth.consume()
    intent, receipt = await mouth.deliver()
    if receipt:
        response.headers["X-Body-Delivery"] = receipt
    return intent


@app.post("/v1/body/{modality}/ack")
async def acknowledge_body_output(modality: str, request: Request, delivery_id: str = Query(min_length=1, max_length=64)) -> dict[str, bool]:
    if modality not in {"face", "mouth"}:
        raise HTTPException(404, "Unknown output modality")
    queue = getattr(request.app.state, "browser_" + modality)
    await queue.acknowledge(delivery_id)
    return {"acknowledged": True}


@app.get("/health")
async def health(request: Request) -> dict[str, str]:
    await request.app.state.runtime.ping()
    return {"status": "healthy"}


@app.get("/v1/portal/status")
async def portal_status(request: Request) -> dict[str, Any]:
    tenant = getattr(request.state, "tenant_storage", None)
    service = (
        CognitiveMcpService(mind=tenant.mind, journal=tenant.journal, memory=tenant.memory)
        if tenant is not None
        else cast(CognitiveMcpService, request.app.state.mcp_service)
    )
    try:
        result = await service.status()
        runtime_settings = get_settings()
        provider = str(
            getattr(
                request.app.state,
                "standalone_reasoning_provider",
                runtime_settings.effective_standalone_reasoning_provider,
            )
        ).strip().lower()
        model = getattr(
            request.app.state,
            "reasoning_model",
            getattr(getattr(request.app.state, "standalone", None), "model", "not started"),
        )
        requested_model = (
            runtime_settings.gemini_model
            if provider == "gemini"
            else runtime_settings.openai_model
            if provider == "openai"
            else "deterministic-echo"
        )

        # Axiom's canonical reasoning owner is the external AI host using MCP.
        # The embedded provider exists only so the standalone Body/API can
        # reason when no external host is driving the interaction.
        result["reasoning"] = {
            "primary_mode": "external_host",
            "active_host": await request.app.state.hosts.active() if hasattr(request.app.state, "hosts") else None,
            "fallback_enabled": provider != "disabled",
            "external_host_protocol": "MCP",
            "external_host_reasoning_owner": "connected MCP host",
            "standalone_fallback": {
                "provider": provider,
                "model": model,
                "requested_model": requested_model,
            },
            "standalone_fallback_provider": provider,
            "standalone_fallback_model": model,
            "standalone_fallback_requested_model": requested_model,
            # Backwards-compatible fields for older Body clients.
            "backend": provider,
            "model": model,
            "requested_model": requested_model,
        }
        result["administration"] = {
            "pin_required": bool(runtime_settings.admin_pin),
            "memory_editing": True,
        }
        return result
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@app.get("/v1/portal/memory")
async def portal_memory(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("newest", pattern="^(newest|oldest)$"),
    memory_class: MemoryClass | None = None,
    search: str | None = Query(None, max_length=200),
    association: str | None = Query(None, max_length=200),
    grounding: str | None = Query(None, max_length=200),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> dict[str, Any]:
    tenant = getattr(request.state, "tenant_storage", None)
    memory_store = cast(MemoryStore, tenant.memory if tenant is not None else request.app.state.memory_store)
    formed_from = (
        datetime.combine(from_date, time.min, tzinfo=UTC)
        if from_date
        else None
    )
    formed_to = (
        datetime.combine(to_date, time.max, tzinfo=UTC)
        if to_date
        else None
    )
    memories, total = await memory_store.query_page(
        offset=offset,
        limit=limit,
        newest_first=order == "newest",
        memory_class=memory_class.value if memory_class else None,
        search=search.strip() if search else None,
        association=association.strip() if association else None,
        grounding=grounding.strip() if grounding else None,
        formed_from=formed_from,
        formed_to=formed_to,
    )
    next_offset = offset + len(memories)
    return {
        "items": memories,
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
    }


@app.get("/v1/portal/journal")
async def portal_journal(
    request: Request,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    order: str = Query("newest", pattern="^(newest|oldest)$"),
    kind: JournalKind | None = None,
    search: str | None = Query(None, max_length=200),
    from_date: date | None = Query(None, alias="from"),
    to_date: date | None = Query(None, alias="to"),
) -> dict[str, Any]:
    tenant = getattr(request.state, "tenant_storage", None)
    journal_store = cast(JournalStore, tenant.journal if tenant is not None else request.app.state.journal_store)
    occurred_from = (
        datetime.combine(from_date, time.min, tzinfo=UTC)
        if from_date
        else None
    )
    occurred_to = (
        datetime.combine(to_date, time.max, tzinfo=UTC)
        if to_date
        else None
    )
    entries, total = await journal_store.query_page(
        offset=offset,
        limit=limit,
        newest_first=order == "newest",
        kind=kind.value if kind else None,
        search=search.strip() if search else None,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
    )
    next_offset = offset + len(entries)
    return {
        "items": [_journal_summary(entry) for entry in entries],
        "total": total,
        "offset": offset,
        "limit": limit,
        "has_more": next_offset < total,
        "next_offset": next_offset if next_offset < total else None,
    }


@app.post("/v1/portal/journal/detail", response_model=JournalEntry)
async def portal_journal_detail(
    body: JournalDetailRequest,
    request: Request,
) -> JournalEntry:
    tenant = getattr(request.state, "tenant_storage", None)
    journal_store = cast(JournalStore, tenant.journal if tenant is not None else request.app.state.journal_store)
    entry = await journal_store.find_exact(
        kind=body.kind.value,
        occurred_at=body.occurred_at,
    )
    if entry is not None:
        return entry
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Journal experience was not found",
    )


async def _apply_admin_memory_revision(
    *,
    original: DurableMemory,
    replacement: DurableMemory,
    memory_store: MemoryStore,
    journal_store: JournalStore,
    channel: str,
) -> DurableMemory:
    from aicognitive_mind.commit import atomic
    class Revision:
        def __init__(self):
            self._memory, self._journal = memory_store, journal_store

        @atomic
        async def apply(self):
            governed_replacement = replacement.model_copy(
                update={
                    "formed_at": original.formed_at,
                    "artifacts": original.artifacts,
                }
            )
            revised = await self._memory.replace_exact(
                original,
                governed_replacement,
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
            if revised is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="The durable memory changed before this revision could be applied",
                )

            await self._journal.append(
                JournalEntry(
                    kind=JournalKind.MEMORY_REVISION,
                    experience={
                        "source": "human_administrator",
                        "channel": channel,
                        "before": original.model_dump(mode="python"),
                        "after": revised.model_dump(mode="python"),
                    },
                ),
                recorded_by=CognitiveActor.CONSCIOUS_MEMORY_STEWARD,
            )
            return revised
    return await Revision().apply()


@app.get("/v1/admin/backup", include_in_schema=False)
async def admin_backup(request: Request) -> Response:
    require_admin(request)

    mind_store = cast(MindStore, request.app.state.mind_store)
    journal_store = cast(JournalStore, request.app.state.journal_store)
    memory_store = cast(MemoryStore, request.app.state.memory_store)
    diagnostics_store = cast(DiagnosticStore, request.app.state.diagnostics)
    created_at = datetime.now(UTC)
    try:
        from aicognitive_mind.snapshot import cognitive_snapshot
        snapshot = await cognitive_snapshot(mind_store, journal_store, memory_store, diagnostics_store)
        mind, journal, memory, diagnostics = (snapshot[key] for key in ("mind", "journal", "memory", "diagnostics"))
        evidence = evidence_references_from_journal(journal)
        archive = build_backup_archive(
            mind=mind,
            journal=journal,
            memory=memory,
            diagnostics=diagnostics,
            evidence=evidence,
            storage_provider=get_settings().storage_provider.lower(),
            created_at=created_at,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "Backup snapshot failed while reading or serializing cognitive state: "
                f"{exc.__class__.__name__}"
            ),
        ) from exc
    filename = backup_filename(created_at)
    return Response(
        content=archive,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@app.get("/v1/admin/status")
async def admin_status(request: Request) -> dict[str, bool]:
    require_admin(request)
    return {"authorized": True, "memory_editing": True}


@app.put("/v1/admin/memory", response_model=DurableMemory)
async def revise_memory(
    body: AdminMemoryRevisionRequest,
    request: Request,
) -> DurableMemory:
    require_admin(request)
    return await _apply_admin_memory_revision(
        original=body.original,
        replacement=body.replacement,
        memory_store=cast(MemoryStore, request.app.state.memory_store),
        journal_store=cast(JournalStore, request.app.state.journal_store),
        channel="portal",
    )


@app.put("/v1/admin/desktop/memory", response_model=DurableMemory)
async def revise_desktop_memory(
    body: DesktopAdminMemoryRevisionRequest,
    request: Request,
) -> DurableMemory:
    require_admin(request)
    memory_store = cast(MemoryStore, request.app.state.memory_store)
    journal_store = cast(JournalStore, request.app.state.journal_store)

    candidates = [
        memory
        for memory in await memory_store.read()
        if (
            memory.memory_class == body.original_memory_class
            and memory.formed_at == body.original_formed_at
            and memory.content == body.original_content
            and memory.associations == body.original_associations
            and memory.grounding == body.original_grounding
        )
    ]
    if len(candidates) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The durable memory could not be resolved uniquely; "
                "refresh memory before editing"
            ),
        )

    original = candidates[0]
    replacement = DurableMemory(
        memory_class=body.replacement_memory_class,
        formed_at=original.formed_at,
        content=body.replacement_content,
        associations=body.replacement_associations,
        grounding=body.replacement_grounding,
        artifacts=original.artifacts,
    )
    return await _apply_admin_memory_revision(
        original=original,
        replacement=replacement,
        memory_store=memory_store,
        journal_store=journal_store,
        channel="desktop",
    )


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
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_reasoning_backend_error_detail(exc),
        ) from exc


@app.post("/v1/mind/body/interact", response_model=InteractionResult)
async def embodied_text_interaction(
    body: InteractionRequest,
    request: Request,
    express: bool = True,
) -> InteractionResult:
    try:
        bridge = cast(MindBodyBridge, request.app.state.mind_body)
        return await bridge.interact(body.message, express=express)
    except MindNotInitializedError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The mind has not been initialized",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=_reasoning_backend_error_detail(exc),
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
    diagnostics = cast(DiagnosticStore, request.app.state.diagnostics)
    return await diagnostics.read()
