import unittest
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import aicognitive_mind.initialize_cli as initialize_cli


class FakeRuntime:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeMindStore:
    def __init__(self) -> None:
        self.mind = None

    async def initialize(self, mind: Any) -> Any:
        self.mind = mind
        return mind


class FakeJournalStore:
    def __init__(self) -> None:
        self.entries: list[Any] = []

    async def append(self, entry: Any, recorded_by: Any) -> Any:
        self.entries.append((entry, recorded_by))
        return entry


class InitializeCliTests(unittest.IsolatedAsyncioTestCase):
    async def test_initialize_once_creates_identity_and_closes_runtime(self) -> None:
        runtime = FakeRuntime()
        mind = FakeMindStore()
        journal = FakeJournalStore()
        storage = SimpleNamespace(
            runtime=runtime,
            mind=mind,
            journal=journal,
            memory=object(),
        )

        async def fake_create_storage(_settings: Any) -> Any:
            return storage

        with patch.object(initialize_cli, "create_storage", fake_create_storage):
            result = await initialize_cli.initialize_once(
                object(),
                "AICognitiveMind",
                (
                    "Understanding before Recommending",
                    "Preserve continuity of identity",
                ),
            )

        self.assertEqual(result["status"], "initialized")
        self.assertEqual(
            result["mind"]["identity"]["self_name"],
            "AICognitiveMind",
        )
        self.assertEqual(
            result["mind"]["identity"]["foundational_values"],
            [
                "Understanding before Recommending",
                "Preserve continuity of identity",
            ],
        )
        self.assertEqual(len(journal.entries), 1)
        self.assertTrue(runtime.closed)


if __name__ == "__main__":
    unittest.main()
