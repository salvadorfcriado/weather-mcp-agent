# 0001 — Use the official MCP SDK (FastMCP) over a hand-rolled protocol, on stdio

**Status:** accepted

## Context
MCP is a JSON-RPC protocol. We could implement the wire protocol by hand (educational,
full control) or use the official `mcp` Python SDK's `FastMCP`. The exercise judges
*correct use of the MCP protocol*, and the server/agent run locally on one machine.

## Decision
Use `mcp.server.fastmcp.FastMCP` for the server and the official `ClientSession` +
`stdio_client` for the agent. Transport is **stdio**: the agent launches the server as a
child process.

## Why (alternatives considered)
- **Hand-rolled JSON-RPC** — rejected: re-implementing the spec risks subtle protocol
  bugs and signals effort spent in the wrong place. FastMCP generates the tool schema from
  type hints + docstrings, which is exactly the "correct protocol use" being assessed.
- **Streamable HTTP transport** — rejected for local use: adds ports, session ids, and
  origin allow-listing for no benefit here. We isolate transport behind `MCPGateway`, so
  switching to HTTP later is a one-module change.

## Consequences
- (+) Minimal protocol boilerplate; schema stays in sync with the Python signatures.
- (+) "Run from a clean checkout" is trivial — no network ports, no server lifecycle to manage.
- (−) Tied to the SDK's release cadence; mitigated by pinning the version in `uv.lock`.
