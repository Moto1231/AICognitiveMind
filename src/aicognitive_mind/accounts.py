from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from aicognitive_mind.domain import CognitiveMind, MindIdentity
from aicognitive_mind.persistence import create_storage
from aicognitive_mind.config import Settings


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

    async def _ensure_mind(self, mind_id: str) -> None:
        """Ensure an account's tenant has a Genesis mind.

        Early signup builds wrote the account record before initializing its Mind,
        so a failed initialization could leave a valid account pointing at an
        empty tenant. Repair that state when the account next authenticates.
        """
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
            "mind_id": mind_id,
            "password_salt": salt,
            "password_hash": digest,
            "active": True,
        })
        return Account(username=username, mind_id=mind_id)

    async def authenticate(self, username: str, password: str) -> Account | None:
        username = username.strip().lower()
        key = "account_" + hashlib.sha256(username.encode("utf-8")).hexdigest()
        record = await self.registry_store.get(key)
        if not record or not record.get("active", False):
            return None
        salt = bytes.fromhex(record["password_salt"])
        _, digest = self._password_hash(password, salt)
        if not hmac.compare_digest(digest, record["password_hash"]):
            return None
        mind_id = str(record["mind_id"])
        await self._ensure_mind(mind_id)
        return Account(username=username, mind_id=mind_id)
