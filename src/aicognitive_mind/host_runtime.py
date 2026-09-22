"""Storage-backed external-host leases and Body handoff, shared by API and MCP."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import time
from copy import deepcopy
from typing import Any
from uuid import uuid4

from aicognitive_mind.commit import CommitConflict, backend


class RuntimeRecords:
    def __init__(self, mind: Any) -> None:
        self.kind, self.db = backend({"mind": mind})

    async def get(self, key: str) -> dict | None:
        if self.kind == "mongo":
            value = await self.db["runtime_records"].find_one({"_id": key})
        elif self.kind == "surreal":
            from surrealdb import RecordID

            value = await self.db.select(RecordID("runtime_records", key))
            if isinstance(value, list):
                value = value[0] if value else None
        else:
            value = getattr(self.db, "_runtime_records", {}).get(key)
        return (
            {k: deepcopy(v) for k, v in value.items() if k not in {"id", "_id"}} if value else None
        )

    async def create(self, key: str, value: dict) -> None:
        if self.kind == "mongo":
            await self.db["runtime_records"].insert_one({"_id": key, **value})
        elif self.kind == "surreal":
            from surrealdb import RecordID

            await self.db.create(RecordID("runtime_records", key), value)
        else:
            if not hasattr(self.db, "_runtime_records"):
                self.db._runtime_records = {}
            if key in self.db._runtime_records:
                raise CommitConflict("Runtime record already exists")
            self.db._runtime_records[key] = deepcopy(value)

    async def replace(self, key: str, before: dict, after: dict) -> bool:
        if self.kind == "mongo":
            result = await self.db["runtime_records"].replace_one({"_id": key, **before}, after)
            return result.matched_count == 1
        if self.kind == "surreal":
            from surrealdb import RecordID

            conditions = " AND ".join(f"{field} = $before.{field}" for field in before)
            result = await self.db.query(
                f"UPDATE $record CONTENT $after WHERE {conditions} RETURN AFTER;",
                {"record": RecordID("runtime_records", key), "before": before, "after": after},
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
                .find({"kind": "body_request", "state": "pending", "deadline": {"$gt": now}})
                .sort("created", 1)
                .limit(20)
            )
            return [{k: v for k, v in row.items() if k != "_id"} async for row in cursor]
        if self.kind == "surreal":
            return await self.db.query(
                "SELECT * OMIT id FROM runtime_records WHERE kind = 'body_request' AND state = 'pending' AND deadline > $now ORDER BY created LIMIT 20;",
                {"now": now},
            )
        return sorted(
            [
                deepcopy(v)
                for v in getattr(self.db, "_runtime_records", {}).values()
                if v.get("kind") == "body_request"
                and v["state"] == "pending"
                and v["deadline"] > now
            ],
            key=lambda v: v["created"],
        )[:20]


class HostRuntime:
    def __init__(self, mind: Any, service: Any, timeout: float = 120) -> None:
        self.records = RuntimeRecords(mind)
        self.service, self.timeout = service, timeout

    async def active(self) -> dict | None:
        host = await self.records.get("active_host")
        if not host or host["expires"] <= time.time():
            return None
        return {key: host[key] for key in ("name", "model", "expires")}

    async def attach(self, name: str, model: str, lease_seconds: int = 120) -> dict:
        if (
            not name.strip()
            or len(name) > 120
            or len(model) > 200
            or not 15 <= lease_seconds <= 300
        ):
            raise ValueError("Invalid host name, model or lease duration (15–300 seconds)")
        before = await self.records.get("active_host")
        if before and before["expires"] > time.time():
            raise CommitConflict("An external host already owns the live lease")
        token = secrets.token_urlsafe(32)
        host = {
            "name": name,
            "model": model,
            "expires": time.time() + lease_seconds,
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
            or host["expires"] <= time.time()
            or not secrets.compare_digest(host["token_hash"], digest)
        ):
            raise PermissionError("External-host lease is absent, expired or owned by another host")
        return host

    async def renew(self, token: str, detach: bool = False) -> dict:
        host = await self.require(token)
        revised = {**host, "expires": 0 if detach else time.time() + 120}
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
            "deadline": time.time() + self.timeout,
            "claim": "",
            "claim_until": 0.0,
            "result": {},
        }
        await self.records.create(key, request)
        while time.time() < request["deadline"]:
            latest = await self.records.get(key)
            if latest and latest["state"] == "complete":
                return latest["result"]
            await asyncio.sleep(0.2)
        raise TimeoutError("External host did not complete the Body request before its deadline")

    async def next_request(self, token: str) -> dict | None:
        host = await self.require(token)
        for request in await self.records.pending():
            claimed = {
                **request,
                "claim": host["token_hash"],
                "claim_until": min(host["expires"], request["deadline"]),
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
        if min(request["deadline"], request["claim_until"]) <= time.time():
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
        return await self.core.interact(message, source=source, input_context=input_context)


class HostAwareInterpreter:
    def __init__(self, fallback: Any, hosts: HostRuntime) -> None:
        self.fallback, self.hosts = fallback, hosts

    async def interpret(self, percept: Any, *, focus: str | None = None) -> str:
        if await self.hosts.active():
            return f"Uninterpreted {percept.modality.value} observation. Use the sensory evidence reference in Body context to inspect the original media."
        return await self.fallback.interpret(percept, focus=focus)
