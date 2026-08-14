from __future__ import annotations

from typing import Any, Protocol


class ReasoningTool(Protocol):
    """A cognitive tool that a reasoning-engine adapter may expose to its model."""

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def input_schema(self) -> dict[str, Any]: ...

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]: ...
