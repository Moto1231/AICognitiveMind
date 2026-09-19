import asyncio
import os
import sys
import uuid

from mcp import Client, StdioServerParameters


def structured(result, tool_name: str) -> dict:
    if result.is_error:
        text = " | ".join(
            item.text for item in result.content if hasattr(item, "text")
        )
        raise RuntimeError(f"{tool_name} failed: {text}")
    if result.structured_content is None:
        raise RuntimeError(f"{tool_name} returned no structured content: {result}")
    return result.structured_content


async def main() -> None:
    database = f"ai_cognitive_mind_stdio_ci_{uuid.uuid4().hex}"
    provider = os.environ.get("STORAGE_PROVIDER", "surreal")
    env = {
        "STORAGE_PROVIDER": provider,
        "APP_NAME": "AI Cognitive Mind CI",
    }
    if provider == "surreal":
        env.update(
            {
                "SURREALDB_URI": os.environ.get("SURREALDB_URI", "mem://"),
                "SURREALDB_NAMESPACE": os.environ.get("SURREALDB_NAMESPACE", "ci"),
                "SURREALDB_DATABASE": database,
            }
        )
    else:
        env.update(
            {
                "MONGODB_URI": os.environ.get(
                    "MONGODB_URI", "mongodb://127.0.0.1:27017"
                ),
                "MONGODB_DATABASE": database,
            }
        )
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "aicognitive_mind.mcp_server", "--transport", "stdio"],
        env=env,
    )

    async with Client(params) as client:
        tools = await client.list_tools()
        names = {tool.name for tool in tools.tools}
        expected = {
            "initialize_mind",
            "mind_status",
            "begin_interaction",
            "complete_interaction",
        }
        missing = expected - names
        if missing:
            raise RuntimeError(f"Missing MCP tools over stdio: {sorted(missing)}")

        initialized = await client.call_tool(
            "initialize_mind",
            {
                "self_name": "Genesis",
                "foundational_values": [
                    "Understanding before Recommending",
                    "Preserve continuity of identity",
                ],
            },
        )
        if structured(initialized, "initialize_mind")["status"] != "initialized":
            raise RuntimeError(f"Unexpected initialization result: {initialized}")

        completed = await client.call_tool(
            "complete_interaction",
            {
                "user_message": "My birthday is February 7. Remember that.",
                "response_text": "I'll remember that your birthday is February 7.",
                "proposed_memories": [
                    {
                        "memory_class": "semantic",
                        "content": "Will's birthday is February 7.",
                        "associations": ["Will", "birthday", "February 7"],
                        "grounding": ["Will directly stated his birthday."],
                    }
                ],
            },
        )
        decisions = structured(completed, "complete_interaction")["memory_decisions"]
        if not decisions or not decisions[0]["accepted"]:
            raise RuntimeError(f"Memory was not accepted: {completed}")

        later = await client.call_tool(
            "begin_interaction",
            {"user_message": "When is Will's birthday?"},
        )
        recalled = structured(later, "begin_interaction")["recalled_context"]["durable_memory"]
        if not any(item["content"] == "Will's birthday is February 7." for item in recalled):
            raise RuntimeError(f"Birthday memory not recalled over stdio: {later}")

        print("MCP stdio continuity smoke test passed")
        print("Tools:", ", ".join(sorted(names)))
        print("Recalled:", recalled[0]["content"])


if __name__ == "__main__":
    asyncio.run(main())
