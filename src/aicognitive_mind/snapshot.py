"""A bounded, consistent cognitive snapshot for portable backups."""

from typing import Any

from aicognitive_mind.commit import backend, surreal_query
from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
)

MODELS = {
    "mind": CognitiveMind,
    "journal": JournalEntry,
    "memory": DurableMemory,
    "diagnostics": DiagnosticObservation,
}
MAX_SNAPSHOT_BYTES = 32 * 1024 * 1024
MAX_SNAPSHOT_ROWS = 20000


async def cognitive_snapshot(mind: Any, journal: Any, memory: Any, diagnostics: Any) -> dict:
    kind, db = backend({"mind": mind})
    if kind == "surreal":
        variables = {"max_rows": MAX_SNAPSHOT_ROWS, "max_bytes": MAX_SNAPSHOT_BYTES}
        statements = ["BEGIN TRANSACTION;"]
        for table in MODELS:
            statements += [
                f"LET $size_{table} = SELECT count() AS rows, math::sum(string::len(<string>$this)) AS bytes FROM {table} GROUP ALL;",
                f"IF ($size_{table}[0].rows ?? 0) > $max_rows OR ($size_{table}[0].bytes ?? 0) > $max_bytes / 4 {{ THROW 'Portable snapshot limit exceeded; use native database backup'; }};",
            ]
        statements += [f"SELECT * FROM {table};" for table in MODELS]
        statements.append("COMMIT TRANSACTION;")
        results = await surreal_query(db, "\n".join(statements), variables)
        rows = results[-4:]  # BEGIN/COMMIT do not produce result rows.
        raw = dict(zip(MODELS, rows, strict=True))
    elif kind == "mongo":
        from pymongo.read_concern import ReadConcern

        mind_id = str(getattr(mind, "mind_id", "root"))
        raw = {}
        async with db.client.start_session() as session:
            async with await session.start_transaction(read_concern=ReadConcern("snapshot")):
                for table in MODELS:
                    cursor = await db[table].aggregate(
                        [
                            {"$match": {"mind_id": mind_id}},
                            {
                                "$group": {
                                    "_id": None,
                                    "rows": {"$sum": 1},
                                    "bytes": {"$sum": {"$bsonSize": "$$ROOT"}},
                                }
                            }
                        ],
                        session=session,
                    )
                    sizes = await cursor.to_list()
                    if sizes and (
                        sizes[0]["rows"] > MAX_SNAPSHOT_ROWS
                        or sizes[0]["bytes"] > MAX_SNAPSHOT_BYTES // 4
                    ):
                        raise RuntimeError(
                            "Portable snapshot limit exceeded; use native database backup"
                        )
                    raw[table] = await db[table].find(
                        {"mind_id": mind_id},
                        session=session,
                    ).to_list()
    else:
        # In-memory test stores have no internal awaits during reads.
        return {
            "mind": await mind.load(),
            "journal": await journal.read(),
            "memory": await memory.read(),
            "diagnostics": await diagnostics.read(),
        }
    result = {
        table: [
            model.model_validate(
                {
                    k: v
                    for k, v in row.items()
                    if k not in {"id", "_id", "mind_id"}
                }
            )
            for row in raw[table]
        ]
        for table, model in MODELS.items()
    }
    if len(result["mind"]) > 1:
        raise RuntimeError("Snapshot contains more than one Mind")
    result["mind"] = result["mind"][0] if result["mind"] else None
    return result
