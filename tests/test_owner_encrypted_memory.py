"""Synthetic tests using a fresh embedded SurrealKV database, never production."""
from __future__ import annotations

import base64
import secrets
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from surrealdb import AsyncSurreal, RecordID

from aicognitive_mind.community_memory import CommunityPrincipal
from aicognitive_mind.owner_encrypted_memory import (
    OwnerEncryptedMemory,
    OwnerEncryptedMemoryError,
    OwnerEncryptedRecordMissing,
    OwnerEncryptedRecordUnauthenticated,
    OwnerMemoryReference,
)
from aicognitive_mind.private_community_steward import PrivateRecordBinding


class RecordingConnection:
    def __init__(self, database: Any) -> None:
        self.database = database
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def query(self, query: str, variables: dict[str, Any]) -> Any:
        self.calls.append((query, variables))
        return await self.database.query(query, variables)


class OwnerEncryptedMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.uri = "surrealkv://" + str(Path(directory.name) / "private_memory")
        self.database: Any = None
        self.addAsyncCleanup(self._close)
        await self._open()
        self.owner = CommunityPrincipal("synthetic_private_account", "synthetic_private_mind")
        self.key = secrets.token_bytes(32)
        self.primary = OwnerMemoryReference.new(
            PrivateRecordBinding(self.owner, "synthetic_private_local_record_id", 9),
        )
        self.plaintext = "Local-only synthetic invoice phrase: EMBER CANARY 5421"

    async def _open(self) -> None:
        self.database = AsyncSurreal(self.uri)
        await self.database.connect()
        await self.database.use("synthetic_ns", "owner_encrypted_staging")
        self.connection = RecordingConnection(self.database)

    async def _close(self) -> None:
        if self.database is not None:
            await self.database.close()
            self.database = None

    def _store(self) -> OwnerEncryptedMemory:
        return OwnerEncryptedMemory(self.connection, self.owner)

    async def test_round_trip_reopen_and_local_recall_with_only_ciphertext_on_wire(self) -> None:
        second = OwnerMemoryReference.new(
            PrivateRecordBinding(self.owner, "another_private_record", 1),
        )
        store = self._store()
        await store.create(self.primary, self.plaintext, key=self.key)
        await store.create(second, "An unrelated fake memory.", key=self.key)
        before_restart = list(self.connection.calls)
        # Inspect the actual stored rows, not just what our helper returned.
        rows = await self.database.query("SELECT * FROM owner_encrypted_memory;", {})
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(set(row) == {"id", "envelope"} for row in rows))
        self.assertTrue(all(
            base64.b64decode(row["envelope"], validate=True).startswith(b"ACM-CS")
            for row in rows
        ))

        await self._close()
        await self._open()
        store = self._store()
        self.assertEqual(await store.read(self.primary, key=self.key), self.plaintext)
        result = await store.recall(
            "ember canary", references=(self.primary, second), key=self.key,
        )
        self.assertEqual([(row.reference, row.text) for row in result], [
            (self.primary, self.plaintext),
        ])
        self.assertEqual(await store.recall(
            "a missing synthetic phrase", references=(self.primary, second), key=self.key,
        ), ())
        requests_and_rows = repr((before_restart, self.connection.calls, rows)).casefold()
        for private_value in (
            self.plaintext, "ember canary", "a missing synthetic phrase", self.owner.account_id,
            self.owner.mind_id, self.primary.binding.record_id, second.binding.record_id,
            self.key.hex(), base64.b64encode(self.key).decode("ascii"),
        ):
            self.assertNotIn(private_value.casefold(), requests_and_rows)

    async def test_wrong_missing_key_owner_version_and_locator_fail_closed(self) -> None:
        store = self._store()
        await store.create(self.primary, self.plaintext, key=self.key)
        before = len(self.connection.calls)
        with self.assertRaisesRegex(OwnerEncryptedMemoryError, "owner key"):
            await store.recall("ember", references=(), key=b"")
        with self.assertRaisesRegex(OwnerEncryptedMemoryError, "belongs to another owner"):
            await OwnerEncryptedMemory(
                self.connection, CommunityPrincipal("another_owner", self.owner.mind_id),
            ).read(self.primary, key=self.key)
        self.assertEqual(len(self.connection.calls), before)
        other = CommunityPrincipal("another_owner", self.owner.mind_id)
        forged = OwnerMemoryReference(
            PrivateRecordBinding(other, self.primary.binding.record_id, 9), self.primary.locator,
        )
        with self.assertRaises(OwnerEncryptedRecordUnauthenticated):
            await OwnerEncryptedMemory(self.connection, other).read(forged, key=self.key)
        with self.assertRaisesRegex(OwnerEncryptedRecordUnauthenticated, "authentication"):
            await store.read(self.primary, key=bytes(byte ^ 0xFF for byte in self.key))
        wrong_binding = OwnerMemoryReference(
            PrivateRecordBinding(self.owner, self.primary.binding.record_id, 10),
            self.primary.locator,
        )
        with self.assertRaisesRegex(OwnerEncryptedRecordUnauthenticated, "authentication"):
            await store.read(wrong_binding, key=self.key)
        another_location = OwnerMemoryReference.new(self.primary.binding)
        stored_record = RecordID("owner_encrypted_memory", self.primary.locator)
        row = await self.database.query(
            "SELECT envelope FROM ONLY $record;", {"record": stored_record},
        )
        await self.database.query("CREATE ONLY $record CONTENT $body;", {
            "record": RecordID("owner_encrypted_memory", another_location.locator),
            "body": row,
        })
        with self.assertRaisesRegex(OwnerEncryptedRecordUnauthenticated, "authentication"):
            await store.read(another_location, key=self.key)

    async def test_modified_missing_and_duplicate_records_never_fall_back(self) -> None:
        store = self._store()
        with self.assertRaises(OwnerEncryptedRecordMissing):
            await store.recall("ember", references=(self.primary,), key=self.key)
        await store.create(self.primary, self.plaintext, key=self.key)
        with self.assertRaisesRegex(OwnerEncryptedMemoryError, "database operation failed"):
            await store.create(self.primary, "different value", key=self.key)
        self.assertEqual(await store.read(self.primary, key=self.key), self.plaintext)
        with self.assertRaisesRegex(OwnerEncryptedMemoryError, "Duplicate"):
            await store.recall("ember", references=(self.primary, self.primary), key=self.key)

        record = RecordID("owner_encrypted_memory", self.primary.locator)
        row = await self.database.query("SELECT envelope FROM ONLY $record;", {"record": record})
        altered = bytearray(base64.b64decode(row["envelope"], validate=True))
        altered[-1] ^= 1
        await self.database.query("UPDATE ONLY $record SET envelope = $data;", {
            "record": record, "data": base64.b64encode(altered).decode("ascii"),
        })
        with self.assertRaisesRegex(OwnerEncryptedRecordUnauthenticated, "authentication"):
            await store.recall("ember", references=(self.primary,), key=self.key)


if __name__ == "__main__":
    unittest.main()
