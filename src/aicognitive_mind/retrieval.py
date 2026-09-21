"""Bounded database-side candidate retrieval and provider-neutral counts."""

from typing import Any

from aicognitive_mind.commit import surreal_query


def json_time(value: Any) -> Any:
    return value.isoformat().replace("+00:00", "Z") if hasattr(value, "isoformat") else value


async def surreal_page(
    db: Any,
    table: str,
    model: Any,
    *,
    offset: int,
    limit: int,
    newest_first: bool,
    search: str | None = None,
    **filters: Any,
) -> tuple[list, int]:
    from aicognitive_mind.surreal_storage import _document

    date = "occurred_at" if table == "journal" else "formed_at"
    clauses, variables = [], {"offset": max(0, offset), "limit": max(0, min(limit, 1000))}
    for key, value in filters.items():
        if value is None:
            continue
        variables[key] = json_time(value)
        if key in {"kind", "memory_class"}:
            clauses.append(f"{key} = ${key}")
        elif key.endswith("_from"):
            clauses.append(f"{date} >= ${key}")
        elif key.endswith("_to"):
            clauses.append(f"{date} <= ${key}")
        elif key in {"association", "grounding"}:
            field = "associations" if key == "association" else key
            variables[key] = value.lower()
            clauses.append(f"string::contains(string::lowercase(<string>{field}), ${key})")
    if search:
        variables["search"] = search.lower()
        field = (
            "experience" if table == "journal" else "[content, associations, grounding, artifacts]"
        )
        clauses.append(f"string::contains(string::lowercase(<string>{field}), $search)")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    direction = "DESC" if newest_first else "ASC"
    results = await surreal_query(
        db,
        f"BEGIN TRANSACTION; SELECT * FROM {table}{where} ORDER BY {date} {direction}, id ASC LIMIT $limit START $offset; "
        f"SELECT count() AS total FROM {table}{where} GROUP ALL; COMMIT TRANSACTION;",
        variables,
    )
    pages = [item for item in results if isinstance(item, list)]
    rows, counts = pages[0], pages[1]
    return [model.model_validate(_document(row)) for row in rows], counts[0][
        "total"
    ] if counts else 0


async def count(store: Any) -> int:
    if hasattr(store, "_collection"):
        return await store._collection.count_documents({})
    if hasattr(store, "_database"):
        table = "journal" if "Journal" in type(store).__name__ else "memory"
        result = await store._database.query(f"SELECT count() AS total FROM {table} GROUP ALL;")
        return result[0]["total"] if result else 0
    return len(await store.read())


async def candidates(store: Any, tokens: set[str], limit: int = 256) -> list:
    # Staging delegates reads to its base; include pending changes in working-memory
    # comparisons separately, while recall describes committed history.
    base = getattr(store, "base", store)
    table = "journal" if "Journal" in type(base).__name__ else "memory"
    from aicognitive_mind.domain import DurableMemory, JournalEntry

    model = JournalEntry if table == "journal" else DurableMemory
    date = "occurred_at" if table == "journal" else "formed_at"
    words = sorted(tokens)[:64]
    if hasattr(base, "_collection"):
        query = {"$or": [base._portal_filter(search=word) for word in words]} if words else {}
        cursor = base._collection.find(query, {"_id": 0}).sort(date, -1).limit(limit)
        matches = [model.model_validate(row) async for row in cursor]
        if not matches:
            matches, _ = await base.query_page(offset=0, limit=limit, newest_first=True)
        return matches
    if hasattr(base, "_database"):
        from aicognitive_mind.surreal_storage import _document

        field = (
            "experience" if table == "journal" else "[content, associations, grounding, artifacts]"
        )
        clauses = [
            f"string::contains(string::lowercase(<string>{field}), $word{i})"
            for i in range(len(words))
        ]
        where = " WHERE " + " OR ".join(clauses) if clauses else ""
        variables = {f"word{i}": word for i, word in enumerate(words)}
        rows = await base._database.query(
            f"SELECT * FROM {table}{where} ORDER BY {date} DESC, id ASC LIMIT {limit};", variables
        )
        if not rows:
            rows = await base._database.query(
                f"SELECT * FROM {table} ORDER BY {date} DESC, id ASC LIMIT {limit};"
            )
        return [model.model_validate(_document(row)) for row in rows]
    return await store.read()
