import asyncio
import os

from mcp import Client


async def main() -> None:
    url = os.environ.get("MCP_URL", "http://127.0.0.1:8001/mcp")

    async with Client(url) as client:
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
            raise RuntimeError(f"Missing MCP tools: {sorted(missing)}")

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
        if initialized.structured_content["status"] != "initialized":
            raise RuntimeError(f"Unexpected initialization result: {initialized}")

        first = await client.call_tool(
            "begin_interaction",
            {"user_message": "My birthday is February 7. Remember that."},
        )
        if first.structured_content["status"] != "ready_to_reason":
            raise RuntimeError(f"Unexpected begin result: {first}")

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
        decisions = completed.structured_content["memory_decisions"]
        if not decisions or not decisions[0]["accepted"]:
            raise RuntimeError(f"Memory was not accepted: {completed}")

        later = await client.call_tool(
            "begin_interaction",
            {"user_message": "When is Will's birthday?"},
        )
        recalled = later.structured_content["recalled_context"]["durable_memory"]
        if not any(item["content"] == "Will's birthday is February 7." for item in recalled):
            raise RuntimeError(f"Birthday memory not recalled: {later}")

        status = await client.call_tool("mind_status", {})
        if status.structured_content["durable_memory_count"] != 1:
            raise RuntimeError(f"Unexpected memory count: {status}")

        print("MCP continuity smoke test passed")
        print("Tools:", ", ".join(sorted(names)))
        print("Recalled:", recalled[0]["content"])


if __name__ == "__main__":
    asyncio.run(main())
