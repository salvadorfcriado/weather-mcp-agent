# Weather MCP Agent

A weather assistant built on the **Model Context Protocol (MCP)**:

- **`src/weather_mcp/`** — an MCP server exposing weather tools, backed by the free
  [Open-Meteo](https://open-meteo.com/) API (no key required).
- **`src/weather_agent/`** — a terminal chat agent that connects to the server as an MCP
  client, discovers tools dynamically, and runs a provider-agnostic LLM tool-calling loop
  (Anthropic **or** OpenAI) with conversation memory.

> Time-boxed engineering exercise (a few hours). Scope, decisions and trade-offs: [`SOLUTION.md`](SOLUTION.md).

## Quickstart

```bash
cp .env.example .env         # then set ANTHROPIC_API_KEY in .env

# Local (Python >=3.11 + uv):
uv sync --extra dev
make run-agent               # terminal REPL (launches the MCP server for you)
uv run chainlit run src/weather_agent/ui/web.py   # web UI → http://localhost:8000

# Or with Docker (serves the web UI):
docker compose up --build    # → http://localhost:8000
```

Other commands: `make check` (lint + tests), `make run-server`, `make test`.

Full setup, architecture, and trade-offs: **[`SOLUTION.md`](SOLUTION.md)**.

## Layout

```
src/weather_mcp/     Part 1 — MCP server (domain · clients · service · server)
src/weather_agent/   Part 2 — providers · mcp_gateway · agent loop · ui/ (REPL + Chainlit)
tests/               unit + integration (no network, no API keys)
docs/                CONTEXT (glossary) · RESEARCH (sources) · adr/ (decisions)
openspec/            spec-driven change: proposal → design → specs → tasks
```

## Design at a glance
- The agent depends on `LLMProvider` and `MCPGateway` abstractions only — adding a provider
  is a new adapter, the loop untouched (DIP/OCP). See [`docs/adr/`](docs/adr/).
- The two packages never import each other; they communicate only over MCP.
- Config via environment (`pydantic-settings`); no secrets in code.

## License & dependencies
MIT. All runtime dependencies are permissively licensed (MIT/BSD/Apache-2.0); see
[`SOLUTION.md`](SOLUTION.md) for the breakdown.
