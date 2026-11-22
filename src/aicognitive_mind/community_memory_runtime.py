"""Opt-in Community Memory integration for explicitly configured staging.

The staging source is the built-in synthetic catalog, not an Axiom journal.
The separately scoped SQLite database contains only memberships, opt-in and
published catalog references. Local private inputs and keys never cross this
handoff; the application accepts only a scoped receipt and fixed catalog ID.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import re
import secrets
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from aicognitive_mind.community_memory import (
    CommunityDraft,
    CommunityGrant,
    CommunityPrincipal,
    SyntheticLesson,
)


_RECEIPT_TTL_SECONDS = 300
_RECEIPT_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")

_RECALL_STOPWORDS = frozenset({
    "about", "after", "before", "each", "from", "have", "that", "their", "these",
    "this", "what", "where", "which", "with", "would", "your",
})


class StagedCommunityStore:
    """Isolated staging database; every read/write rechecks current participation."""

    def __init__(self, db_path: Path, group: str, eligible_minds: frozenset[str]) -> None:
        self.path = db_path
        self.group = group
        self.eligible_minds = eligible_minds
        fd = os.open(db_path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        with self._access(write=True) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS community_opt_in (
                account_id TEXT NOT NULL, mind_id TEXT NOT NULL,
                enabled INTEGER NOT NULL, epoch INTEGER NOT NULL,
                PRIMARY KEY(account_id, mind_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS community_lesson (
                account_id TEXT NOT NULL, mind_id TEXT NOT NULL, group_id TEXT NOT NULL,
                lesson_id TEXT NOT NULL, opt_in_epoch INTEGER NOT NULL,
                PRIMARY KEY(account_id, mind_id, group_id, lesson_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS community_handoff (
                token_hash TEXT PRIMARY KEY, account_id TEXT NOT NULL, mind_id TEXT NOT NULL,
                group_id TEXT NOT NULL, epoch INTEGER NOT NULL, expires_at REAL NOT NULL)""")
            db.execute("""CREATE INDEX IF NOT EXISTS community_handoff_principal
                ON community_handoff (account_id, mind_id, group_id)""")

    @contextmanager
    def _access(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=0.2)
        try:
            db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _preference(db: sqlite3.Connection, principal: CommunityPrincipal) -> tuple[bool, int]:
        row = db.execute(
            "SELECT enabled, epoch FROM community_opt_in WHERE account_id=? AND mind_id=?",
            (principal.account_id, principal.mind_id),
        ).fetchone()
        return (row[0] == 1, int(row[1])) if row is not None else (False, 0)

    def _eligible(self, principal: CommunityPrincipal, group: str) -> bool:
        return group == self.group and principal.mind_id in self.eligible_minds

    async def opted_in(self, principal: CommunityPrincipal) -> bool:
        def read() -> bool:
            with self._access() as db:
                return self._preference(db, principal)[0]

        return await asyncio.to_thread(read)

    async def set_opt_in(self, principal: CommunityPrincipal, enabled: bool) -> bool:
        if enabled and not self._eligible(principal, self.group):
            raise ValueError("This Mind is not eligible for the configured community.")

        def write() -> bool:
            with self._access(write=True) as db:
                old_enabled, epoch = self._preference(db, principal)
                if enabled != old_enabled:
                    db.execute(
                        "INSERT INTO community_opt_in VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(account_id, mind_id) DO UPDATE "
                        "SET enabled=excluded.enabled, epoch=excluded.epoch",
                        (principal.account_id, principal.mind_id, enabled, epoch + 1),
                    )
                if not enabled:
                    db.execute(
                        "DELETE FROM community_lesson WHERE account_id=? AND mind_id=?",
                        (principal.account_id, principal.mind_id),
                    )
                    db.execute(
                        "DELETE FROM community_handoff WHERE account_id=? AND mind_id=?",
                        (principal.account_id, principal.mind_id),
                    )
                return enabled

        return await asyncio.to_thread(write)

    def _grant(
        self, db: sqlite3.Connection, principal: CommunityPrincipal, group: str,
    ) -> CommunityGrant | None:
        if not self._eligible(principal, group):
            return None
        enabled, epoch = self._preference(db, principal)
        return CommunityGrant(principal, group, epoch, 0) if enabled else None

    @staticmethod
    def _receipt_hash(receipt: str) -> str:
        return hashlib.sha256(receipt.encode("ascii")).hexdigest()

    async def issue_handoff(self, principal: CommunityPrincipal) -> str | None:
        # Called only by the successful personal-sleep path; the caller does not
        # supply title, receipt issuer, account, group, or any private content.
        token = secrets.token_urlsafe(32)

        def write() -> str | None:
            now = time.time()
            with self._access(write=True) as db:
                grant = self._grant(db, principal, self.group)
                if grant is None:
                    return None
                db.execute("DELETE FROM community_handoff WHERE expires_at <= ?", (now,))
                db.execute(
                    "DELETE FROM community_handoff WHERE account_id=? AND mind_id=? AND group_id=?",
                    (principal.account_id, principal.mind_id, self.group),
                )
                db.execute(
                    "INSERT INTO community_handoff VALUES (?, ?, ?, ?, ?, ?)",
                    (self._receipt_hash(token), principal.account_id, principal.mind_id,
                     self.group, grant.opt_in_epoch, now + _RECEIPT_TTL_SECONDS),
                )
                return token

        return await asyncio.to_thread(write)

    async def submit_handoff(
        self, principal: CommunityPrincipal, receipt: str, lesson: SyntheticLesson,
    ) -> bool | None:
        if type(lesson) is not SyntheticLesson or not _RECEIPT_PATTERN.fullmatch(receipt):
            return None
        token_hash = self._receipt_hash(receipt)

        def write() -> bool | None:
            with self._access(write=True) as db:
                grant = self._grant(db, principal, self.group)
                if grant is None:
                    return None
                # Redemption and publication share one transaction. A receipt
                # from another principal, group, or prior opt-in cannot be used.
                consumed = db.execute(
                    "DELETE FROM community_handoff WHERE token_hash=? AND account_id=? "
                    "AND mind_id=? AND group_id=? AND epoch=? AND expires_at>?",
                    (token_hash, principal.account_id, principal.mind_id, self.group,
                     grant.opt_in_epoch, time.time()),
                ).rowcount
                if consumed != 1:
                    return None
                return db.execute(
                    "INSERT OR IGNORE INTO community_lesson VALUES (?, ?, ?, ?, ?)",
                    (principal.account_id, principal.mind_id, self.group, lesson.value,
                     grant.opt_in_epoch),
                ).rowcount == 1

        return await asyncio.to_thread(write)

    async def recall_ids(
        self, principal: CommunityPrincipal, group: str,
    ) -> tuple[SyntheticLesson, ...]:
        def read() -> tuple[SyntheticLesson, ...]:
            with self._access() as db:
                if self._grant(db, principal, group) is None:
                    return ()
                rows = db.execute(
                    "SELECT lesson_id, l.mind_id FROM community_lesson l "
                    "JOIN community_opt_in p ON p.account_id=l.account_id AND p.mind_id=l.mind_id "
                    "WHERE group_id=? AND p.enabled=1 AND p.epoch=l.opt_in_epoch "
                    "ORDER BY lesson_id",
                    (group,),
                ).fetchall()
                return tuple(dict.fromkeys(
                    SyntheticLesson(lesson) for lesson, owner in rows
                    if owner in self.eligible_minds and lesson in SyntheticLesson._value2member_map_
                ))

        return await asyncio.to_thread(read)

    async def recall(
        self, principal: CommunityPrincipal, group: str,
    ) -> tuple[CommunityDraft, ...]:
        from aicognitive_mind.community_memory import synthetic_community_draft

        return tuple(synthetic_community_draft(lesson) for lesson in await self.recall_ids(
            principal, group,
        ))


class CommunityMemoryRuntime:
    """Bind the existing MCP lifecycle to the explicitly enabled staged store."""

    def __init__(self, store: StagedCommunityStore) -> None:
        self.store = store

    async def status(self, principal: CommunityPrincipal) -> dict[str, bool]:
        available = principal.mind_id in self.store.eligible_minds
        return {"available": available, "opted_in": available and await self.store.opted_in(principal)}

    async def set_opt_in(self, principal: CommunityPrincipal, enabled: bool) -> dict[str, bool]:
        await self.store.set_opt_in(principal, enabled)
        return await self.status(principal)

    async def after_personal_sleep(self, principal: CommunityPrincipal) -> str | None:
        return await self.store.issue_handoff(principal)

    async def submit(
        self, principal: CommunityPrincipal, receipt: str, lesson: SyntheticLesson,
    ) -> bool | None:
        return await self.store.submit_handoff(principal, receipt, lesson)

    async def recall(
        self, principal: CommunityPrincipal, focus: str,
    ) -> list[dict[str, str]]:
        words = set(re.findall(r"[a-z]{4,}", focus.casefold())) - _RECALL_STOPWORDS
        if not words:
            return []
        drafts = await self.store.recall(principal, self.store.group)
        matches = [
            {"lesson_id": item.lesson.value, "title": item.title, "guidance": item.guidance}
            for item in drafts
            if words.intersection(re.findall(
                r"[a-z]{4,}", f"{item.title} {item.guidance}".casefold(),
            ))
        ]
        return matches[:4]


def configure_community_runtime(
    db_path: str | None, group: str, allowed_minds: str,
) -> CommunityMemoryRuntime | None:
    if not db_path:
        return None
    path = Path(db_path)
    minds = frozenset(part.strip() for part in allowed_minds.split(",") if part.strip())
    if not path.is_absolute() or not minds or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", group):
        raise ValueError("Community Memory needs an absolute path, valid group and Mind allowlist.")
    if not all(re.fullmatch(r"[A-Za-z0-9_-]{1,128}", mind) for mind in minds):
        raise ValueError("Community Memory Mind selectors must be normalized.")
    return CommunityMemoryRuntime(StagedCommunityStore(path, group, minds))
