"""Default application tables required before reads on SurrealDB 3.x."""

from __future__ import annotations

from typing import Any


APPLICATION_TABLES = (
    "mind", "journal", "memory", "diagnostics", "evidence", "runtime_records",
    "commit_state", "commit_receipts",
)


async def bootstrap_tables(database: Any) -> None:
    """Create missing tables only; retain every existing definition and record."""
    for table in APPLICATION_TABLES:
        # One checked statement per call avoids SDK query() checking only the
        # first result of a multi-statement response. No OVERWRITE or data DML.
        await database.query(
            f"DEFINE TABLE IF NOT EXISTS {table} SCHEMALESS PERMISSIONS NONE;"
        )
