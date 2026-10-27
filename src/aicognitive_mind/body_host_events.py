"""Private host capabilities for bounded local sensory preprocessing."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.config import get_settings
from aicognitive_mind.host_runtime import HostRuntime
from aicognitive_mind.persistence import scope_storage


class HostInputRequest(BaseModel):
    mind_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    lease_token: str = Field(min_length=20, max_length=256, repr=False)
    request_id: str = Field(min_length=1, max_length=128)


class HostFailureRequest(HostInputRequest):
    reason: str = Field(min_length=1, max_length=500)


class HostTranscriptRequest(HostInputRequest):
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    captured_at: datetime
    transcript: str = Field(max_length=16_000)
    model: str = Field(min_length=1, max_length=200)
    segments: list[dict[str, Any]] = Field(default_factory=list, max_length=128)


async def _authorized_host(payload: HostInputRequest, request: Request):
    storage = scope_storage(request.app.state.storage, payload.mind_id)
    hosts = HostRuntime(storage.mind, None, get_settings().reasoning_timeout_seconds)
    try:
        host = await hosts.require(payload.lease_token)
    except PermissionError as exc:
        raise HTTPException(401, "Invalid host capability") from exc
    return storage, hosts, host


def _pending_audio(record: dict | None) -> dict:
    if not record or record.get("kind") != "body_request" or (
        record.get("task") != "sensory_interpretation" or record.get("priority") != 10
    ):
        raise HTTPException(404, "Sensory input was not found")
    if record.get("state") != "pending" or (
        record.get("deadline") is not None and record["deadline"] <= time.time()
    ):
        raise HTTPException(410, "Sensory input is no longer pending")
    return record


def _live_claim(record: dict) -> bool:
    return bool(record.get("claim")) and (
        record.get("claim_until") is None or record["claim_until"] > time.time()
    )


def create_host_events_router() -> APIRouter:
    router = APIRouter(prefix="/v1/host-events")

    @router.post("/fail")
    async def fail_input(payload: HostFailureRequest, request: Request) -> dict:
        _storage, hosts, _host = await _authorized_host(payload, request)
        try:
            return await hosts.fail(payload.lease_token, payload.request_id, payload.reason)
        except PermissionError as exc:
            raise HTTPException(401, "Invalid host claim") from exc
        except CommitConflict as exc:
            raise HTTPException(409, "Sensory input changed") from exc
        except ValueError as exc:
            raise HTTPException(400, "Invalid sensory failure") from exc

    @router.post("/input")
    async def read_input(payload: HostInputRequest, request: Request) -> dict:
        storage, hosts, host = await _authorized_host(payload, request)
        record = _pending_audio(await hosts.records.get(payload.request_id))
        context = record.get("input_context", {})
        evidence = context.get("evidence", {})
        result = {
            "request_id": payload.request_id, "state": record["state"],
            "modality": context.get("modality"), "evidence": evidence,
        }
        if context.get("modality") != "audio":
            return result
        if context.get("derived_audio") is not None:
            return {**result, "derived_audio": context["derived_audio"]}
        if _live_claim(record) and not (
            record.get("preparing_audio") and record.get("claim") == host["token_hash"]
        ):
            raise HTTPException(409, "Sensory input is already being processed")
        try:
            captured = datetime.fromisoformat(evidence["captured_at"].replace("Z", "+00:00"))
            artifact = await storage.evidence.find_exact(
                sha256=evidence["sha256"], captured_at=captured,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid preserved audio reference") from exc
        if artifact is None:
            raise HTTPException(404, "Preserved audio was not found")
        try:
            raw = base64.b64decode(artifact.payload_base64, validate=True)
        except ValueError as exc:
            raise HTTPException(500, "Preserved audio integrity check failed") from exc
        if len(raw) != artifact.byte_length or hashlib.sha256(raw).hexdigest() != artifact.sha256:
            raise HTTPException(500, "Preserved audio integrity check failed")
        if len(raw) > 8_000_000:
            raise HTTPException(413, "Audio exceeds the preprocessing limit")
        now = time.time()
        prepared = {
            **record, "claim": host["token_hash"], "preparing_audio": True,
            "claim_until": min(record.get("deadline") or now + hosts.timeout, now + hosts.timeout),
        }
        if not await hosts.records.replace(payload.request_id, record, prepared):
            raise HTTPException(409, "Sensory input changed")
        return {**result, "audio_base64": artifact.payload_base64, "media_type": artifact.media_type}

    @router.post("/transcript")
    async def attach_transcript(payload: HostTranscriptRequest, request: Request) -> dict:
        _storage, hosts, host = await _authorized_host(payload, request)
        try:
            segment_size = len(json.dumps(payload.segments, allow_nan=False))
        except (TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid transcript segment metadata") from exc
        if segment_size > 40_000:
            raise HTTPException(400, "Transcript segment metadata exceeds its limit")
        record = await hosts.records.get(payload.request_id)
        if not record or record.get("task") != "sensory_interpretation" or (
            record.get("input_context", {}).get("modality") != "audio"
        ):
            raise HTTPException(404, "Audio input was not found")
        context = record.get("input_context", {})
        evidence = context.get("evidence", {})
        try:
            captured = datetime.fromisoformat(evidence["captured_at"].replace("Z", "+00:00"))
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(400, "Invalid preserved audio reference") from exc
        if evidence.get("sha256") != payload.sha256 or captured != payload.captured_at:
            raise HTTPException(400, "Transcript does not match the preserved audio")
        derived = {
            "source": "local_asr", "transcript": payload.transcript,
            "model": payload.model, "segments": payload.segments,
            "sha256": payload.sha256, "captured_at": evidence["captured_at"],
        }
        existing = context.get("derived_audio")
        if existing is not None:
            if existing != derived:
                raise HTTPException(409, "A different derived transcript already exists")
            return {"accepted": True, "request_id": payload.request_id, "derived_audio": existing}
        _pending_audio(record)
        if not record.get("preparing_audio") or record.get("claim") != host["token_hash"] or not _live_claim(record):
            raise HTTPException(409, "Audio preparation is not owned by this host")
        revised = {
            **record, "input_context": {**context, "derived_audio": derived},
            "claim": "", "claim_until": 0.0, "preparing_audio": False,
        }
        if not await hosts.records.replace(payload.request_id, record, revised):
            raise HTTPException(409, "Sensory input changed")
        return {"accepted": True, "request_id": payload.request_id, "derived_audio": derived}

    return router
