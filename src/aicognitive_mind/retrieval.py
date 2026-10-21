"""Bounded database-side candidate retrieval and provider-neutral counts."""

import time
from typing import Any

from aicognitive_mind.commit import surreal_query
from aicognitive_mind.timing import emit


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
        if key in {"kind", "memory_class", "mind_id"}:
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


def _included_in_count(value: Any, exclude_checkpoint_type: str | None) -> bool:
    return not (
        exclude_checkpoint_type is not None
        and getattr(value, "kind", None) == "checkpoint"
        and value.experience.get("checkpoint_type") == exclude_checkpoint_type
    )


async def count(store: Any, *, exclude_checkpoint_type: str | None = None) -> int:
    from aicognitive_mind.commit import StagedStore

    if isinstance(store, StagedStore):
        total = await count(store.base, exclude_checkpoint_type=exclude_checkpoint_type)
        for table, operation, before, after in store.operations:
            if table != store.table:
                continue
            if operation == "replace":
                total -= int(_included_in_count(before, exclude_checkpoint_type))
            total += int(_included_in_count(after, exclude_checkpoint_type))
        return total
    if hasattr(store, "_collection"):
        query = (
            {"mind_id": store.mind_id}
            if getattr(store, "mind_id", None) is not None
            else {}
        )
        if exclude_checkpoint_type is not None:
            query["$nor"] = [
                {"kind": "checkpoint", "experience.checkpoint_type": exclude_checkpoint_type}
            ]
        return await store._collection.count_documents(query)
    if hasattr(store, "_database"):
        table = "journal" if "Journal" in type(store).__name__ else "memory"
        clauses, variables = [], {}
        if getattr(store, "mind_id", None) is not None:
            clauses.append("mind_id = $mind_id")
            variables["mind_id"] = store.mind_id
        if exclude_checkpoint_type is not None:
            clauses.append(
                "(kind != $checkpoint_kind OR experience.checkpoint_type = NONE "
                "OR experience.checkpoint_type != $checkpoint_type)"
            )
            variables.update(checkpoint_kind="checkpoint", checkpoint_type=exclude_checkpoint_type)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        result = await store._database.query(
            f"SELECT count() AS total FROM {table}{where} GROUP ALL;",
            variables,
        )
        return result[0]["total"] if result else 0
    if hasattr(store, "_entries"):
        if exclude_checkpoint_type is None:
            return len(store._entries)
        return sum(_included_in_count(entry, exclude_checkpoint_type) for entry in store._entries)
    if hasattr(store, "_memories"):
        return len(store._memories)
    return sum(_included_in_count(value, exclude_checkpoint_type) for value in await store.read())


async def candidates(store: Any, tokens: set[str], limit: int = 256) -> list:
    """Retrieve recall candidates, logging how long each retrieval takes."""
    base = getattr(store, "base", store)
    table = "journal" if "Journal" in type(base).__name__ else "memory"
    started = time.perf_counter()
    rows = await _candidates(store, tokens, limit)
    emit(
        "timing candidates table=%s tokens=%d limit=%d rows=%d total=%.3fs",
        table,
        len(tokens),
        limit,
        len(rows),
        time.perf_counter() - started,
    )
    return rows


async def _candidates(store: Any, tokens: set[str], limit: int = 256) -> list:
    # Staging delegates reads to its base; include pending changes in working-memory
    # comparisons separately, while recall describes committed history.
    base = getattr(store, "base", store)
    table = "journal" if "Journal" in type(base).__name__ else "memory"
    from aicognitive_mind.domain import DurableMemory, JournalEntry

    model = JournalEntry if table == "journal" else DurableMemory
    date = "occurred_at" if table == "journal" else "formed_at"
    words = sorted(tokens)[:64]
    if hasattr(base, "_collection"):
        return await base.query_candidates(set(words), limit=limit)
    if hasattr(base, "_database"):
        from aicognitive_mind.surreal_storage import _document

        field = (
            "experience"
            if table == "journal"
            else "[content, associations, grounding, artifacts]"
        )
        search_clauses = [
            f"string::contains(string::lowercase(<string>{field}), $word{i})"
            for i in range(len(words))
        ]
        variables = {f"word{i}": word for i, word in enumerate(words)}
        scope = ""
        if getattr(base, "mind_id", None) is not None:
            variables["mind_id"] = base.mind_id
            scope = "mind_id = $mind_id"
        search = " OR ".join(search_clauses)
        clauses = [
            value
            for value in (
                scope,
                f"({search})" if search else "",
            )
            if value
        ]
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        queried = time.perf_counter()
        rows = await base._database.query(
            f"SELECT * FROM {table}{where} "
            f"ORDER BY {date} DESC, id ASC LIMIT {limit};",
            variables,
        )
        query_seconds = time.perf_counter() - queried
        fell_back = False
        if not rows:
            fell_back = True
            fallback_where = f" WHERE {scope}" if scope else ""
            rows = await base._database.query(
                f"SELECT * FROM {table}{fallback_where} "
                f"ORDER BY {date} DESC, id ASC LIMIT {limit};",
                {"mind_id": base.mind_id} if scope else {},
            )
        query_seconds = time.perf_counter() - queried
        validated = time.perf_counter()
        result = [model.model_validate(_document(row)) for row in rows]
        emit(
            "timing candidates.surreal table=%s tokens=%d db=%.3fs validate=%.3fs rows=%d fallback=%s",
            table,
            len(words),
            query_seconds,
            time.perf_counter() - validated,
            len(rows),
            fell_back,
        )
        return result
    return await store.read()
