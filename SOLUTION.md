# SOLUTION

A weather agent built on the Model Context Protocol: an **MCP weather server** and a
**provider-agnostic chat agent** with both a terminal REPL and a Chainlit web UI.

## Language

**Python 3.11+.** It's the role's primary language, and the whole stack is first-class in
Python: the official `mcp` SDK, the Anthropic SDK, and async HTTP via `httpx`. Managed
with **uv** for fast, reproducible installs from a committed lock file.

## Quick start

Prerequisites: **Python ≥ 3.11**, **uv**, an **Anthropic API key**. Docker is optional.

```bash
cp .env.example .env        # then set ANTHROPIC_API_KEY in .env
```

**Run locally**

```bash
uv sync --extra dev                                  # install
uv run weather-agent                                 # terminal REPL
uv run chainlit run src/weather_agent/ui/web.py      # web UI → http://localhost:8000
make check                                           # ruff + 51 tests
```

**Run with Docker** (one command, serves the web UI)

```bash
docker compose up --build                            # → http://localhost:8000
```

The MCP server needs no key (Open-Meteo is free); only the agent needs an LLM key.

## Configuration (no secrets in code)

All config comes from the environment / `.env` (loaded by `pydantic-settings`).
`.env.example` is the committed template; `.env` is git-ignored.

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Active provider (only `anthropic` ships; see extensions) |
| `ANTHROPIC_API_KEY` | — | Required; the app fails fast with a clear message if missing |
| `ANTHROPIC_MODEL` | `claude-haiku-4-5` | Any tool-calling Claude model |
| `AGENT_MAX_ITERATIONS` | `8` | Hard cap on tool-call iterations per turn |
| `WEATHER_CACHE_TTL_SECONDS` | `600` | Current-weather cache TTL (`0` disables it) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Architecture

Two sibling packages under `src/` that never import each other — they communicate only
over MCP. The design is **ports and adapters**: each component depends on an abstraction,
and the replaceable parts (LLM vendor, MCP transport, UI, observability backend, upstream
HTTP) are adapters behind those ports.

```
  INPUT adapters          PORTS (stable)              OUTPUT adapters
  REPL ┐                                          ┌─ AnthropicProvider  (shipped)
  Web  ┼─▶ AgentSession ─▶ depends on ─▶ LLMProvider ┼─ (OpenAIProvider, … = extension)
       ┘     (loop)                                └─
                  ├─▶ MCPGateway ─▶ stdio ─▶ weather_mcp server ─▶ Open-Meteo
                  └─▶ Tracer ──┬─ LoggingTracer (shipped)
                               └─ (LangfuseTracer = extension)
```

**Part 1 — MCP server (`src/weather_mcp/`).** Layered so dependencies point inward:
`server.py` (thin FastMCP adapter) → `service.py` (orchestrates geocode → fetch → map,
owns the WMO code→text map) → `clients/` (Open-Meteo `httpx` clients behind Protocols,
plus caching decorators) → `domain/` (pure pydantic value objects + typed errors). The
domain knows nothing about MCP or Open-Meteo wire formats.

**Part 2 — chat agent (`src/weather_agent/`).** `AgentSession.send()` runs a bounded
tool-calling loop and yields a typed event stream (`TextDelta`, `ToolCallStarted`,
`ToolResult`, `Done`). It depends only on `LLMProvider`, `ToolGateway`, and `Tracer`
abstractions — no SDK or transport types — so it's fully unit-testable with fakes. Both
frontends consume the same event stream.

### How SOLID shows up
- **SRP** — geocoding, weather fetch, domain mapping, MCP transport, and the agent loop
  are separate units, each with one reason to change.
- **DIP** — the agent loop talks to `LLMProvider`/`ToolGateway`/`Tracer`, never to a
  concrete SDK; dependencies are injected at the composition root (`runtime.py`).
- **OCP** — adding an LLM provider, a tracer backend, a UI frontend, or caching is a new
  adapter/decorator; existing code is untouched.
- **LSP** — `Cached*Client` and the real Open-Meteo clients are interchangeable behind
  the same Protocol; the service can't tell them apart.

### Error handling
Typed domain errors (`LocationNotFoundError`, `UpstreamWeatherError`) are mapped by the
server into graceful MCP tool errors (`isError`), surfaced by the gateway, and fed back to
the model as observations. A stack trace never reaches the user or the LLM, and the agent
can recover (e.g. ask the user to clarify an unknown place).

Deeper rationale lives in [`docs/adr/`](docs/adr/) (the hard-to-reverse decisions),
[`docs/RESEARCH.md`](docs/RESEARCH.md) (verified foundations + sources), and the
spec-driven change under [`openspec/changes/weather-mcp-agent/`](openspec/changes/weather-mcp-agent/).

## Testing

`make check` runs ruff + **51 tests**. Tests inject fakes at the ports (a mock `httpx`
transport, a fake `LLMProvider`, a fake `ToolGateway`), so they need **no network and no
API keys**. The server is exercised through a real in-memory MCP client round-trip. Each
spec scenario maps to a test.

Validated end-to-end with a live key across all three surfaces: the REPL, the Chainlit web
UI, and the Docker container (including a multi-tool "compare Madrid and Oslo" query and
follow-up questions that rely on conversation context).

## Bonuses implemented

- **Streaming** — token-by-token from the provider through the agent to both UIs.
- **Web UI** — Chainlit chat that renders the tool calls (input + output) as live steps.
- **Tests** — unit + in-memory MCP integration (51).
- **Observability** — structured logging of every provider/tool step with latency, behind
  an extensible `Tracer` seam.
- **Containerisation** — `Dockerfile` + `docker-compose.yml`, one-command run.

## Dependency licenses (all permissive)

| Package | License |
|---|---|
| `mcp` | MIT |
| `httpx` | BSD-3-Clause |
| `pydantic` / `pydantic-settings` | MIT |
| `anthropic` | MIT |
| `chainlit` | Apache-2.0 |
| `pytest`, `ruff` (dev) | MIT |

## Trade-offs & limitations

- **stdio transport** couples the server lifecycle to the agent process — ideal for local
  use and a clean checkout. It's isolated behind `MCPGateway`, so switching to an HTTP
  transport is a one-adapter change.
- **Geocoding** searches the first comma-segment of the location (so "New York, NY"
  resolves) and takes the top-ranked match; the resolved name/region is echoed back so the
  user sees what was matched. Ambiguous names could be improved with disambiguation.
- **Conversation context** is in-memory per session (not persisted across restarts).
- **Caching** is in-process (not shared across processes).

## What I'd add with more time

- **A second LLM provider (e.g. OpenAI)** — the `LLMProvider` port and factory are ready;
  it's one adapter plus a registration. Same pattern shipped for one provider to keep the
  abstraction honest without doubling the surface.
- **A Langfuse tracer** behind the existing `Tracer` seam, for richer LLM tracing.
- **More tools** (multi-day forecast, alerts, comparison) — the server's layering makes a
  new tool a thin addition over the existing service.
- **LLM prompt caching** of the system prompt + tool definitions to cut cost/latency on
  longer sessions.
- **HTTP/SSE transport**, plus auth and rate limiting, for a multi-user deployment, and CI
  running `make check` on every PR.
