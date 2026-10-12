from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from pydantic import BaseModel, Field, field_validator


class MCPToolRecord(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)
    input_schema: dict[str, Any] = Field(default_factory=dict, alias="inputSchema")
    enabled: bool = True

    model_config = {"populate_by_name": True}


class MCPServerRecord(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex, min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=8, max_length=2000)
    bearer_token: str = Field(default="", max_length=4096)
    enabled: bool = True
    tools: list[MCPToolRecord] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def validate_id(cls, value: str) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
            raise ValueError("Server ID may contain only letters, numbers, underscores, and hyphens")
        return value

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("MCP server URL must use HTTP or HTTPS and include a hostname")
        if parsed.username or parsed.password or parsed.fragment:
            raise ValueError("MCP server URL cannot embed credentials or a fragment")
        return value.rstrip("/")


class MCPServerRegistry:
    RECORD_KEY = "mcp_server_registry"

    def __init__(self, records: Any) -> None:
        self.records = records

    async def list(self) -> list[MCPServerRecord]:
        record = await self.records.get(self.RECORD_KEY)
        if not record:
            return []
        return [MCPServerRecord.model_validate(item) for item in record.get("items", [])]

    async def replace(self, items: list[MCPServerRecord]) -> list[MCPServerRecord]:
        identifiers = [item.id for item in items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("MCP server IDs must be unique")
        names = [item.name.casefold() for item in items]
        if len(names) != len(set(names)):
            raise ValueError("MCP server names must be unique")
        after = {"items": [item.model_dump(mode="json", by_alias=True) for item in items]}
        before = await self.records.get(self.RECORD_KEY)
        if before is None:
            await self.records.create(self.RECORD_KEY, after)
        elif not await self.records.replace(self.RECORD_KEY, before, after):
            raise RuntimeError("MCP server registry changed concurrently; refresh and retry")
        return items

    async def discover(self, server: MCPServerRecord) -> list[MCPToolRecord]:
        result = await self._request(server, "tools/list", {})
        tools = result.get("tools", [])
        if not isinstance(tools, list):
            raise ValueError("MCP server returned an invalid tools list")
        discovered: list[MCPToolRecord] = []
        for item in tools:
            if not isinstance(item, dict) or not isinstance(item.get("name"), str):
                continue
            previous = next((tool for tool in server.tools if tool.name == item["name"]), None)
            schema = item.get("inputSchema", {})
            discovered.append(
                MCPToolRecord(
                    name=item["name"],
                    description=str(item.get("description") or ""),
                    inputSchema=schema if isinstance(schema, dict) else {},
                    enabled=previous.enabled if previous else True,
                )
            )
        return discovered

    async def call_tool(
        self,
        server: MCPServerRecord,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if not server.enabled:
            raise ValueError("This MCP server is disabled")
        tool = next((item for item in server.tools if item.name == tool_name), None)
        if tool is None or not tool.enabled:
            raise ValueError("This MCP tool is not enabled")
        return await self._request(
            server,
            "tools/call",
            {"name": tool_name, "arguments": arguments},
        )

    async def _request(
        self,
        server: MCPServerRecord,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if server.bearer_token:
            headers["Authorization"] = f"Bearer {server.bearer_token}"
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as client:
            initialize = await client.post(
                server.url,
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "Axiom Admin", "version": "1.0.0"},
                    },
                },
            )
            initialize.raise_for_status()
            session_id = initialize.headers.get("mcp-session-id")
            if session_id:
                headers["MCP-Session-Id"] = session_id
            initialized = await client.post(
                server.url,
                headers=headers,
                json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            )
            if initialized.status_code not in {200, 202, 204}:
                initialized.raise_for_status()
            response = await client.post(
                server.url,
                headers=headers,
                json={"jsonrpc": "2.0", "id": 2, "method": method, "params": params},
            )
            response.raise_for_status()
            payload = self._decode_response(response)
            if "error" in payload:
                error = payload["error"]
                message = error.get("message", "Unknown MCP error") if isinstance(error, dict) else str(error)
                raise ValueError(f"MCP server error: {message}")
            result = payload.get("result", {})
            if not isinstance(result, dict):
                raise ValueError("MCP server returned an invalid JSON-RPC result")
            return result

    @staticmethod
    def _decode_response(response: httpx.Response) -> dict[str, Any]:
        content_type = response.headers.get("content-type", "").lower()
        if "json" in content_type:
            payload = response.json()
        else:
            payload = None
            for line in response.text.splitlines():
                if line.startswith("data:"):
                    data = line[5:].strip()
                    if data and data != "[DONE]":
                        try:
                            candidate = json.loads(data)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(candidate, dict) and ("result" in candidate or "error" in candidate):
                            payload = candidate
            if payload is None:
                raise ValueError("MCP server returned no JSON-RPC response")
        if not isinstance(payload, dict):
            raise ValueError("MCP server returned an invalid JSON-RPC response")
        return payload
