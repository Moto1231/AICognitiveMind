"""Storage-backed external-host leases and Body handoff, shared by API and MCP."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import time
from copy import deepcopy
from typing import Any
from uuid import uuid4

from aicognitive_mind.commit import CommitConflict, backend, surreal_query
from aicognitive_mind.task_dispatcher import TaskDispatchError, TaskModelDispatcher


logger = logging.getLogger('aicognitive_mind.auth_diagnostics')


class RuntimeRecords:
    def __init__(self, mind: Any) -> None:
        self.kind, self.db = backend({"mind": mind})
        self.mind_id = str(getattr(mind, "mind_id", "root"))

    async def get(self, key: str) -> dict | None:
        if self.kind == "mongo":
            # Accounts are global selectors for tenant Minds. Do not scope them
            # to the current root Mind, which may change across deployments.
            query = {"key": key} if key.startswith("account_") else {
                "mind_id": self.mind_id,
                "key": key,
            }
            value = await self.db["runtime_records"].find_one(query)
        elif self.kind == "surreal":
            from surrealdb import RecordID

            # Accounts are global selectors for tenant Minds, not state owned by
            # whichever root Mind happens to initialize the deployed process.
            # Keep one canonical unscoped account registry across root mind IDs.
            if key.startswith("account_"):
                # Account identity is the globally unique deterministic key. Query
                # by that key first so login can recover accounts written under
                # either the canonical or the briefly shipped tenant-scoped ID.
                # surreal_query normalizes driver response envelopes.
                results = await surreal_query(
                    self.db,
                    "SELECT * FROM runtime_records WHERE key = $key LIMIT 1;",
                    {"key": key},
                )
                matches = results[0] if results else []
                value = matches[0] if isinstance(matches, list) and matches else None
                if value is not None:
                    logger.warning("AUTH_DIAG registry key_lookup_found")
                else:
                    logger.warning("AUTH_DIAG registry key_lookup_missing")
                    # Recover canonical records created before `key` was
                    # persisted as a field on the record.
                    value = await self.db.select(RecordID("runtime_records", key))
                    if isinstance(value, list):
                        value = value[0] if value else None
                    logger.warning(
                        "AUTH_DIAG registry canonical_id_lookup result=%s",
                        "found" if value else "missing",
                    )
            else:
                scoped_id = RecordID(
                    "runtime_records",
                    f"{self.mind_id}__{key}",
                )
                value = await self.db.select(scoped_id)
                if isinstance(value, list):
                    value = value[0] if value else None
                if value is None and self.mind_id == "axiom":
                    value = await self.db.select(RecordID("runtime_records", key))
                    if isinstance(value, list):
                        value = value[0] if value else None
        else:
            value = getattr(self.db, "_runtime_records", {}).get(key)
        return (
            {
                k: deepcopy(v)
                for k, v in value.items()
                if k not in {"id", "_id", "mind_id", "key"}
            }
            if value
            else None
        )

    async def create(self, key: str, value: dict) -> None:
        if self.kind == "mongo":
            await self.db["runtime_records"].insert_one(
                {
                    "_id": key if key.startswith("account_") else f"{self.mind_id}:{key}",
                    "mind_id": self.mind_id,
                    "key": key,
                    **value,
                }
            )
        elif self.kind == "surreal":
            from surrealdb import RecordID

            record_id = (
                RecordID("runtime_records", key)
                if key.startswith("account_")
                else RecordID("runtime_records", f"{self.mind_id}__{key}")
            )
            await self.db.create(
                record_id,
                {
                    "mind_id": self.mind_id,
                    "key": key,
                    **value,
                },
            )
        else:
            if not hasattr(self.db, "_runtime_records"):
                self.db._runtime_records = {}
            if key in self.db._runtime_records:
                raise CommitConflict("Runtime record already exists")
            self.db._runtime_records[key] = deepcopy(value)

    async def replace(self, key: str, before: dict, after: dict) -> bool:
        if self.kind == "mongo":
            selector = {"key": key, **before} if key.startswith("account_") else {
                "mind_id": self.mind_id,
                "key": key,
                **before,
            }
            result = await self.db["runtime_records"].replace_one(
                selector,
                {
                    "mind_id": self.mind_id,
                    "key": key,
                    **after,
                },
            )
            return result.matched_count == 1
        if self.kind == "surreal":
            from surrealdb import RecordID

            scoped_id = RecordID(
                "runtime_records",
                f"{self.mind_id}__{key}",
            )
            target_id = (
                RecordID("runtime_records", key)
                if key.startswith("account_")
                else scoped_id
            )
            current = await self.db.select(target_id)
            if isinstance(current, list):
                current = current[0] if current else None
            if current is None and (self.mind_id == "axiom" or key.startswith("account_")):
                legacy_id = (
                    scoped_id if key.startswith("account_")
                    else RecordID("runtime_records", key)
                )
                current = await self.db.select(legacy_id)
                if isinstance(current, list):
                    current = current[0] if current else None
                if current is not None:
                    target_id = legacy_id
            conditions = " AND ".join(
                f"{field} = $before.{field}" for field in before
            )
            result = await self.db.query(
                f"UPDATE $record CONTENT $after WHERE {conditions} RETURN AFTER;",
                {
                    "record": target_id,
                    "before": before,
                    "after": {
                        "mind_id": self.mind_id,
                        "key": key,
                        **after,
                    },
                },
            )
            return bool(result)
        if await self.get(key) != before:
            return False
        self.db._runtime_records[key] = deepcopy(after)
        return True

    async def pending(self) -> list[dict]:
        now = time.time()
        if self.kind == "mongo":
            cursor = (
                self.db["runtime_records"]
                .find(
                    {
                        "mind_id": self.mind_id,
                        "kind": "body_request",
                        "state": "pending",
                        "$or": [
                            {"deadline": {"$gt": now}},
                            {"deadline": {"$exists": False}},
                            {"deadline": None},
                        ],
                    }
                )
                .sort("created", 1)
                .limit(20)
            )
            return [
                {
                    k: v
                    for k, v in row.items()
                    if k not in {"_id", "mind_id", "key"}
                }
                async for row in cursor
            ]
        if self.kind == "surreal":
            return await self.db.query(
                "SELECT * OMIT id, mind_id, key FROM runtime_records "
                "WHERE mind_id = $mind_id AND kind = 'body_request' "
                "AND state = 'pending' AND (deadline IS NONE OR deadline > $now) "
                "ORDER BY created LIMIT 20;",
                {"now": now, "mind_id": self.mind_id},
            )
        return sorted(
            [
                deepcopy(v)
                for v in getattr(self.db, "_runtime_records", {}).values()
                if v.get("kind") == "body_request"
                and v["state"] == "pending"
                and (v.get("deadline") is None or v["deadline"] > now)
            ],
            key=lambda v: v["created"],
        )[:20]


class HostRuntime:
    def __init__(self, mind: Any, service: Any, timeout: float = 120) -> None:
        self.records = RuntimeRecords(mind)
        self.service, self.timeout = service, timeout

    async def active(self) -> dict | None:
        host = await self.records.get("active_host")
        if not host or (
            host.get("expires") is not None and host["expires"] <= time.time()
        ):
            return None
        return {
            key: host.get(key)
            for key in ("name", "model", "expires", "attached_at", "last_heartbeat_at")
        }

    async def status(self) -> dict:
        now = time.time()
        host = await self.active()
        requests = await self.records.pending()
        items = []
        for request in requests:
            raw_claim_until = request.get("claim_until")
            claim_until = (
                float(raw_claim_until) if raw_claim_until is not None else None
            )
            in_progress = bool(request.get("claim")) and (
                claim_until is None or claim_until > now
            )
            items.append({
                "request_id": request["request_id"],
                "state": "in_progress" if in_progress else "pending",
                "age_seconds": max(0, int(now - float(request.get("created", now)))),
                "remaining_seconds": (
                    max(0, int(float(request["deadline"]) - now))
                    if request.get("deadline") is not None else None
                ),
            })
        pending_count = sum(item["state"] == "pending" for item in items)
        in_progress_count = sum(item["state"] == "in_progress" for item in items)
        return {
            "connected": host is not None,
            "host": host,
            "lease_remaining_seconds": (
                max(0, int(float(host["expires"]) - now))
                if host and host.get("expires") is not None else None
            ),
            "last_heartbeat_age_seconds": (
                max(0, int(now - float(host["last_heartbeat_at"])))
                if host and host.get("last_heartbeat_at") is not None else None
            ),
            "requests": {
                "pending": pending_count,
                "in_progress": in_progress_count,
                "items": items,
            },
        }

    async def attach(self, name: str, model: str, lease_seconds: int = 120) -> dict:
        if (
            not name.strip()
            or len(name) > 120
            or len(model) > 200
        ):
            raise ValueError("Invalid host name or model")
        # The reasoning host is persistent. Specialist/task-provider calls own their
        # own deadlines; a Body request or idle period must not expire this connection.
        # Keep lease_seconds as a compatibility parameter for existing callers.
        before = await self.records.get("active_host")
        if before and (
            before.get("expires") is None or before["expires"] > time.time()
        ):
            raise CommitConflict("An external host already owns the live lease")
        token = secrets.token_urlsafe(32)
        now = time.time()
        host = {
            "name": name,
            "model": model,
            "attached_at": now,
            "last_heartbeat_at": now,
            "expires": None,
            "token_hash": hashlib.sha256(token.encode()).hexdigest(),
        }
        if before:
            if not await self.records.replace("active_host", before, host):
                raise CommitConflict("Another host attached concurrently")
        else:
            await self.records.create("active_host", host)
        return {"lease_token": token, "expires": host["expires"]}

    async def require(self, token: str) -> dict:
        host = await self.records.get("active_host")
        digest = hashlib.sha256(token.encode()).hexdigest()
        if (
            not host
            or (
                host.get("expires") is not None
                and host["expires"] <= time.time()
            )
            or not secrets.compare_digest(host["token_hash"], digest)
        ):
            raise PermissionError("External-host lease is absent, expired or owned by another host")
        return host

    async def renew(self, token: str, detach: bool = False) -> dict:
        host = await self.require(token)
        now = time.time()
        revised = {
            **host,
            "expires": 0 if detach else None,
            "last_heartbeat_at": now,
        }
        if not await self.records.replace("active_host", host, revised):
            raise CommitConflict("Host lease changed")
        return {"expires": revised["expires"]}

    async def submit(self, message: str) -> dict:
        if not await self.active():
            raise RuntimeError("No external reasoning host is attached")
        key = uuid4().hex
        request = {
            "kind": "body_request",
            "request_id": key,
            "state": "pending",
            "message": message,
            "created": time.time(),
            # Main reasoning requests have no task-provider deadline. They remain
            # pending until the connected reasoning host explicitly completes them.
            "deadline": None,
            "claim": "",
            "claim_until": 0.0,
            "result": {},
        }
        await self.records.create(key, request)
        while True:
            latest = await self.records.get(key)
            if latest and latest["state"] == "complete":
                return latest["result"]
            await asyncio.sleep(0.2)

    async def next_request(self, token: str) -> dict | None:
        host = await self.require(token)
        for request in await self.records.pending():
            claimed = {
                **request,
                "claim": host["token_hash"],
                "claim_until": (
                    min(host["expires"], request["deadline"])
                    if host.get("expires") is not None and request.get("deadline") is not None
                    else None
                ),
            }
            if await self.records.replace(request["request_id"], request, claimed):
                context = await self.service.begin_interaction(request["message"])
                return {
                    "request_id": request["request_id"],
                    "user_message": request["message"],
                    "context": context,
                }
        return None

    async def complete(
        self, token: str, request_id: str, response_text: str, proposed_memories: tuple = ()
    ) -> dict:
        host = await self.require(token)
        request = await self.records.get(request_id)
        if (
            not request
            or request.get("kind") != "body_request"
            or request["claim"] != host["token_hash"]
        ):
            raise PermissionError("Body request was not claimed by this host")
        if request["state"] == "complete":
            if request["result"]["response_text"] != response_text:
                raise CommitConflict("Body request already completed with another response")
            return request["result"]
        deadlines = [
            float(value)
            for value in (request.get("deadline"), request.get("claim_until"))
            if value is not None
        ]
        if deadlines and min(deadlines) <= time.time():
            raise CommitConflict("Body request claim expired")
        committed = await self.service.complete_interaction(
            request["message"],
            response_text,
            proposed_memories=proposed_memories,
            idempotency_key="body:" + request_id,
        )
        result = {"response_text": response_text, "occurred_at": committed["occurred_at"]}
        if not await self.records.replace(
            request_id, request, {**request, "state": "complete", "result": result}
        ):
            raise CommitConflict("Body request changed; retry completion with the same response")
        return result


class HostAwareCore:
    """Route Body cognition to a live host; never silently double-run a timeout."""

    def __init__(self, core: Any, hosts: HostRuntime) -> None:
        self.core, self.hosts = core, hosts

    def __getattr__(self, name: str) -> Any:
        return getattr(self.core, name)

    async def interact(
        self, message: str, *, source: str = "human", input_context: dict | None = None
    ) -> Any:
        if await self.hosts.active():
            import json

            from aicognitive_mind.domain import InteractionResult

            if input_context:
                message += "\nBody context: " + json.dumps(input_context, default=str)
            return InteractionResult.model_validate(await self.hosts.submit(message))
        from aicognitive_mind.config import body_allow_standalone_fallback_enabled

        if not body_allow_standalone_fallback_enabled():
            raise RuntimeError(
                "No external reasoning host is attached. Body standalone fallback is disabled."
            )
        return await self.core.interact(message, source=source, input_context=input_context)


class HostAwareInterpreter:
    def __init__(self, fallback: Any, hosts: HostRuntime) -> None:
        self.fallback, self.hosts = fallback, hosts
        self.task_dispatcher = (
            TaskModelDispatcher(fallback.records)
            if getattr(fallback, "records", None) is not None else None
        )

    async def interpret(self, percept: Any, *, focus: str | None = None) -> str:
        task_dispatch_failed = False
        if self.task_dispatcher is not None:
            modality = getattr(getattr(percept, "modality", None), "value", "")
            if modality in {"vision", "audio"}:
                try:
                    specialist_result = await self.task_dispatcher.interpret_percept(
                        percept, focus=focus
                    )
                except TaskDispatchError as exc:
                    task_dispatch_failed = True
                    logger.warning(
                        "sensory_task_failed modality=%s error=%s; handing preserved evidence to reasoning",
                        modality, exc,
                    )
                else:
                    if specialist_result is not None:
                        return specialist_result
        host = await self.hosts.active()
        if host:
            # The reasoning host is the default interpreter whenever no specialist
            # is explicitly configured. Preserve the evidence locator and metadata
            # in the request so the host can use the same evidence trail as the Body.
            import json

            percept_payload = percept.model_dump(mode="json")
            content_ref = percept_payload.get("content_ref")
            if isinstance(content_ref, str) and content_ref.startswith("data:"):
                # Large inline media is not a useful text prompt. Evidence IDs and
                # metadata remain available for the host to retrieve the persisted item.
                percept_payload["content_ref"] = (
                    content_ref if len(content_ref) <= 120_000
                    else "[inline media omitted from text handoff; use persisted evidence references]"
                )
            prompt = (
                f"Interpret this {percept.modality.value} percept as Axiom's default "
                "reasoning host. Describe only what the evidence supports. If the original "
                "media is not accessible from the supplied evidence reference, say so clearly "
                "instead of inventing an interpretation.\n"
                + (f"Requested focus: {focus}\n" if focus else "")
                + "PERCEPT:\n"
                + json.dumps(percept_payload, ensure_ascii=False, separators=(",", ":"))
            )
            try:
                result = await self.hosts.submit(prompt)
            except Exception as exc:
                raise RuntimeError(
                    f"Reasoning-host interpretation failed for {percept.modality.value}: "
                    f"{exc.__class__.__name__}: {exc}"
                ) from exc
            response_text = result.get("response_text") if isinstance(result, dict) else None
            if isinstance(response_text, str) and response_text.strip():
                return response_text.strip()
            raise RuntimeError(
                f"Reasoning host returned no interpretation for {percept.modality.value} evidence."
            )
        from aicognitive_mind.config import body_allow_standalone_fallback_enabled

        if not body_allow_standalone_fallback_enabled():
            modality = getattr(getattr(percept, "modality", None), "value", "unknown")
            if modality in {"audio", "vision"} and self.task_dispatcher is not None:
                task_label = {
                    "audio": "Audio & Transcription",
                    "vision": "Vision",
                }[modality]
                raise RuntimeError(
                    f"No external reasoning host is attached and the {task_label} "
                    "task has no configured provider/model assignment, or both its "
                    "primary and fallback failed. Configure the specialist task in Axiom settings "
                    "or reconnect the reasoning host."
                )
            raise RuntimeError(
                "No external reasoning host is attached. Body standalone fallback is disabled."
            )
        if task_dispatch_failed:
            # Let the independently configured Body reasoning fallback inspect the
            # preserved evidence rather than retrying the same failed task route.
            return (
                f"Uninterpreted {percept.modality.value} observation after the configured "
                "task primary and fallback failed. Use the sensory evidence reference "
                "in Body context to inspect the original media."
            )
        return await self.fallback.interpret(percept, focus=focus)
