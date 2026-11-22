"""Owner-side encrypted candidate input, not loaded by the hosted application.

Run this only inside the owner's trust boundary. The caller provides every
key, trusted local consent check and local selector. No key provisioning,
password derivation, cloud inference, storage or network client is provided.

Local host sequence:
1. Obtain a 32-byte key from owner-controlled local key storage and keep the
   record binding alongside its encrypted envelope. Use encrypt_private_input
   on explicitly supplied input, not on a copy pulled from a hosted journal.
2. When personal sleep issues a handoff receipt, call curate_and_submit_locally
   with the encrypted envelope, key and expected binding. Provide a trusted
   consent check and a same-boundary selector that returns a catalog enum.
3. The submit adapter maps (receipt, lesson) to the hosted handoff API; neither
   the key nor the plaintext is an argument. Published lesson recall needs no
   private key, though it still needs its ordinary community authorization.

Run the executable synthetic example in tests/test_private_community_steward.py
with unittest discovery. Deploying this module inside operator-controlled
Python would NOT give the owner an exclusive trust boundary. This doesn't
migrate existing hosted journals and cannot guarantee erasure of Python bytes.
"""
from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from secrets import token_bytes

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from aicognitive_mind.community_memory import CommunityPrincipal, SyntheticLesson

_FORMAT = b"ACM-CS\x01"
_NONCE_BYTES = 12
_KEY_BYTES = 32
_TAG_BYTES = 16
MAX_PRIVATE_BYTES = 65_536
_ACCOUNT_ID = re.compile(r"[A-Za-z0-9_:-]{1,160}")
_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
_RECEIPT = re.compile(r"[A-Za-z0-9_-]{43}")


class PrivateInputError(ValueError):
    """Invalid or unauthenticated input; never includes any sensitive values."""


@dataclass(frozen=True, slots=True)
class PrivateRecordBinding:
    principal: CommunityPrincipal
    record_id: str
    version: int

    def associated_data(self) -> bytes:
        if type(self.principal) is not CommunityPrincipal:
            raise PrivateInputError("Invalid private record binding")
        fields = (self.principal.account_id, self.principal.mind_id, self.record_id)
        if (
            type(fields[0]) is not str or not _ACCOUNT_ID.fullmatch(fields[0])
            or any(type(field) is not str or not _ID.fullmatch(field) for field in fields[1:])
            or type(self.version) is not int
            or not 0 < self.version < 2**63
        ):
            raise PrivateInputError("Invalid private record binding")
        return _FORMAT + json.dumps((*fields, self.version), separators=(",", ":")).encode("ascii")


def _cipher(key: bytes) -> AESGCM:
    if type(key) is not bytes or len(key) != _KEY_BYTES:
        raise PrivateInputError("A caller-supplied 32-byte key is required")
    return AESGCM(key)


def encrypt_private_input(record: bytes, *, key: bytes, binding: PrivateRecordBinding) -> bytes:
    """Return a versioned envelope; caller retains key and expected binding locally."""
    if type(record) is not bytes or not 0 < len(record) <= MAX_PRIVATE_BYTES:
        raise PrivateInputError("Invalid private input size or type")
    nonce = token_bytes(_NONCE_BYTES)
    ciphertext = _cipher(key).encrypt(nonce, record, binding.associated_data())
    return _FORMAT + nonce + ciphertext


def decrypt_private_input(envelope: bytes, *, key: bytes, binding: PrivateRecordBinding) -> bytes:
    """Authenticate against the expected local record, owner, Mind and version."""
    nonce_end = len(_FORMAT) + _NONCE_BYTES
    overhead = nonce_end + _TAG_BYTES
    if (
        type(envelope) is not bytes
        or not overhead < len(envelope) <= overhead + MAX_PRIVATE_BYTES
        or not envelope.startswith(_FORMAT)
    ):
        raise PrivateInputError("Invalid encrypted private input")
    try:
        return _cipher(key).decrypt(
            envelope[len(_FORMAT):nonce_end], envelope[nonce_end:], binding.associated_data()
        )
    except InvalidTag:
        raise PrivateInputError("Encrypted private input failed authentication") from None


async def curate_and_submit_locally(
    envelope: bytes,
    *,
    key: bytes,
    binding: PrivateRecordBinding,
    receipt: str,
    is_opted_in: Callable[[], bool],
    select_local: Callable[[bytes], SyntheticLesson | None],
    submit: Callable[[str, SyntheticLesson], Awaitable[bool]],
) -> bool:
    """Run one owner-local selection; hand only receipt and fixture ID to submit.

    Consent and selector callbacks must be trusted and remain local. This
    process does not sandbox the selector, guarantee zeroization in Python or
    replace the server's current authorization and one-use receipt checks.
    """
    if is_opted_in() is not True:
        return False
    if type(receipt) is not str or not _RECEIPT.fullmatch(receipt):
        return False
    record = decrypt_private_input(envelope, key=key, binding=binding)
    try:
        selected = select_local(record)
    except Exception:
        # A model error might include its input. Do not propagate its text.
        return False
    finally:
        del record
    if type(selected) is not SyntheticLesson or is_opted_in() is not True:
        return False
    return await submit(receipt, selected) is True
