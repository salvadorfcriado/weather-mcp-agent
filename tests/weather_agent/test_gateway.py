"""Tests for MCPGateway.call result parsing and transport-error handling.

The gateway is driven with a fake MCP session (no subprocess, no network).
"""

from __future__ import annotations

from mcp import types

from weather_agent.mcp_gateway import MCPGateway


class FakeSession:
    def __init__(
        self, *, result: types.CallToolResult | None = None, raises: Exception | None = None
    ):
        self._result = result
        self._raises = raises

    async def call_tool(self, name: str, arguments: dict) -> types.CallToolResult:
        if self._raises is not None:
            raise self._raises
        assert self._result is not None
        return self._result


def _gateway_with(session: FakeSession) -> MCPGateway:
    gw = MCPGateway()
    gw._session = session  # bypass the stdio connection for a unit test
    return gw


async def test_call_parses_text_content() -> None:
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="14°C, Clear sky")], isError=False
    )
    gw = _gateway_with(FakeSession(result=result))
    outcome = await gw.call("get_current_weather", {"location": "London"})
    assert outcome.content == "14°C, Clear sky"
    assert outcome.is_error is False


async def test_call_propagates_tool_error_flag() -> None:
    result = types.CallToolResult(
        content=[types.TextContent(type="text", text="Location not found")], isError=True
    )
    gw = _gateway_with(FakeSession(result=result))
    outcome = await gw.call("get_current_weather", {"location": "Atlantis"})
    assert outcome.is_error is True
    assert "not found" in outcome.content.lower()


async def test_call_transport_error_becomes_error_outcome() -> None:
    gw = _gateway_with(FakeSession(raises=ConnectionError("server died")))
    outcome = await gw.call("get_current_weather", {"location": "London"})
    assert outcome.is_error is True
    assert "tool call failed" in outcome.content.lower()


async def test_call_falls_back_to_structured_content() -> None:
    result = types.CallToolResult(content=[], isError=False, structuredContent={"temperature": 14})
    gw = _gateway_with(FakeSession(result=result))
    outcome = await gw.call("get_current_weather", {"location": "London"})
    assert "temperature" in outcome.content
