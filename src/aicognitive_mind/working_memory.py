from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, TypeAdapter

from aicognitive_mind.storage import WorkingMemoryStore


class ReadWorkingMemoryCall(BaseModel):
    action: Literal["read"]


class SetWorkingContextCall(BaseModel):
    action: Literal["set_context"]
    key: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=1, max_length=500)


WorkingMemoryCall = ReadWorkingMemoryCall | SetWorkingContextCall
_CALL_ADAPTER: TypeAdapter[WorkingMemoryCall] = TypeAdapter(WorkingMemoryCall)


class WorkingMemoryTool:
    """Interaction-scoped access to the Mind's temporary conscious context."""

    def __init__(self, store: WorkingMemoryStore) -> None:
        self._store = store

    @property
    def name(self) -> str:
        return "working_memory"

    @property
    def description(self) -> str:
        return (
            "Read or update temporary conscious context such as the current speaker, location, "
            "active topic, or immediate situation. This context is intentionally flushable at "
            "checkpoints and is not long-term memory."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["read", "set_context"],
                },
                "key": {
                    "type": "string",
                    "description": "Required for set_context; e.g. current_speaker.",
                },
                "value": {
                    "type": "string",
                    "description": "Required for set_context; temporary context value.",
                },
            },
            "required": ["action"],
        }

    async def invoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        call = _CALL_ADAPTER.validate_python(arguments)
        if isinstance(call, ReadWorkingMemoryCall):
            state = await self._store.read()
            return {"status": "read", "working_context": state.context}

        state = await self._store.set_context(call.key, call.value)
        return {
            "status": "updated",
            "working_context": state.context,
        }
