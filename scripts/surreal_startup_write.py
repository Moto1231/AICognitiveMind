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
from typing import Any

from surrealdb import AsyncSurreal

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
                await db.version()
                report["stage"] = "before_inventory"
                before = await _inventory(db)
                report["before_counts"] = before
                report["role"] = "EDITOR"
                if any(before.values()):
                    raise CheckStopped("target_nonempty")
                report.update(stage="tenancy_probe", write_attempted=True, cleanup="unverified")
                result = await probe(_stores(db))
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
            report["error_kind"] = exc.args[0] if exc.args and exc.args[0] in ERROR_KINDS else "operation_failed"
        except TimeoutError:
            report["error_kind"] = "timeout"
        except Exception:
            # SDK exceptions can include credentials, query values or payloads.
            report["error_kind"] = "operation_failed"
        finally:
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
