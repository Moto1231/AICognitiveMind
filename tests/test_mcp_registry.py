import unittest

from pydantic import ValidationError

from aicognitive_mind.mcp_registry import MCPServerRecord, MCPServerRegistry, MCPToolRecord


class FakeRecords:
    def __init__(self):
        self.value = None

    async def get(self, key):
        return self.value

    async def create(self, key, value):
        self.value = value

    async def replace(self, key, before, after):
        if self.value != before:
            return False
        self.value = after
        return True


class MCPServerRegistryTests(unittest.IsolatedAsyncioTestCase):
    async def test_registry_persists_server_and_tool_schema(self):
        records = FakeRecords()
        registry = MCPServerRegistry(records)
        server = MCPServerRecord(
            id="server-one",
            name="Example",
            url="https://example.com/mcp",
            tools=[
                MCPToolRecord(
                    name="hello",
                    description="Say hello",
                    inputSchema={"type": "object", "properties": {"name": {"type": "string"}}},
                )
            ],
        )

        await registry.replace([server])
        loaded = await registry.list()

        self.assertEqual(loaded[0].id, "server-one")
        self.assertEqual(loaded[0].tools[0].name, "hello")
        self.assertEqual(loaded[0].tools[0].input_schema["properties"]["name"]["type"], "string")

    async def test_registry_rejects_duplicate_names(self):
        registry = MCPServerRegistry(FakeRecords())
        first = MCPServerRecord(id="one", name="Same", url="https://one.example/mcp")
        second = MCPServerRecord(id="two", name="same", url="https://two.example/mcp")

        with self.assertRaises(ValueError):
            await registry.replace([first, second])

    async def test_server_url_must_be_http_or_https(self):
        with self.assertRaises(ValidationError):
            MCPServerRecord(id="bad", name="Bad", url="ftp://example.com/mcp")

    async def test_disabled_tools_cannot_be_called(self):
        registry = MCPServerRegistry(FakeRecords())
        server = MCPServerRecord(
            id="server-one",
            name="Example",
            url="https://example.com/mcp",
            tools=[MCPToolRecord(name="disabled", enabled=False)],
        )

        with self.assertRaisesRegex(ValueError, "not enabled"):
            await registry.call_tool(server, "disabled", {})


if __name__ == "__main__":
    unittest.main()
