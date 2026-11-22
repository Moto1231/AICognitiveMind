"""Additive owner-side storage and recall for explicitly known encrypted records.

The caller owns the database connection, key, and list of local references.
The hosted application does not load this adapter. No existing record is read,
rewritten, or used as a fallback, and the database never sees a search query.
"""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from secrets import token_hex
from typing import Any, Protocol

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from surrealdb import RecordID

from aicognitive_mind.community_memory import CommunityPrincipal
from aicognitive_mind.private_community_steward import (
    MAX_PRIVATE_BYTES,
    PrivateInputError,
    PrivateRecordBinding,
    decrypt_private_input,
    encrypt_private_input,
)

_TABLE = "owner_encrypted_memory"
_LOOKUP = re.compile(r"[0-9a-f]{64}")
_KEY_CONTEXT = b"Axiom owner encrypted memory record key v1"
_MAX_RECALL_RECORDS = 32
_MAX_RECALL_QUERY = 512
_MAX_ENCODED_ENVELOPE = ((MAX_PRIVATE_BYTES + 64 + 2) // 3) * 4
_CREATE = "CREATE ONLY $record CONTENT $body;"
_READ = "SELECT envelope FROM ONLY $record;"


class OwnerEncryptedMemoryError(ValueError):
    """Invalid local input or unavailable encrypted storage."""


class OwnerEncryptedRecordMissing(OwnerEncryptedMemoryError):
    """The database omitted an explicitly expected record."""


class OwnerEncryptedRecordUnauthenticated(OwnerEncryptedMemoryError):
    """The stored envelope did not authenticate against the owner's expectations."""


class OwnerMemoryDatabase(Protocol):
    async def query(self, query: str, variables: dict[str, Any]) -> Any: ...


@dataclass(frozen=True, slots=True, repr=False)
class OwnerMemoryReference:
    """Owner-held reference. Only the independent opaque locator leaves the owner."""

    binding: PrivateRecordBinding
    locator: str

    @classmethod
    def new(cls, binding: PrivateRecordBinding) -> OwnerMemoryReference:
        reference = cls(binding, token_hex(32))
        reference.validate()
        return reference

    def validate(self) -> None:
        if (
            type(self.binding) is not PrivateRecordBinding
            or type(self.locator) is not str
            or not _LOOKUP.fullmatch(self.locator)
        ):
            raise OwnerEncryptedMemoryError("Invalid encrypted memory reference")
        try:
            self.binding.associated_data()
        except PrivateInputError:
            raise OwnerEncryptedMemoryError("Invalid private memory binding") from None


@dataclass(frozen=True, slots=True, repr=False)
class OwnerMemoryMatch:
    reference: OwnerMemoryReference
    text: str


def _require_key(key: bytes) -> None:
    if type(key) is not bytes or len(key) != 32:
        raise OwnerEncryptedMemoryError("A 32-byte owner key is required")


def _record_key(key: bytes, reference: OwnerMemoryReference) -> bytes:
    # A distinct AEAD key binds the random lookup handle without disclosing
    # the owner, Mind, record ID or version to the database.
    return HKDF(
        algorithm=hashes.SHA256(), length=32,
        salt=bytes.fromhex(reference.locator), info=_KEY_CONTEXT,
    ).derive(key)


class OwnerEncryptedMemory:
    """Use only inside the owner process with a separately authorized Surreal connection."""

    def __init__(self, database: OwnerMemoryDatabase, principal: CommunityPrincipal) -> None:
        if type(principal) is not CommunityPrincipal:
            raise OwnerEncryptedMemoryError("Invalid owner")
        self._database = database
        self._principal = principal

    def _check_reference(self, reference: OwnerMemoryReference) -> None:
        if (
            type(reference) is not OwnerMemoryReference
            or type(reference.binding) is not PrivateRecordBinding
            or reference.binding.principal != self._principal
        ):
            raise OwnerEncryptedMemoryError("Encrypted memory reference belongs to another owner")
        reference.validate()

    async def _query(self, sql: str, variables: dict[str, Any]) -> Any:
        try:
            return await self._database.query(sql, variables)
        except Exception:
            # Drivers may include connection or bound values in exception messages.
            raise OwnerEncryptedMemoryError("Encrypted memory database operation failed") from None

    async def create(self, reference: OwnerMemoryReference, text: str, *, key: bytes) -> None:
        """Append a version through this adapter; duplicate locators do not overwrite."""
        _require_key(key)
        self._check_reference(reference)
        if type(text) is not str or not 0 < len(text) <= MAX_PRIVATE_BYTES:
            raise OwnerEncryptedMemoryError("Invalid private memory size or type")
        try:
            value = text.encode("utf-8")
        except UnicodeEncodeError:
            raise OwnerEncryptedMemoryError("Invalid private memory encoding") from None
        if len(value) > MAX_PRIVATE_BYTES:
            raise OwnerEncryptedMemoryError("Invalid private memory size or type")
        envelope = encrypt_private_input(
            value, key=_record_key(key, reference), binding=reference.binding,
        )
        encoded = base64.b64encode(envelope).decode("ascii")
        row = await self._query(_CREATE, {
            "record": RecordID(_TABLE, reference.locator), "body": {"envelope": encoded},
        })
        if not isinstance(row, dict) or row.get("envelope") != encoded:
            raise OwnerEncryptedMemoryError("Encrypted memory write was not confirmed")

    async def read(self, reference: OwnerMemoryReference, *, key: bytes) -> str:
        """Read a known reference. Missing, tampered and wrong-key are errors."""
        _require_key(key)
        self._check_reference(reference)
        row = await self._query(_READ, {"record": RecordID(_TABLE, reference.locator)})
        if row is None:
            raise OwnerEncryptedRecordMissing("The expected encrypted memory is unavailable")
        encoded = row.get("envelope") if isinstance(row, dict) else None
        if type(encoded) is not str or not 0 < len(encoded) <= _MAX_ENCODED_ENVELOPE:
            raise OwnerEncryptedMemoryError("Invalid encrypted memory response")
        try:
            envelope = base64.b64decode(encoded, validate=True)
        except ValueError:
            raise OwnerEncryptedMemoryError("Invalid encrypted memory response") from None
        try:
            value = decrypt_private_input(
                envelope, key=_record_key(key, reference), binding=reference.binding,
            )
        except PrivateInputError:
            raise OwnerEncryptedRecordUnauthenticated(
                "Encrypted memory failed authentication"
            ) from None
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            raise OwnerEncryptedMemoryError("Invalid private memory encoding") from None

    async def recall(
        self, phrase: str, *, references: tuple[OwnerMemoryReference, ...], key: bytes,
    ) -> tuple[OwnerMemoryMatch, ...]:
        """Match a phrase locally against up to 32 explicitly supplied references."""
        _require_key(key)
        if type(phrase) is not str or not 0 < len(phrase) <= _MAX_RECALL_QUERY or not phrase.strip():
            raise OwnerEncryptedMemoryError("Invalid local recall phrase")
        if type(references) is not tuple or len(references) > _MAX_RECALL_RECORDS:
            raise OwnerEncryptedMemoryError("Too many or invalid local recall references")
        for reference in references:
            self._check_reference(reference)
        if (
            len({reference.locator for reference in references}) != len(references)
            or len({reference.binding for reference in references}) != len(references)
        ):
            raise OwnerEncryptedMemoryError("Duplicate local recall references")
        query = phrase.strip().casefold()
        matches = []
        for reference in references:
            text = await self.read(reference, key=key)
            if query in text.casefold():
                matches.append(OwnerMemoryMatch(reference, text))
        return tuple(matches)
