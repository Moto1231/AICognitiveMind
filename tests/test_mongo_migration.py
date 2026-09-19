import unittest
from copy import deepcopy
from typing import Any

from scripts.migrate_mongo import migrate


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


class FakeDatabase:
    def __init__(self, collections: dict[str, list[dict[str, Any]]] | None = None) -> None:
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in (collections or {}).items()
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection())


class MongoMigrationTests(unittest.TestCase):
    def test_migrates_one_mind_and_full_history_without_reinitialization(self) -> None:
        source = FakeDatabase(
            {
                "mind": [{"_id": "mind-storage-id", "identity": {"self_name": "Genesis"}}],
                "journal": [{"_id": "j1", "kind": "initialization"}],
                "memory": [{"_id": "m1", "content": "Will likes parks."}],
                "diagnostics": [{"_id": "d1", "component": "reasoning_engine"}],
            }
        )
        target = FakeDatabase()

        copied = migrate(source, target)

        self.assertEqual(
            copied,
            {"mind": 1, "journal": 1, "memory": 1, "diagnostics": 1},
        )
        self.assertEqual(
            target["mind"].documents[0]["identity"]["self_name"],
            "Genesis",
        )
        self.assertEqual(target["memory"].documents[0]["content"], "Will likes parks.")
        self.assertEqual(target["mind"].documents[0]["_id"], "mind-storage-id")

    def test_refuses_target_that_already_contains_cognitive_history(self) -> None:
        source = FakeDatabase({"mind": [{"identity": {"self_name": "Genesis"}}]})
        target = FakeDatabase({"mind": [{"identity": {"self_name": "Another"}}]})

        with self.assertRaisesRegex(RuntimeError, "refusing to merge two cognitive histories"):
            migrate(source, target)

    def test_refuses_source_without_exactly_one_mind(self) -> None:
        source = FakeDatabase()
        target = FakeDatabase()

        with self.assertRaisesRegex(RuntimeError, "exactly one Mind document"):
            migrate(source, target)


if __name__ == "__main__":
    unittest.main()
