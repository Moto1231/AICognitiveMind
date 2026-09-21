"""Two independent host sessions and server processes against durable test storage.

Uses deterministic host responses; never calls a paid model or production storage.
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

from mcp import Client, StdioServerParameters

from aicognitive_mind.domain import CognitiveMind, MindIdentity
from aicognitive_mind.surreal_storage import SurrealMindStore, SurrealRuntime


def structured(result):
    if result.is_error or result.structured_content is None:
        raise RuntimeError(str(result))
    return result.structured_content


async def main():
    with tempfile.TemporaryDirectory() as directory:
        uri = "surrealkv://" + str(Path(directory) / "handoff").replace("\\", "/")
        runtime = SurrealRuntime(uri, "ci", "handoff")
        await runtime.initialize()
        original = CognitiveMind(
            identity=MindIdentity(
                self_name="Axiom",
                foundational_values=("Continuity",),
                relationships=({"name": "Will", "role": "creator"},),
            )
        )
        await SurrealMindStore(runtime.database).initialize(original)
        await runtime.close()
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "aicognitive_mind.mcp_server", "--transport", "stdio"],
            env={
                **os.environ,
                "STORAGE_PROVIDER": "surreal",
                "SURREALDB_URI": uri,
                "SURREALDB_NAMESPACE": "ci",
                "SURREALDB_DATABASE": "handoff",
                "SURREALDB_USERNAME": "",
                "SURREALDB_PASSWORD": "",
            },
        )
        proposal = {
            "memory_class": "semantic",
            "content": "Atlas uses SurrealDB.",
            "grounding": ["Direct test interaction"],
            "associations": ["Atlas"],
        }
        async with Client(parameters) as host_a:
            await host_a.call_tool("begin_interaction", {"user_message": "Remember Atlas"})
            first = structured(
                await host_a.call_tool(
                    "complete_interaction",
                    {
                        "user_message": "Remember Atlas",
                        "response_text": "Saved by host A",
                        "proposed_memories": [proposal],
                        "idempotency_key": "host-a-turn",
                    },
                )
            )
        # Closing the Client stops its stdio child. A new process must recover disk state.
        async with Client(parameters) as host_b:
            resumed = structured(
                await host_b.call_tool("begin_interaction", {"user_message": "Atlas"})
            )
            assert resumed["mind"] == original.model_dump(mode="json")
            assert (
                resumed["recalled_context"]["durable_memory"][0]["content"] == proposal["content"]
            )
            retry = structured(
                await host_b.call_tool(
                    "complete_interaction",
                    {
                        "user_message": "Remember Atlas",
                        "response_text": "Saved by host A",
                        "proposed_memories": [proposal],
                        "idempotency_key": "host-a-turn",
                    },
                )
            )
            assert retry == first
            structured(
                await host_b.call_tool(
                    "complete_interaction",
                    {
                        "user_message": "Continue",
                        "response_text": "Continued by host B",
                        "proposed_memories": [],
                        "idempotency_key": "host-b-turn",
                    },
                )
            )
            status = structured(await host_b.call_tool("mind_status", {}))
            assert status["journal_experience_count"] == 2
            assert status["durable_memory_count"] == 1
        print(
            "Two-process MCP handoff passed: identity, relationships, memory, receipts and subsequent writes"
        )


if __name__ == "__main__":
    asyncio.run(main())
