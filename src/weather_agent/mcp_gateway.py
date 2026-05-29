"""MCP client wrapper: launch the server, discover tools, invoke them over stdio.

Isolates the MCP transport from the agent loop. The agent depends on the `ToolGateway`
Protocol (so tests inject a fake); `MCPGateway` is the real stdio-backed implementation.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import AsyncExitStack
from dataclasses import dataclass
from typing import Any, Protocol

from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

from weather_agent.providers.base import ToolSpec


@dataclass(frozen=True)
class ToolOutcome:
    """Result of a tool invocation, as data the agent can feed back to the model."""

    content: str
    is_error: bool


class ToolGateway(Protocol):
    """What the agent needs from its tool transport."""

    @property
    def tools(self) -> list[ToolSpec]: ...

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome: ...


def default_server_params() -> StdioServerParameters:
    """Launch the bundled weather server with the current interpreter, inheriting env."""
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "weather_mcp"],
        env={**os.environ},
    )


class MCPGateway:
    """Connects to the weather MCP server over stdio and exposes its tools."""

    def __init__(self, server_params: StdioServerParameters | None = None) -> None:
        self._params = server_params or default_server_params()
        self._stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._tools: list[ToolSpec] = []

    async def __aenter__(self) -> MCPGateway:
        read, write = await self._stack.enter_async_context(stdio_client(self._params))
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        discovered = await self._session.list_tools()
        self._tools = [
            ToolSpec(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
            )
            for tool in discovered.tools
        ]
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self._stack.aclose()
        self._session = None

    @property
    def tools(self) -> list[ToolSpec]:
        return self._tools

    async def call(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        if self._session is None:
            raise RuntimeError("MCPGateway is not connected; use 'async with MCPGateway() as gw'.")
        try:
            result = await self._session.call_tool(name, arguments)
        except Exception as exc:
            # Transport/protocol failure (e.g. the server died): surface it as data so
            # the agent loop can feed it back to the model instead of crashing.
            return ToolOutcome(content=f"tool call failed: {exc}", is_error=True)

        text = "\n".join(
            block.text for block in result.content if isinstance(block, types.TextContent)
        )
        if not text and result.structuredContent is not None:
            text = json.dumps(result.structuredContent)
        return ToolOutcome(
            content=text or "(tool returned no content)", is_error=bool(result.isError)
        )
