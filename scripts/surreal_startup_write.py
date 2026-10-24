"""Explicit, content-free runtime storage probe for the approved fresh target.

This reuses the application's stores and live tenancy probe, not the ordinary
storage initializer: that initializer performs out-of-scope legacy migration.
Only the existing probe writes, and its cleanup targets its generated scope.
No canonical Mind, account, model configuration or imported data is created.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping
from importlib.metadata import version
from typing import Any

from pydantic import ValidationError as ModelValidationError
from surrealdb import AsyncSurreal
from surrealdb.errors import ServerError

from aicognitive_mind.commit import CommitConflict
from aicognitive_mind.persistence import StorageBundle
from aicognitive_mind.surreal_preflight import TABLES, _count, _quiet_transport
from aicognitive_mind.surreal_storage import (
    SurrealDiagnosticStore,
    SurrealEvidenceStore,
    SurrealJournalStore,
    SurrealMemoryStore,
    SurrealMindStore,
)
from aicognitive_mind.tenancy import verify_live_tenancy


APP_SHA = "65157abe34b659b0da2c6c162fa51ee8fff5de6d"
HOST = "mir-ai-06gmqbgl1duq581garj3eabaq4.aws-use1.surreal.cloud"
URI = f"wss://{HOST}/rpc"
NAMESPACE = "mir_ai"
DATABASE = "ai_cognitive_mind"
USERNAME = "axiom_runtime"
MIND_ID = "axiom"


class CheckStopped(Exception):
    """Only fixed safe categories may be exposed to the caller."""


ERROR_KINDS = {
    "editor_database_role_unverified", "invalid_metadata", "unknown_tables_present",
    "unexpected_schema", "unexpected_table_schema", "target_nonempty",
    "tenancy_probe_failed", "post_probe_target_nonempty",
}


SERVER_KINDS = {
    "Validation", "Configuration", "Thrown", "Query", "Serialization",
    "NotAllowed", "NotFound", "AlreadyExists", "Connection", "Internal",
    "Parse", "InvalidRequest", "InvalidParams", "NamespaceEmpty", "DatabaseEmpty",
    "InvalidParameter", "InvalidContent", "InvalidMerge", "NotExecuted", "TimedOut",
    "Cancelled", "Deserialization", "Auth", "InvalidAuth", "InvalidPass", "InvalidRole",
    "TokenExpired", "SessionExpired", "Method", "Function", "Target", "Table",
    "Record", "Namespace", "Database", "Transaction", "Session",
}
RPC_CODES = {-32700, -32600, -32601, -32602, -32603, -32000, -32002}


def safe_error(error: Any) -> dict[str, Any]:
    """Copy only fixed categories/codes; never stringify errors or their values."""
    if isinstance(error, ServerError):
        source = {"kind": error.kind, "code": error.code, "details": error.details}
    elif isinstance(error, dict):
        source = error
    else:
        source = None
    if source is not None:
        result: dict[str, Any] = {"exception_category": "database_server"}
        kinds = []
        detail = source
        for _ in range(4):
            kind = detail.get("kind") if isinstance(detail, dict) else None
            if not isinstance(kind, str) or kind not in SERVER_KINDS:
                break
            kinds.append(kind)
            detail = detail.get("details")
        if kinds:
            result["server_kind"] = kinds
        code = source.get("code")
        if type(code) is int and code in RPC_CODES:
            result["error_code"] = code
        return result
    categories = (
        (ModelValidationError, "model_validation"), (CommitConflict, "commit_conflict"),
        (TimeoutError, "timeout"), (asyncio.CancelledError, "cancelled"),
        (KeyError, "response_key"), (IndexError, "response_index"),
        (TypeError, "python_type"), (ValueError, "python_value"),
        (OSError, "transport"), (RuntimeError, "runtime"),
    )
    for kind, category in categories:
        if isinstance(error, kind):
            return {"exception_category": category}
    return {"exception_category": "database_server_unstructured" if isinstance(error, str) else "unclassified"}


def _version(value: Any) -> str:
    if isinstance(value, str):
        match = re.fullmatch(r"(?:surrealdb[- ])?([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})(?:[-+][a-zA-Z0-9.]+)?", value)
        if match:
            return match[1]
    return "unrecognized"


class ProbeDatabase:
    """Observe existing probe calls without additional I/O or changed results."""

    def __init__(self, database: Any) -> None:
        self.database = database
        self.last_operation = "not_started"
        self.last_successful_operation: str | None = None
        self.first_failure: dict[str, Any] | None = None
        self.cleanup_failure: dict[str, Any] | None = None

    def _operation(self, method: str, target: Any, variables: Any = None) -> str:
        if method == "query_raw":
            return "initialize_probe_mind" if isinstance(target, str) and "CREATE ONLY $record" in target else "transaction"
        if method == "query" and isinstance(target, str):
            match = re.search(r"\bFROM ([a-z_]+)\b", target)
            table = match[1] if match and match[1] in TABLES else None
            if table:
                if target.startswith("DELETE FROM "):
                    return "cleanup_" + table
                scope = variables.get("mind_id") if isinstance(variables, dict) else None
                prefix = "probe_" if isinstance(scope, str) and scope.startswith("__tenancy_probe_") else "primary_" if scope == MIND_ID else ""
                return "read_" + prefix + table
        table = target if isinstance(target, str) and target in TABLES else getattr(target, "table_name", None)
        return ("read_" if method == "select" else "create_") + table if table in TABLES else method

    def _failure(self, operation: str, error: Any, index: int | None = None) -> None:
        failure = {"operation": operation, **safe_error(error)}
        if index is not None:
            failure["statement_index"] = index
        if self.first_failure is None:
            self.first_failure = failure
        if operation.startswith("cleanup_") and self.cleanup_failure is None:
            self.cleanup_failure = failure

    async def _call(self, method: str, target: Any, *args: Any) -> Any:
        operation = self._operation(method, target, args[0] if args else None)
        self.last_operation = operation
        try:
            result = await getattr(self.database, method)(target, *args)
        except BaseException as exc:
            self._failure(operation, exc)
            raise
        failed = False
        if method == "query_raw" and isinstance(result, dict):
            if "error" in result:
                self._failure(operation, result["error"])
                failed = True
            rows = result.get("result")
            if isinstance(rows, list):
                for index, row in enumerate(rows[:32]):
                    if isinstance(row, dict) and row.get("status") == "ERR":
                        self._failure(operation, row.get("result"), index)
                        failed = True
                        break
        if not failed:
            self.last_successful_operation = operation
        return result

    async def query(self, sql: str, variables: dict | None = None) -> Any:
        return await self._call("query", sql, variables) if variables is not None else await self._call("query", sql)

    async def query_raw(self, sql: str, variables: dict | None = None) -> Any:
        return await self._call("query_raw", sql, variables) if variables is not None else await self._call("query_raw", sql)

    async def select(self, record: Any) -> Any:
        return await self._call("select", record)

    async def create(self, record: Any, data: Any) -> Any:
        return await self._call("create", record, data)

    def snapshot(self) -> dict[str, Any]:
        return {
            "last_operation": self.last_operation,
            "last_successful_operation": self.last_successful_operation,
            "first_failure": self.first_failure,
            "cleanup_failure": self.cleanup_failure,
        }


def _editor_only(info: Any) -> bool:
    if not isinstance(info, dict) or not isinstance(info.get("users"), dict):
        return False
    definition = info["users"].get(USERNAME)
    if not isinstance(definition, str):
        return False
    # Discard quoted values, including hashes/comments, before finding roles.
    plain = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", "''", definition)
    if not re.match(rf"^DEFINE USER {USERNAME} ON DATABASE\b", plain, re.I):
        return False
    match = re.search(r"\bROLES\s+([A-Z,\s]+?)(?=\bDURATION\b|\bCOMMENT\b|;?\s*$)", plain, re.I)
    return bool(match and [role.strip().upper() for role in match[1].split(",")] == ["EDITOR"])


async def _inventory(db: Any) -> dict[str, int]:
    info = await db.query("INFO FOR DB;")
    if not _editor_only(info):
        raise CheckStopped("editor_database_role_unverified")
    if not isinstance(info.get("tables"), dict):
        raise CheckStopped("invalid_metadata")
    present = set(info["tables"])
    if present.difference(TABLES):
        raise CheckStopped("unknown_tables_present")
    for table, definition in info["tables"].items():
        if not isinstance(definition, str) or not re.fullmatch(
            rf"DEFINE TABLE (?:{table}|`{table}`)(?: TYPE ANY)? SCHEMALESS PERMISSIONS NONE;?",
            " ".join(definition.split()),
        ):
            raise CheckStopped("unexpected_table_schema")
    # An otherwise empty target with custom functions/configuration is not a
    # known fresh database. Do not execute writes that might trigger that code.
    if any(value for key, value in info.items() if key not in {"users", "tables"}):
        raise CheckStopped("unexpected_schema")
    del info
    counts = {table: 0 for table in TABLES}
    for table in TABLES:
        if table not in present:
            continue
        schema = await db.query(f"INFO FOR TABLE {table};")
        if not isinstance(schema, dict) or any(schema.values()):
            raise CheckStopped("unexpected_table_schema")
        counts[table] = _count(await db.query(f"SELECT count() AS total FROM {table} GROUP ALL;"))
    return counts


def _stores(db: Any) -> StorageBundle:
    # Runtime initialization is deliberately absent. These are exactly the
    # provider stores used by the pinned application on one SDK connection.
    return StorageBundle(
        mind_id=MIND_ID,
        runtime=db,
        mind=SurrealMindStore(db, MIND_ID),
        journal=SurrealJournalStore(db, MIND_ID),
        memory=SurrealMemoryStore(db, MIND_ID),
        diagnostics=SurrealDiagnosticStore(db, MIND_ID),
        evidence=SurrealEvidenceStore(db, MIND_ID),
    )


async def run_check(
    environ: Mapping[str, str] | None = None,
    *,
    database_factory: Any = AsyncSurreal,
    probe: Any = verify_live_tenancy,
    timeout_seconds: float = 90,
) -> dict[str, Any]:
    env = os.environ if environ is None else environ
    report: dict[str, Any] = {
        "application_sha": APP_SHA, "endpoint_host": HOST,
        "namespace": NAMESPACE, "database": DATABASE,
        "auth_scope": "database", "legacy_migration": "skipped",
        "status": "stopped", "stage": "configuration",
        "write_attempted": False, "cleanup": "not_started",
    }
    if env.get("AXIOM_STARTUP_APP_SHA") != APP_SHA:
        report["error_kind"] = "application_source_not_pinned"
        return report
    username = env.get("AXIOM_RUNTIME_SURREALDB_USERNAME", "")
    password = env.get("AXIOM_RUNTIME_SURREALDB_PASSWORD", "")
    if username != USERNAME or not password:
        report["error_kind"] = "missing_or_unapproved_runtime_credentials"
        return report

    db = None
    trace = None
    with _quiet_transport():
        try:
            async with asyncio.timeout(timeout_seconds):
                report["stage"] = "connection"
                db = database_factory(URI)
                await db.connect()
                report["stage"] = "authentication"
                # Explicit database scope; no root attempt, fallback or retry.
                await db.signin({
                    "namespace": NAMESPACE, "database": DATABASE,
                    "username": username, "password": password,
                })
                report["authenticated"] = True
                # Successful database-user signin establishes the existing
                # database before USE; this cannot bootstrap a missing target.
                await db.use(NAMESPACE, DATABASE)
                report["server_version"] = _version(await db.version())
                report["sdk_version"] = _version(version("surrealdb"))
                report["stage"] = "before_inventory"
                before = await _inventory(db)
                report["before_counts"] = before
                report["role"] = "EDITOR"
                if any(before.values()):
                    raise CheckStopped("target_nonempty")
                report.update(stage="tenancy_probe", write_attempted=True, cleanup="unverified")
                trace = ProbeDatabase(db)
                result = await probe(_stores(trace))
                if result.get("status") != "passed" or result.get("primary_initialized") is not False:
                    raise CheckStopped("tenancy_probe_failed")
                # Never report the probe's generated identifier or payloads.
                del result
                report["stage"] = "after_inventory"
                after = await _inventory(db)
                report["after_counts"] = after
                if any(after.values()):
                    report["cleanup"] = "records_remain"
                    raise CheckStopped("post_probe_target_nonempty")
                report.update(status="passed", stage="complete", cleanup="empty")
        except CheckStopped as exc:
            kind = exc.args[0] if exc.args else None
            report["error_kind"] = kind if isinstance(kind, str) and kind in ERROR_KINDS else "operation_failed"
        except TimeoutError:
            report["error_kind"] = "timeout"
            report["exception"] = {"exception_category": "timeout"}
        except Exception as exc:
            # SDK exceptions can include credentials, query values or payloads.
            report["error_kind"] = "operation_failed"
            report["exception"] = safe_error(exc)
            prior = exc.__context__
            if isinstance(prior, BaseException) and prior is not exc:
                # A finally/cleanup exception can mask a model/parser failure.
                # Classify that context without exposing its message or values.
                report["prior_exception"] = safe_error(prior)
        finally:
            if trace is not None:
                report["probe_diagnostics"] = trace.snapshot()
            if db is not None:
                if report["write_attempted"] and report["cleanup"] == "unverified":
                    try:
                        async with asyncio.timeout(15):
                            after = await _inventory(db)
                            report["after_counts"] = after
                            report["cleanup"] = "records_remain" if any(after.values()) else "empty"
                    except Exception:
                        report["cleanup"] = "unverified"
                try:
                    async with asyncio.timeout(10):
                        await db.close()
                except Exception:
                    report.update(status="stopped", stage="close", error_kind="close_failed")
    return report


def main() -> None:
    report = asyncio.run(run_check())
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
