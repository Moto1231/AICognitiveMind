"""Content-free, read-only inspection of an existing remote Surreal database.

This deliberately does not use SurrealRuntime or the RPC ``use`` method. On
some server versions USE can create missing namespaces/databases. HTTP headers
select the existing target; database-scoped sign-in and read queries must fail
if that target does not exist. No schema or application initialization runs.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Iterator
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from aicognitive_mind.config import Settings


TABLES = (
    "mind", "journal", "memory", "diagnostics", "evidence", "runtime_records",
    "commit_state", "commit_receipts",
)
MAX_RESPONSE_BYTES = 1_048_576
REQUEST_TIMEOUT_SECONDS = 10.0
PREFLIGHT_TIMEOUT_SECONDS = 60.0
INFO_QUERY = "INFO FOR DB;"
DUPLICATE_MIND_QUERY = (
    "SELECT count() AS total FROM "
    "(SELECT mind_id, count() AS copies FROM mind "
    "WHERE mind_id != NONE AND mind_id != NULL GROUP BY mind_id) "
    "WHERE copies > 1 GROUP ALL;"
)
ACCOUNT_FILTER = (
    "(kind = 'account' OR string::starts_with(key ?? '', 'account_') "
    "OR string::contains(type::string(id), 'account_'))"
)
ACCOUNT_QUERIES = {
    "rows": f"SELECT count() AS total FROM runtime_records WHERE {ACCOUNT_FILTER} GROUP ALL;",
    "missing_mind_mapping": (
        f"SELECT count() AS total FROM runtime_records WHERE {ACCOUNT_FILTER} "
        "AND string::trim(mind_id ?? '') = '' GROUP ALL;"
    ),
    "legacy_missing_key": (
        f"SELECT count() AS total FROM runtime_records WHERE {ACCOUNT_FILTER} "
        "AND (key = NONE OR key = NULL) GROUP ALL;"
    ),
    "duplicate_global_keys": (
        "SELECT count() AS total FROM "
        "(SELECT key, count() AS copies FROM runtime_records "
        f"WHERE {ACCOUNT_FILTER} AND key != NONE AND key != NULL GROUP BY key) "
        "WHERE copies > 1 GROUP ALL;"
    ),
}


def count_queries(table: str) -> tuple[str, str, str]:
    """Only fixed application table names can enter the read-only SQL."""
    if table not in TABLES:
        raise ValueError("Unsupported preflight table")
    return (
        f"SELECT count() AS total FROM {table} GROUP ALL;",
        "SELECT count() AS total FROM "
        f"(SELECT mind_id FROM {table} "
        "WHERE mind_id != NONE AND mind_id != NULL GROUP BY mind_id) GROUP ALL;",
        f"SELECT count() AS total FROM {table} "
        "WHERE mind_id = NONE OR mind_id = NULL GROUP ALL;",
    )


class PreflightError(Exception):
    """Contains only a fixed, content-free failure category."""


class _DiscardOutput:
    def write(self, value: str) -> int:
        return len(value)

    def flush(self) -> None:
        pass


@contextlib.contextmanager
def _quiet_transport() -> Iterator[None]:
    # This is a standalone diagnostic command, not a service request handler.
    # Client/debug output and raw exception messages must never reach its logs.
    previous_disable = logging.root.manager.disable
    sink = _DiscardOutput()
    logging.disable(logging.CRITICAL)
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            yield
    finally:
        logging.disable(previous_disable)


def _endpoint(settings: Settings) -> tuple[str, str]:
    try:
        uri = urlsplit(settings.surrealdb_uri)
        port = uri.port
        host = uri.hostname
    except ValueError:
        raise PreflightError("invalid_configuration") from None
    if (
        uri.scheme not in {"wss", "https"}
        or not host
        or uri.username is not None
        or uri.password is not None
        or uri.query
        or uri.fragment
    ):
        raise PreflightError("invalid_configuration")
    # Preserve the configured origin and reverse-proxy prefix. No redirects,
    # alternative origins, certificate overrides or network retries are used.
    path = uri.path.rstrip("/")
    if not path.endswith("/rpc"):
        path += "/rpc"
    authority = f"[{host}]" if ":" in host else host
    if port is not None:
        authority += f":{port}"
    return host, urlunsplit(("https", authority, path, "", ""))


async def _rpc(
    client: Any, endpoint: str, headers: dict[str, str], method: str, params: list[Any],
) -> Any:
    async with client.stream(
        "POST", endpoint, headers=headers,
        json={"id": "surreal-preflight", "method": method, "params": params},
    ) as response:
        if response.status_code != 200:
            # Never include response bodies, URLs, headers or exception strings.
            if response.status_code in {401, 403}:
                raise PreflightError(f"http_{response.status_code}")
            raise PreflightError("http_error")
        body = bytearray()
        async for chunk in response.aiter_bytes():
            if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                raise PreflightError("response_too_large")
            body.extend(chunk)
        result = json.loads(body)
    if not isinstance(result, dict) or "error" in result or "result" not in result:
        raise PreflightError("rpc_error")
    return result["result"]


async def _query(client: Any, endpoint: str, headers: dict[str, str], sql: str) -> Any:
    statements = await _rpc(client, endpoint, headers, "query", [sql, {}])
    if (
        not isinstance(statements, list)
        or len(statements) != 1
        or not isinstance(statements[0], dict)
        or statements[0].get("status") != "OK"
        or "result" not in statements[0]
    ):
        raise PreflightError("query_failed")
    return statements[0]["result"]


def _count(value: Any) -> int:
    if value == []:
        return 0
    if isinstance(value, list) and len(value) == 1 and isinstance(value[0], dict):
        count = value[0].get("total")
        if type(count) is int and count >= 0:
            return count
    raise PreflightError("invalid_count_response")


async def preflight(
    settings: Settings,
    *,
    client_factory: Any = httpx.AsyncClient,
    timeout_seconds: float = PREFLIGHT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Return only target identity, outcomes, aggregate counts and conflict flags."""
    report: dict[str, Any] = {
        "endpoint_host": None,
        "namespace": settings.surrealdb_namespace,
        "database": settings.surrealdb_database,
        "connection": "error",
        "stage": "configuration",
    }
    try:
        host, endpoint = _endpoint(settings)
        report["endpoint_host"] = host
        if settings.surrealdb_auth_level != "database":
            raise PreflightError("database_scoped_auth_required")
        if not settings.surrealdb_username or not settings.surrealdb_password:
            report["connection"] = "not_configured"
            raise PreflightError("missing_credentials")
        if not settings.surrealdb_namespace or not settings.surrealdb_database:
            raise PreflightError("invalid_configuration")
        headers = {
            "Accept": "application/json", "Content-Type": "application/json",
            "Surreal-NS": settings.surrealdb_namespace,
            "Surreal-DB": settings.surrealdb_database,
        }
        with _quiet_transport():
            async with asyncio.timeout(timeout_seconds):
                async with client_factory(
                    timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False, trust_env=False,
                ) as client:
                    report["stage"] = "authentication"
                    token = await _rpc(client, endpoint, headers, "signin", [{
                        "NS": settings.surrealdb_namespace,
                        "DB": settings.surrealdb_database,
                        "user": settings.surrealdb_username,
                        "pass": settings.surrealdb_password,
                    }])
                    if isinstance(token, dict):
                        token = token.get("access")
                    if not isinstance(token, str) or not token:
                        raise PreflightError("invalid_auth_response")
                    headers["Authorization"] = f"Bearer {token}"
                    report["stage"] = "metadata"
                    info = await _query(client, endpoint, headers, INFO_QUERY)
                    if not isinstance(info, dict) or not isinstance(info.get("tables"), dict):
                        raise PreflightError("invalid_metadata_response")
                    table_names = set(info["tables"])
                    # INFO may include arbitrary schema/credential definitions.
                    # Retain only membership of known table names and a count.
                    other_tables = len(table_names.difference(TABLES))
                    present = table_names.intersection(TABLES)
                    del info, table_names
                    report["stage"] = "counts"
                    tables = {}
                    for table in TABLES:
                        values = [0, 0, 0]
                        if table in present:
                            values = [
                                _count(await _query(client, endpoint, headers, sql))
                                for sql in count_queries(table)
                            ]
                        tables[table] = dict(
                            exists=table in present, rows=values[0],
                            tenant_count=values[1], unscoped_rows=values[2],
                        )
                    duplicates = 0
                    if "mind" in present:
                        duplicates = _count(await _query(
                            client, endpoint, headers, DUPLICATE_MIND_QUERY,
                        ))
                    accounts = {name: 0 for name in ACCOUNT_QUERIES}
                    if "runtime_records" in present:
                        accounts = {
                            name: _count(await _query(client, endpoint, headers, sql))
                            for name, sql in ACCOUNT_QUERIES.items()
                        }
                    summary = dict(
                        connection="ok", stage="complete", tables=tables,
                        account_lookup_counts=accounts,
                        other_table_count=other_tables,
                        conflicts={
                            "target_nonempty": any(t["rows"] for t in tables.values()),
                            "unscoped_rows": sum(t["unscoped_rows"] for t in tables.values()),
                            "duplicate_mind_scopes": duplicates,
                            "unknown_tables_present": bool(other_tables),
                            "account_lookup_review_required": any(
                                accounts[name] for name in (
                                    "missing_mind_mapping", "legacy_missing_key",
                                    "duplicate_global_keys",
                                )
                            ),
                            "source_not_compared": True,
                        },
                    )
        report.update(summary)
    except PreflightError as exc:
        report["error_kind"] = exc.args[0]
    except (TimeoutError, httpx.TimeoutException):
        report["error_kind"] = "timeout"
    except httpx.TransportError:
        report["error_kind"] = "transport_error"
    except Exception:
        report["error_kind"] = "request_failed"
    return report
