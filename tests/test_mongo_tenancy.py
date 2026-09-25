import unittest
from copy import deepcopy
from typing import Any

from aicognitive_mind.domain import (
    CognitiveMind,
    DiagnosticObservation,
    DurableMemory,
    JournalEntry,
    JournalKind,
    MemoryClass,
    MindIdentity,
    SensoryEvidenceArtifact,
)
from aicognitive_mind.mongo_storage import (
    MongoDiagnosticStore,
    MongoEvidenceStore,
    MongoJournalStore,
    MongoMemoryStore,
    MongoMindStore,
)


class FakeCursor:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = deepcopy(documents)
        self._index = 0

    def sort(self, *_args: Any, **_kwargs: Any) -> "FakeCursor":
        return self

    def __aiter__(self) -> "FakeCursor":
        self._index = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._index >= len(self.documents):
            raise StopAsyncIteration
        value = self.documents[self._index]
        self._index += 1
        return deepcopy(value)


class FakeCollection:
    def __init__(self, documents: list[dict[str, Any]]) -> None:
        self.documents = deepcopy(documents)

    @staticmethod
    def _matches(document: dict[str, Any], query: dict[str, Any]) -> bool:
        return all(document.get(key) == value for key, value in query.items())

    @staticmethod
    def _project(
        document: dict[str, Any],
        projection: dict[str, int] | None,
    ) -> dict[str, Any]:
        result = deepcopy(document)
        if projection:
            for key, enabled in projection.items():
                if enabled == 0:
                    result.pop(key, None)
        return result

    async def find_one(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> dict[str, Any] | None:
        for document in self.documents:
            if self._matches(document, query):
                return self._project(document, projection)
        return None

    def find(
        self,
        query: dict[str, Any],
        projection: dict[str, int] | None = None,
    ) -> FakeCursor:
        return FakeCursor(
            [
                self._project(document, projection)
                for document in self.documents
                if self._matches(document, query)
            ]
        )


class FakeDatabase:
    def __init__(self, collections: dict[str, list[dict[str, Any]]]) -> None:
        self.collections = {
            name: FakeCollection(documents)
            for name, documents in collections.items()
        }

    def __getitem__(self, name: str) -> FakeCollection:
        return self.collections.setdefault(name, FakeCollection([]))


class MongoTenancyTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_minds_cannot_read_each_others_cognitive_data(self) -> None:
        alpha_mind = CognitiveMind(identity=MindIdentity(self_name="Alpha"))
        beta_mind = CognitiveMind(identity=MindIdentity(self_name="Beta"))
        alpha_memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="alpha-memory",
        )
        beta_memory = DurableMemory(
            memory_class=MemoryClass.SEMANTIC,
            content="beta-memory",
        )
        alpha_journal = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"input": {"content": "alpha-journal"}},
        )
        beta_journal = JournalEntry(
            kind=JournalKind.INTERACTION,
            experience={"input": {"content": "beta-journal"}},
        )
        alpha_diagnostic = DiagnosticObservation(
            component="alpha",
            operation="test",
            implementation={},
        )
        beta_diagnostic = DiagnosticObservation(
            component="beta",
            operation="test",
            implementation={},
        )
        alpha_evidence = SensoryEvidenceArtifact(
            modality="vision",
            source="alpha-camera",
            media_type="image/png",
            sha256="a" * 64,
            byte_length=1,
            payload_base64="YQ==",
        )
        beta_evidence = SensoryEvidenceArtifact(
            modality="vision",
            source="beta-camera",
            media_type="image/png",
            sha256="b" * 64,
            byte_length=1,
            payload_base64="Yg==",
        )

        database = FakeDatabase(
            {
                "mind": [
                    {"_id": "alpha", "mind_id": "alpha", **alpha_mind.model_dump(mode="python")},
                    {"_id": "beta", "mind_id": "beta", **beta_mind.model_dump(mode="python")},
                ],
                "memory": [
                    {"mind_id": "alpha", **alpha_memory.model_dump(mode="python")},
                    {"mind_id": "beta", **beta_memory.model_dump(mode="python")},
                ],
                "journal": [
                    {"mind_id": "alpha", **alpha_journal.model_dump(mode="python")},
                    {"mind_id": "beta", **beta_journal.model_dump(mode="python")},
                ],
                "diagnostics": [
                    {"mind_id": "alpha", **alpha_diagnostic.model_dump(mode="python")},
                    {"mind_id": "beta", **beta_diagnostic.model_dump(mode="python")},
                ],
                "evidence": [
                    {"mind_id": "alpha", **alpha_evidence.model_dump(mode="python")},
                    {"mind_id": "beta", **beta_evidence.model_dump(mode="python")},
                ],
            }
        )

        alpha = {
            "mind": MongoMindStore(database, "alpha"),
            "memory": MongoMemoryStore(database, "alpha"),
            "journal": MongoJournalStore(database, "alpha"),
            "diagnostics": MongoDiagnosticStore(database, "alpha"),
            "evidence": MongoEvidenceStore(database, "alpha"),
        }
        beta = {
            "mind": MongoMindStore(database, "beta"),
            "memory": MongoMemoryStore(database, "beta"),
            "journal": MongoJournalStore(database, "beta"),
            "diagnostics": MongoDiagnosticStore(database, "beta"),
            "evidence": MongoEvidenceStore(database, "beta"),
        }

        self.assertEqual((await alpha["mind"].load()).identity.self_name, "Alpha")
        self.assertEqual((await beta["mind"].load()).identity.self_name, "Beta")
        self.assertEqual([m.content for m in await alpha["memory"].read()], ["alpha-memory"])
        self.assertEqual([m.content for m in await beta["memory"].read()], ["beta-memory"])
        self.assertEqual(
            [j.experience["input"]["content"] for j in await alpha["journal"].read()],
            ["alpha-journal"],
        )
        self.assertEqual(
            [j.experience["input"]["content"] for j in await beta["journal"].read()],
            ["beta-journal"],
        )
        self.assertEqual(
            [d.component for d in await alpha["diagnostics"].read()],
            ["alpha"],
        )
        self.assertEqual(
            [d.component for d in await beta["diagnostics"].read()],
            ["beta"],
        )
        self.assertEqual(
            [e.source for e in await alpha["evidence"].read()],
            ["alpha-camera"],
        )
        self.assertEqual(
            [e.source for e in await beta["evidence"].read()],
            ["beta-camera"],
        )

    def test_portal_filters_always_include_mind_id(self) -> None:
        database = FakeDatabase({"memory": [], "journal": []})
        memory = MongoMemoryStore(database, "alpha")
        journal = MongoJournalStore(database, "alpha")

        self.assertEqual(memory._portal_filter()["mind_id"], "alpha")
        self.assertEqual(journal._portal_filter()["mind_id"], "alpha")


if __name__ == "__main__":
    unittest.main()
