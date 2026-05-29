## Why

The exercise asks us to show how we build AI-powered applications on the Model Context
Protocol. A weather agent is the vehicle: it must demonstrate correct MCP usage, a clean
LLM tool-calling loop, and — what actually matters — sound architecture and clear
communication. This change delivers that as a complete, reviewable solution.

## What Changes

- Add an **MCP weather server** exposing a `get_current_weather` tool that accepts a
  human-readable location, geocodes it, and returns current conditions (temperature, wind
  speed, a description, with units) from the free Open-Meteo API. Location-not-found and
  upstream failures surface as typed, graceful results — never stack traces.
- Add a **provider-agnostic LLM layer**: a single `LLMProvider` interface with an
  **Anthropic** adapter shipped and selected at runtime by env var (Strategy + Factory);
  additional providers (e.g. OpenAI) are new adapters behind the same port, documented as
  an extension in `SOLUTION.md`, not implemented here.
- Add a **chat agent** that connects to the server as an MCP client, discovers tools
  dynamically, drives a bounded tool-calling loop, keeps conversation context, and emits
  an **event stream** (text deltas, tool-call started, tool result, done) so any frontend
  can render progress live.
- Add a **chat interface** with two interchangeable frontends over that event stream: a
  **terminal REPL** (default, simple) and a **Chainlit web UI** (Apache-2.0) that shows
  the agent's tool-calls as they happen.
- Make **observability extensible**: the agent emits trace events through a `Tracer`
  seam; ship a structured-logging tracer; document a Langfuse adapter as the future
  extension (no Langfuse dependency or server in this deliverable).
- **Cache upstream data** (geocoding for the session, current weather on a short TTL) via
  a Decorator over the HTTP clients, leaving the `WeatherService` untouched.
- Add supporting infrastructure: env-based configuration (no secrets in code), a pytest
  suite, and Docker packaging, plus `SOLUTION.md`.

## Capabilities

### New Capabilities
- `mcp-weather-server`: An MCP server (FastMCP, stdio) exposing weather tool(s) backed by
  Open-Meteo geocoding + current-weather, with typed domain models, injectable + cached
  clients, and graceful error handling.
- `llm-provider-abstraction`: A single `LLMProvider` interface with an Anthropic adapter
  and a factory seam for additional providers, selected by env var, normalizing chat +
  tool-calls so nothing downstream depends on a vendor SDK; fails fast on missing keys; no
  secrets in code.
- `weather-chat-agent`: The MCP client + bounded tool-calling loop. Discovers tools
  dynamically, invokes them via a gateway, turns errors into observations, keeps in-session
  context, emits an event stream, and reports through an extensible observability seam.
- `chat-interface`: User-facing chat over the agent's event stream. Two interchangeable
  frontends — terminal REPL and Chainlit web UI — neither coupled to the LLM or to MCP.

### Modified Capabilities
<!-- None — greenfield repo, no existing specs. -->

## Impact

- New code under `src/weather_mcp/` (Part 1) and `src/weather_agent/` (Part 2, including
  `providers/`, `mcp_gateway`, `agent`, an `observability` seam, and `ui/` for REPL + web);
  `tests/`.
- Runtime dependencies, all permissive: `mcp` (MIT), `httpx` (BSD), `pydantic` /
  `pydantic-settings` (MIT), `anthropic` (MIT), `chainlit` (Apache-2.0). Dev: `pytest`,
  `ruff` (MIT). Pinned in `uv.lock`.
- New project tooling already in place: `pyproject.toml`, `.env.example`, `Makefile`.
  Still to add: `Dockerfile`, `docker-compose.yml`, `SOLUTION.md`.
- Requires an Anthropic API key at runtime; the MCP server needs none.

## Non-goals

- Extra tools (multi-day forecast, weather alerts, location comparison) — may follow if
  time allows.
- **Running a Langfuse (or any tracing) server** — observability ships as a structured-
  logging tracer behind an extensible seam; Langfuse is documented as a future adapter.
- LLM prompt caching — deferred to "next steps" (marginal for short conversations).
- Persisting conversation across sessions (in-memory context only).
- Authentication, multi-user, production deployment / CI beyond local Docker.
