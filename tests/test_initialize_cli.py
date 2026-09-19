from types import SimpleNamespace
from typing import Any

import pytest

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


@pytest.mark.asyncio
async def test_initialize_once_creates_identity_and_closes_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    monkeypatch.setattr(initialize_cli, "create_storage", fake_create_storage)

    result = await initialize_cli.initialize_once(
        object(),
        "AICognitiveMind",
        ("Understanding before Recommending", "Preserve continuity of identity"),
    )

    assert result["status"] == "initialized"
    assert result["mind"]["identity"]["self_name"] == "AICognitiveMind"
    assert result["mind"]["identity"]["foundational_values"] == [
        "Understanding before Recommending",
        "Preserve continuity of identity",
    ]
    assert len(journal.entries) == 1
    assert runtime.closed is True
