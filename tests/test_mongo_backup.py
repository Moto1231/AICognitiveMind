import os
import tempfile
import unittest
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

from bson import BSON, ObjectId

from scripts.backup_mongo import (
    create_backup,
    restore_backup,
    verify_backup,
)


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]] | None = None) -> None:
        self.documents = deepcopy(documents or [])

    def count_documents(self, _query: dict[str, Any]) -> int:
        return len(self.documents)

    def find(self, _query: dict[str, Any]) -> list[dict[str, Any]]:
        return deepcopy(self.documents)

    def insert_many(
        self,
        documents: list[dict[str, Any]],
        ordered: bool = True,
    ) -> None:
        assert ordered
        self.documents.extend(deepcopy(documents))

    def delete_many(self, query: dict[str, Any]) -> None:
        identifiers = set(query["_id"]["$in"])
        self.documents = [
            document for document in self.documents if document.get("_id") not in identifiers
        ]


class FailingCollection(FakeCollection):
    def insert_many(
        self,
        documents: list[dict[str, Any]],
        ordered: bool = True,
    ) -> None:
        super().insert_many(documents, ordered=ordered)
        raise RuntimeError("simulated write failure")


class FakeDatabase:
    def __init__(
        self,
        collections: dict[str, list[dict[str, Any]]] | None = None,
        *,
        name: str = "ai_cognitive_mind",
    ) -> None:
        self.name = name
        self.collections = {
            collection_name: FakeCollection(documents)
            for collection_name, documents in (collections or {}).items()
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())


def cognitive_documents() -> dict[str, list[dict[str, Any]]]:
    return {
        "mind": [
            {
                "_id": ObjectId("64b64c7f17f3f9c01e84a111"),
                "identity": {"self_name": "AICognitiveMind"},
                "created_at": datetime(2026, 9, 13, 1, 45, tzinfo=timezone.utc),
            }
        ],
        "journal": [
            {
                "_id": ObjectId("64b64c7f17f3f9c01e84a112"),
                "kind": "initialization",
            }
        ],
        "memory": [
            {
                "_id": ObjectId("64b64c7f17f3f9c01e84a113"),
                "content": "Preserve continuity of identity.",
            }
        ],
        "diagnostics": [
            {
                "_id": ObjectId("64b64c7f17f3f9c01e84a114"),
                "component": "reasoning_engine",
            }
        ],
    }


class MongoBackupTests(unittest.TestCase):
    def test_exports_verifies_and_restores_exact_bson_documents(self) -> None:
        source_documents = cognitive_documents()
        source = FakeDatabase(source_documents)
        target = FakeDatabase()

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "canonical.mind-backup"
            exported = create_backup(
                source,
                backup,
                created_at=datetime(2026, 9, 19, 14, 0, tzinfo=timezone.utc),
            )

            self.assertEqual(
                exported,
                {"mind": 1, "journal": 1, "memory": 1, "diagnostics": 1},
            )
            self.assertEqual(verify_backup(backup), exported)
            self.assertEqual(os.stat(backup).st_mode & 0o777, 0o600)

            restored = restore_backup(backup, target)

        self.assertEqual(restored, exported)
        for name, expected_documents in source_documents.items():
            self.assertEqual(
                [BSON.encode(document) for document in target[name].documents],
                [BSON.encode(document) for document in expected_documents],
            )

    def test_refuses_export_without_exactly_one_mind(self) -> None:
        source = FakeDatabase()

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "invalid.mind-backup"
            with self.assertRaisesRegex(RuntimeError, "exactly one Mind document"):
                create_backup(source, backup)
            self.assertFalse(backup.exists())

    def test_refuses_restore_into_existing_cognitive_history(self) -> None:
        source = FakeDatabase(cognitive_documents())
        target = FakeDatabase({"mind": [{"_id": "another-mind"}]})

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "canonical.mind-backup"
            create_backup(source, backup)
            with self.assertRaisesRegex(RuntimeError, "refusing to merge two cognitive histories"):
                restore_backup(backup, target)

        self.assertEqual(target["mind"].documents, [{"_id": "another-mind"}])

    def test_detects_collection_corruption(self) -> None:
        source = FakeDatabase(cognitive_documents())

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "canonical.mind-backup"
            create_backup(source, backup)
            with ZipFile(backup, "r") as archive:
                files = {name: archive.read(name) for name in archive.namelist()}
            files["collections/memory.json"] += b" "
            with ZipFile(backup, "w", compression=ZIP_DEFLATED) as archive:
                for name, payload in files.items():
                    archive.writestr(name, payload)

            with self.assertRaisesRegex(RuntimeError, "checksum mismatch"):
                verify_backup(backup)

    def test_rolls_back_partial_restore(self) -> None:
        source = FakeDatabase(cognitive_documents())
        target = FakeDatabase()
        target.collections["memory"] = FailingCollection()

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "canonical.mind-backup"
            create_backup(source, backup)
            with self.assertRaisesRegex(RuntimeError, "simulated write failure"):
                restore_backup(backup, target)

        for name in ("mind", "journal", "memory", "diagnostics"):
            self.assertEqual(target[name].documents, [])

    def test_refuses_to_overwrite_a_backup_by_default(self) -> None:
        source = FakeDatabase(cognitive_documents())

        with tempfile.TemporaryDirectory() as directory:
            backup = Path(directory) / "canonical.mind-backup"
            create_backup(source, backup)
            with self.assertRaises(FileExistsError):
                create_backup(source, backup)


if __name__ == "__main__":
    unittest.main()
