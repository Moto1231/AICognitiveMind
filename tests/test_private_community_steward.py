import unittest
from dataclasses import replace
from typing import cast
from unittest.mock import AsyncMock, Mock, patch

from aicognitive_mind.community_memory import CommunityPrincipal, SyntheticLesson
from aicognitive_mind.private_community_steward import (
    MAX_PRIVATE_BYTES,
    PrivateInputError,
    PrivateRecordBinding,
    curate_and_submit_locally,
    decrypt_private_input,
    encrypt_private_input,
)

# Deliberately fake values, not keys to any real record.
KEY = bytes(range(32))
PRIVATE = b"synthetic-private-marker-not-for-community"
RECEIPT = "r" * 43
BINDING = PrivateRecordBinding(
    CommunityPrincipal("account:mind-alpha", "mind-alpha"), "record-a", 1,
)


class PrivateInputTests(unittest.TestCase):
    def test_ciphertext_roundtrip_and_nonce_changes(self):
        first = encrypt_private_input(PRIVATE, key=KEY, binding=BINDING)
        second = encrypt_private_input(PRIVATE, key=KEY, binding=BINDING)
        self.assertNotEqual(first, second)
        self.assertNotIn(PRIVATE, first)
        self.assertNotIn(KEY, first)
        self.assertEqual(decrypt_private_input(first, key=KEY, binding=BINDING), PRIVATE)

    def test_wrong_key_binding_and_tamper_fail_closed(self):
        encrypted = encrypt_private_input(PRIVATE, key=KEY, binding=BINDING)
        wrong_bindings = (
            replace(BINDING, principal=CommunityPrincipal("account-other", "mind-alpha")),
            replace(BINDING, principal=CommunityPrincipal("account-alpha", "mind-other")),
            replace(BINDING, record_id="record-b"),
            replace(BINDING, version=2),
        )
        wrong_inputs = [
            (encrypted, KEY, binding) for binding in wrong_bindings
        ] + [
            (encrypted, b"x" * 32, BINDING),
            (encrypted[:-1] + bytes([encrypted[-1] ^ 1]), KEY, BINDING),
            (encrypted[:-1], KEY, BINDING),
            (b"garbage", KEY, BINDING),
        ]
        for ciphertext, key, binding in wrong_inputs:
            with self.assertRaises(PrivateInputError):
                decrypt_private_input(ciphertext, key=key, binding=binding)

    def test_size_and_version_are_bounded(self):
        with self.assertRaises(PrivateInputError):
            encrypt_private_input(bytes(MAX_PRIVATE_BYTES + 1), key=KEY, binding=BINDING)
        with self.assertRaises(PrivateInputError):
            encrypt_private_input(PRIVATE, key=KEY, binding=replace(BINDING, version=0))
        with self.assertRaises(PrivateInputError):
            encrypt_private_input(PRIVATE, key=b"short", binding=BINDING)


class LocalStewardTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.envelope = encrypt_private_input(PRIVATE, key=KEY, binding=BINDING)
        self.consent = Mock(return_value=True)
        self.select = Mock(return_value=SyntheticLesson.CHECK_BINDINGS)
        self.submit = AsyncMock(return_value=True)

    async def curate(self, receipt=RECEIPT):
        return await curate_and_submit_locally(
            self.envelope, key=KEY, binding=BINDING, receipt=receipt, is_opted_in=self.consent,
            select_local=self.select, submit=self.submit,
        )

    async def test_opt_out_and_malformed_receipt_never_decrypt(self):
        with patch("aicognitive_mind.private_community_steward.decrypt_private_input") as decrypt:
            self.consent.return_value = False
            self.assertFalse(await self.curate())
            self.consent.return_value = True
            self.assertFalse(await self.curate("raw private value"))
            decrypt.assert_not_called()
        self.select.assert_not_called()
        self.submit.assert_not_awaited()

    async def test_only_receipt_and_catalog_id_cross_submit_boundary(self):
        self.assertTrue(await self.curate())
        self.select.assert_called_once_with(PRIVATE)
        self.submit.assert_awaited_once_with(RECEIPT, SyntheticLesson.CHECK_BINDINGS)

    async def test_refusal_unrestricted_output_error_and_revocation_do_not_submit(self):
        for result in (None, cast(SyntheticLesson, "check_bindings"), PRIVATE):
            self.select.return_value = result
            self.assertFalse(await self.curate())
        self.select.side_effect = RuntimeError(PRIVATE)
        self.assertFalse(await self.curate())
        self.select.side_effect = None
        self.select.return_value = SyntheticLesson.CHECK_BINDINGS
        self.consent.side_effect = [True, False]
        self.assertFalse(await self.curate())
        self.submit.assert_not_awaited()
