from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from aicognitive_mind.domain import CognitiveMind, MindIdentity
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.config import Settings
from aicognitive_mind.commit import CommitConflict


logger = logging.getLogger("aicognitive_mind.auth_diagnostics")


@dataclass(frozen=True)
class Account:
    username: str
    mind_id: str


class AccountService:
    """Operational account registry. Accounts select Minds; they are not cognitive memory."""

    def __init__(self, settings: Settings, registry_store: Any) -> None:
        self.settings = settings
        self.registry_store = registry_store

    @staticmethod
    def _password_hash(password: str, salt: bytes | None = None) -> tuple[str, str]:
        salt = salt or secrets.token_bytes(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310_000)
        return salt.hex(), digest.hex()

    async def resolve_subject(self, subject: str) -> Account | None:
        """Resolve a verified OAuth/session subject, never an arbitrary tenant selector.

        A live, unique account must still own the subject. This does not create
        or initialize a Mind, and does not authenticate a supplied password.
        """
        if not isinstance(subject, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", subject):
            return None
        candidates = await self.registry_store.account_subject_records(subject)
        if len(candidates) > 1:
            raise CommitConflict("Ambiguous account subject")
        if not candidates:
            return None
        username = candidates[0].get("username")
        if not isinstance(username, str) or not 3 <= len(username.strip()) <= 120:
            return None
        username = username.strip().lower()
        key = "account_" + hashlib.sha256(username.encode("utf-8")).hexdigest()
        # The canonical lookup also rejects duplicate historical account keys.
        # Never authorize solely from a query row's claimed username or selector.
        record = await self.registry_store.get(key)
        if (
            not record or record.get("kind") != "account" or record.get("active") is not True
            or not isinstance(record.get("username"), str)
            or record["username"].strip().lower() != username
        ):
            return None
        mind_id = record.get("account_mind_id")
        if mind_id is None or mind_id == "":
            mind_id = "__legacy__"
        if (
            not isinstance(mind_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", mind_id)
            or mind_id != subject
        ):
            return None
        return Account(username=username, mind_id=mind_id)

    async def _ensure_mind(self, mind_id: str) -> None:
        """Ensure an account's tenant has a Genesis mind.

        Early signup builds wrote the account record before initializing its Mind,
        so a failed initialization could leave a valid account pointing at an
        empty tenant. Repair that state when the account next authenticates.
        """
        if getattr(self.registry_store, "kind", None) == "surreal":
            from aicognitive_mind.surreal_storage import SurrealMindStore

            # The registry already owns the connection to this namespace/database.
            # Opening another native SurrealKV engine on the same path can leave
            # the first engine with stale serialization state after tenant writes.
            # Remote Surreal connections can use this same tenant-scoped store.
            mind = SurrealMindStore(self.registry_store.db, mind_id)
            if await mind.load() is None:
                await mind.initialize(CognitiveMind(identity=MindIdentity(self_name=None)))
            return

        storage = await create_storage(self.settings, mind_id=mind_id)
        try:
            if await storage.mind.load() is None:
                await storage.mind.initialize(
                    CognitiveMind(identity=MindIdentity(self_name=None))
                )
        finally:
            await storage.runtime.close()

    async def create(self, username: str, password: str) -> Account:
        username = username.strip().lower()
        if len(username) < 3 or len(password) < 8:
            raise ValueError("Username must be at least 3 characters and password at least 8.")
        key = "account_" + hashlib.sha256(username.encode("utf-8")).hexdigest()
        if await self.registry_store.get(key):
            raise ValueError("Account already exists")
        mind_id = "mind_" + uuid4().hex

        # Initialize the tenant before publishing credentials. This prevents a
        # failed Genesis initialization from leaving an orphan account record.
        await self._ensure_mind(mind_id)

        salt, digest = self._password_hash(password)
        await self.registry_store.create(key, {
            "kind": "account",
            "username": username,
            "account_mind_id": mind_id,
            "password_salt": salt,
            "password_hash": digest,
            "active": True,
        })
        # Verify the record through the same lookup used by login. A successful
        # database create acknowledgement is not proof that authentication can
        # retrieve the account (for example, after a scope/namespace mismatch).
        persisted = await self.registry_store.get(key)
        if not persisted or persisted.get("account_mind_id") != mind_id:
            logger.error("AUTH_DIAG signup registry_readback_failed")
            raise RuntimeError("Account storage verification failed; signup was not confirmed.")
        logger.warning("AUTH_DIAG signup registry_readback_ok")
        return Account(username=username, mind_id=mind_id)

    async def authenticate(self, username: str, password: str) -> Account | None:
        username = username.strip().lower()
        key = "account_" + hashlib.sha256(username.encode("utf-8")).hexdigest()
        record = await self.registry_store.get(key)
        if record is None:
            logger.warning("AUTH_DIAG account authentication record_not_found")
            return None
        if not record.get("active", False):
            logger.warning("AUTH_DIAG account authentication inactive")
            return None
        salt = bytes.fromhex(record["password_salt"])
        _, digest = self._password_hash(password, salt)
        if not hmac.compare_digest(digest, record["password_hash"]):
            logger.warning("AUTH_DIAG account authentication password_mismatch")
            return None
        logger.warning("AUTH_DIAG account authentication accepted")
        # Credential verification must not depend on tenant/Mind initialization.
        # If tenant storage is temporarily unhealthy, valid credentials should
        # still establish the account session instead of turning login into a
        # 500. Tenant access/repair belongs after authentication.
        mind_id_value = record.get("account_mind_id")
        if mind_id_value:
            mind_id = str(mind_id_value)
        else:
            # Compatibility for the original pre-multi-user account. Its Mind
            # lives in the unscoped legacy store, so do not manufacture a new
            # tenant id: doing so makes the existing Mind appear uninitialized.
            mind_id = "__legacy__"
            logger.warning("AUTH_DIAG account authentication legacy_mind_selected")
        return Account(username=username, mind_id=mind_id)
