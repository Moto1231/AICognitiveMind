"""Staged cognitive writes, atomic storage commits and durable retry receipts.

Transaction metadata belongs to storage, never to Mind identity or memories.
Mongo deployments require a replica set (Atlas already provides one).
"""

from __future__ import annotations

import hashlib
import inspect
import json
from copy import copy, deepcopy
from functools import wraps
from typing import Any

from pydantic import BaseModel

from aicognitive_mind.permissions import CognitiveOperation
from aicognitive_mind.storage import MindAlreadyInitializedError


class CommitConflict(RuntimeError):
    pass


def document(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(k): document(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [document(v) for v in value]
    return value


class StagedStore:
    def __init__(self, base: Any, table: str, operations: list) -> None:
        self.base, self.table, self.operations = base, table, operations

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)

    async def read(self) -> list:
        values = await self.base.read()
        for table, operation, before, after in self.operations:
            if table != self.table:
                continue
            if operation == "replace":
                values = [deepcopy(after) if item == before else item for item in values]
            else:
                values.append(deepcopy(after))
        return values

    async def load(self) -> Any:
        result = await self.base.load()
        for table, _, _, after in self.operations:
            if table == self.table:
                result = after
        return deepcopy(result)

    async def initialize(self, value: Any) -> Any:
        if await self.load() is not None:
            raise MindAlreadyInitializedError("This instance already contains its mind")
        self.operations.append((self.table, "initialize", None, value))
        return deepcopy(value)

    async def append(self, value: Any, recorded_by: Any) -> Any:
        self.base._policy.assert_allowed(recorded_by, CognitiveOperation.RECORD_JOURNAL)
        self.operations.append((self.table, "append", None, value))
        return deepcopy(value)

    async def remember(self, value: Any, recorded_by: Any) -> Any:
        self.base._policy.assert_allowed(recorded_by, CognitiveOperation.WRITE_DURABLE_MEMORY)
        self.operations.append((self.table, "append", None, value))
        return deepcopy(value)

    async def replace_exact(self, original: Any, replacement: Any, recorded_by: Any) -> Any:
        operation = (
            CognitiveOperation.APPROVE_IDENTITY_REVISION
            if self.table == "mind"
            else CognitiveOperation.WRITE_DURABLE_MEMORY
        )
        self.base._policy.assert_allowed(recorded_by, operation)
        values = [await self.load()] if self.table == "mind" else await self.read()
        if original not in values:
            return None
        self.operations.append((self.table, "replace", original, replacement))
        return deepcopy(replacement)


def backend(stores: dict) -> tuple[str, Any]:
    store = next(iter(stores.values()))
    if hasattr(store, "_collection"):
        return "mongo", store._collection.database
    if hasattr(store, "_database"):
        return "surreal", store._database
    return "memory", next(iter(stores.values()))


def storage_mind_id(stores: dict) -> str:
    ids = {
        str(store.mind_id)
        for store in stores.values()
        if getattr(store, "mind_id", None) is not None
    }
    if len(ids) > 1:
        raise CommitConflict("Cognitive commit spans more than one mind_id")
    return next(iter(ids), "root")


async def receipt(stores: dict, key: str | None) -> Any:
    if key is None:
        return None
    kind, db = backend(stores)
    if kind == "mongo":
        mind_id = storage_mind_id(stores)
        return await db["commit_receipts"].find_one(
            {"mind_id": mind_id, "key": key}
        )
    if kind == "surreal":
        from surrealdb import RecordID

        value = await db.select(RecordID("commit_receipts", key))
        return value[0] if isinstance(value, list) and value else value or None
    return getattr(db, "_commit_receipts", {}).get(key)


async def surreal_query(db: Any, sql: str, variables: dict | None = None) -> list:
    response = await db.query_raw(sql, variables or {})
    if "error" in response:
        raise CommitConflict(str(response["error"]))
    results = response.get("result", [])
    for item in results:
        if item.get("status") != "OK":
            raise CommitConflict(str(item.get("result", "Transaction failed")))
    return [item.get("result") for item in results]


async def revision(stores: dict) -> int:
    kind, db = backend(stores)
    if kind == "mongo":
        mind_id = storage_mind_id(stores)
        row = await db["commit_state"].find_one({"mind_id": mind_id})
        return row["version"] if row else 0
    if kind == "surreal":
        from surrealdb import RecordID

        row = await db.select(RecordID("commit_state", "root"))
        if isinstance(row, list):
            row = row[0] if row else None
        return row["version"] if row else 0
    return getattr(db, "_commit_revision", 0)


async def commit(
    stores: dict,
    operations: list,
    key: str | None,
    saved: dict,
    expected_version: int | None = None,
) -> None:
    kind, db = backend(stores)
    if not operations and not key:
        return
    if expected_version is None:
        expected_version = await revision(stores)
    if kind == "surreal":
        variables: dict = {"expected_version": expected_version}
        statements = [
            "BEGIN TRANSACTION;",
            "LET $version = (SELECT VALUE version FROM ONLY commit_state:root) ?? 0;",
            "IF $version != $expected_version { THROW 'Concurrent cognitive commit; begin again'; };",
            "UPSERT commit_state:root SET version = $expected_version + 1;",
        ]
        for i, (table, operation, before, after) in enumerate(operations):
            variables[f"after{i}"] = document(after)
            if operation == "initialize":
                statements += [
                    f"IF array::len(SELECT * FROM {table}) > 0 {{ THROW 'Mind already initialized'; }};",
                    f"CREATE ONLY {table}:root CONTENT $after{i};",
                ]
            elif operation == "replace":
                variables[f"before{i}"] = document(before)
                statements += [
                    f"LET $changed{i} = UPDATE {table} CONTENT $after{i} WHERE {' AND '.join(f'{field} = $before{i}.{field}' for field in type(before).model_fields)} RETURN AFTER;",
                    f"IF array::len($changed{i}) != 1 {{ THROW 'Concurrent cognitive revision'; }};",
                ]
            else:
                statements.append(f"CREATE {table} CONTENT $after{i};")
        if key:
            from surrealdb import RecordID

            variables.update(receipt_id=RecordID("commit_receipts", key), receipt=saved)
            statements.append("CREATE ONLY $receipt_id CONTENT $receipt;")
        statements.append("COMMIT TRANSACTION;")
        if operations or key:
            await surreal_query(db, "\n".join(statements), variables)
        return
    if kind == "mongo":
        mind_id = storage_mind_id(stores)
        async with db.client.start_session() as session:
            async with await session.start_transaction():
                state = await db["commit_state"].find_one(
                    {"mind_id": mind_id},
                    session=session,
                )
                if (state["version"] if state else 0) != expected_version:
                    raise CommitConflict("Concurrent cognitive commit; begin again")
                await db["commit_state"].replace_one(
                    {"mind_id": mind_id},
                    {
                        "mind_id": mind_id,
                        "version": expected_version + 1,
                    },
                    upsert=True,
                    session=session,
                )
                for table, operation, before, after in operations:
                    value = after.model_dump(mode="python")
                    scoped_value = {"mind_id": mind_id, **value}
                    if operation == "initialize":
                        if await db[table].find_one(
                            {"mind_id": mind_id},
                            session=session,
                        ):
                            raise MindAlreadyInitializedError(
                                "This mind is already initialized"
                            )
                        await db[table].insert_one(
                            {
                                "_id": mind_id,
                                **scoped_value,
                            },
                            session=session,
                        )
                    elif operation == "replace":
                        selector = {
                            "mind_id": mind_id,
                            **before.model_dump(mode="python"),
                        }
                        replacement = scoped_value
                        if table == "mind":
                            replacement = {
                                "_id": mind_id,
                                **scoped_value,
                            }
                        result = await db[table].replace_one(
                            selector,
                            replacement,
                            session=session,
                        )
                        if result.matched_count != 1:
                            raise CommitConflict("Concurrent cognitive revision")
                    else:
                        await db[table].insert_one(scoped_value, session=session)
                if key:
                    await db["commit_receipts"].insert_one(
                        {
                            "_id": f"{mind_id}:{key}",
                            "mind_id": mind_id,
                            "key": key,
                            **saved,
                        },
                        session=session,
                    )
        return
    # In-memory stores are test doubles. Apply to copies and publish without awaits.
    attributes = {"mind": "_mind", "memory": "_memories", "journal": "_entries"}
    if getattr(db, "_commit_revision", 0) != expected_version:
        raise CommitConflict("Concurrent cognitive commit; begin again")
    pending = {
        table: deepcopy(getattr(store, attributes[table])) for table, store in stores.items()
    }
    for table, operation, before, after in operations:
        if operation == "initialize":
            if pending[table] is not None:
                raise MindAlreadyInitializedError("This instance already contains its mind")
            pending[table] = deepcopy(after)
        elif operation == "replace":
            if table == "mind":
                if pending[table] != before:
                    raise CommitConflict("Concurrent identity revision")
                pending[table] = deepcopy(after)
            else:
                if before not in pending[table]:
                    raise CommitConflict("Concurrent memory revision")
                pending[table][pending[table].index(before)] = deepcopy(after)
        else:
            pending[table].append(deepcopy(after))
    if key and key in getattr(db, "_commit_receipts", {}):
        raise CommitConflict("Concurrent completion")
    for table, value in pending.items():
        setattr(stores[table], attributes[table], value)
    db._commit_revision = expected_version + 1
    if key:
        if not hasattr(db, "_commit_receipts"):
            db._commit_receipts = {}
        db._commit_receipts[key] = saved


def atomic(method: Any) -> Any:
    """Run a service method on staging stores; publish only on success."""

    @wraps(method)
    async def wrapped(self: Any, *args: Any, **kwargs: Any) -> Any:
        stores = {
            table: getattr(self, f"_{table}")
            for table in ("mind", "journal", "memory")
            if hasattr(getattr(self, f"_{table}", None), "_policy")
        }
        if not stores or any(isinstance(store, StagedStore) for store in stores.values()):
            return await method(self, *args, **kwargs)
        bound = inspect.signature(method).bind(self, *args, **kwargs)
        bound.apply_defaults()
        arguments = {
            k: v for k, v in bound.arguments.items() if k not in {"self", "idempotency_key"}
        }
        token = bound.arguments.get("idempotency_key")
        if token is not None and (not isinstance(token, str) or not 1 <= len(token) <= 128):
            raise ValueError("idempotency_key must contain 1 to 128 characters")
        key = (
            hashlib.sha256(f"{method.__qualname__}:{token}".encode()).hexdigest() if token else None
        )
        fingerprint = hashlib.sha256(
            json.dumps(document(arguments), sort_keys=True, default=str).encode()
        ).hexdigest()
        previous = await receipt(stores, key)
        if previous:
            if previous["fingerprint"] != fingerprint:
                raise CommitConflict("Idempotency key was already used for different input")
            return deepcopy(previous["result"])
        version = await revision(stores)
        staged = copy(self)
        operations: list = []
        for table, store in stores.items():
            setattr(staged, f"_{table}", StagedStore(store, table, operations))
        result = await method(staged, *args, **kwargs)
        saved = {"fingerprint": fingerprint, "result": document(result)}
        try:
            await commit(stores, operations, key, saved, version)
        except Exception:
            previous = await receipt(stores, key)
            if previous and previous["fingerprint"] == fingerprint:
                return deepcopy(previous["result"])
            raise
        return result

    return wrapped
