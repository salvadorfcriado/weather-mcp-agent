## Context

Greenfield repo, `src/` layout, two sibling packages that never import each other and
talk only over MCP. The work is judged on MCP correctness, a clean agent loop, SOLID /
separation of concerns, usability, and the clarity of `SOLUTION.md`. Hard constraints
(see `CLAUDE.md`): permissive licenses only, no secrets in code, typed graceful errors,
async I/O, injectable dependencies for testability. Foundational facts (official MCP SDK
API, Open-Meteo endpoints, WMO codes) are verified in `docs/RESEARCH.md`. The three
hardest decisions are recorded as ADRs and only referenced here.

## Goals / Non-Goals

**Goals:**
- A ports-and-adapters shape where the volatile parts (LLM vendor, MCP transport, UI
  frontend, observability backend, upstream HTTP) are adapters behind stable ports.
- A bounded, streaming agent loop that the two frontends consume identically.
- Server layering where the domain is independent of MCP and of Open-Meteo.
- Everything unit-testable with injected fakes — no network, no API keys in tests.

**Non-Goals:**
- Extra weather tools, LLM prompt caching, cross-session persistence, auth, CI/deploy
  beyond local Docker. Running a tracing server (observability ships as a logging tracer
  behind a seam; Langfuse is a documented future adapter).

## Decisions

### D1 — Overall shape: ports and adapters
Each component depends on abstractions; the replaceable concretions are adapters. This is
the through-line that makes every SOLID principle visible in one consistent way.

```
  INPUT adapters            PORTS (stable)                 OUTPUT adapters
  ─────────────             ──────────────                 ───────────────
  REPL        ┐                                         ┌─ AnthropicProvider (shipped)
  Chainlit    ┼─▶ AgentSession ─▶ depends on ─▶ LLMProvider ─┼─ (future: OpenAIProvider, …)
              ┘     (loop)                                └─
                       │
                       ├─▶ MCPGateway ──▶ stdio ──▶ weather_mcp server
                       └─▶ Tracer ───────┬─ LoggingTracer (shipped)
                                         └─ (future: LangfuseTracer)
```

### D2 — MCP server layering (SRP, dependencies point inward)
```
  server.py  ─uses→  WeatherService  ─uses→  GeocodingClient / WeatherClient (Protocols)
  (FastMCP,           (orchestrate +              ▲                  ▲
   thin adapter)       map to domain,             │                  │
        │              raise typed errors)   OpenMeteo*Client    Cached*Client (Decorator)
        └─ translates domain ⇄ MCP                                    │ wraps a real client
  domain/ (models, errors)  ← pure; imported by service, imports nothing outward
```
`server.py` holds no business logic; `WeatherService` knows the steps but no wire formats;
`domain/` is pure. The WMO code→description map lives in `wmo.py`, owned by the service.

### D3 — Official MCP SDK (FastMCP) over stdio
See **ADR-0001**. FastMCP generates the tool schema from type hints + docstring; the agent
uses `ClientSession` + `stdio_client` and launches the server as a child process.

### D4 — Provider-agnostic LLM layer
See **ADR-0002**. `LLMProvider` is the port; `AnthropicProvider` is the adapter shipped in
this deliverable, chosen by a factory from `LLM_PROVIDER`. Additional providers (e.g.
OpenAI) are new adapters behind the same port — documented in `SOLUTION.md` as the OCP
extension, not implemented here. Neutral types: `Message`, `ToolSpec`, `ToolCall` (name,
arguments, id), `ToolResultMessage`.

### D5 — Upstream caching via Decorator
See **ADR-0003**. `Cached{Geocoding,Weather}Client` implement the client Protocols and
wrap a real client; wired in a factory. Geocoding cached for the process; weather on
`WEATHER_CACHE_TTL_SECONDS`.

### D6 — Agent event-stream contract (enables streaming + both UIs)
The agent exposes one async method that yields a typed event stream; the conversation
state lives inside the `AgentSession` across calls.

```python
# provider-neutral, UI-neutral
AgentEvent = TextDelta(text) | ToolCallStarted(id, tool, arguments)
           | ToolResult(id, summary, is_error) | Done(final_text)

class AgentSession:
    async def send(self, user_text: str) -> AsyncIterator[AgentEvent]: ...
```
A frontend just renders events; the REPL prints deltas and tool lines, Chainlit shows
tool steps live. **Streaming source:** `LLMProvider` exposes a streaming `chat()` that
yields neutral text deltas and the turn's tool calls; the loop re-emits text deltas,
executes tool calls via the gateway (emitting `ToolCallStarted`/`ToolResult`), feeds
results back, and repeats until the model finishes (`Done`), bounded by
`AGENT_MAX_ITERATIONS`. If provider streaming proves time-consuming, the loop can emit one
`TextDelta` per turn with the full text — the UI contract is unchanged (documented as a
fallback).

### D7 — Frontends depend only on the agent contract
REPL and Chainlit import `AgentSession` and the event types — never a provider SDK or the
MCP client. Adding a frontend touches nothing else (OCP). Lives in `weather_agent/ui/`.

### D8 — Observability is a `Tracer` seam
The loop calls a `Tracer` (start/end span, record tool call + outcome + latency).
`LoggingTracer` (structured stdlib logging) ships and is the default. A Langfuse adapter
is a documented future implementation; no Langfuse dependency is added. No secrets or raw
payloads are logged.

### D9 — Configuration
`pydantic-settings` loads all config from env / `.env`; `.env.example` is the template,
`.env` is git-ignored. Missing the selected provider's key fails fast with a clear message.

### D10 — Error handling philosophy
Typed domain errors (`LocationNotFoundError`, `UpstreamWeatherError`) → mapped by
`server.py` into MCP tool results flagged `isError` with a human message → surfaced by the
gateway and fed to the model by the agent as an observation. No stack trace ever reaches
the user or the LLM.

### D11 — Testing strategy
Inject fakes at the ports: a fake `httpx` transport for the clients, a fake `LLMProvider`
and a fake `MCPGateway` for the agent loop. Each spec scenario maps to a test. No live
network, no API keys. `make check` (ruff + pytest) is the definition of done.

## Risks / Trade-offs

- [Provider streaming with tool-calls differs across SDKs and adds complexity] → Normalize
  to neutral events at the adapter boundary; keep the non-streaming fallback (D6) so the
  bonus never blocks the core.
- [stdio couples server lifecycle to the agent process] → Acceptable; isolated behind
  `MCPGateway`, so an HTTP transport is a one-adapter change.
- [Ambiguous geocoding names] → Take the top match and echo the resolved name/country;
  documented limitation.
- [Chainlit pulls a larger dependency tree] → It's optional UI (Apache-2.0); the REPL is
  the dependency-light default path for "run from a clean checkout".
- [Two SDKs drift over time] → Versions pinned in `uv.lock`; the agent never sees SDK types.

## Open Questions

- Default models per provider in `.env.example` — pick current fast defaults
  (e.g. a fast Claude / a fast GPT), overridable by env. Resolve during apply.
- Exact ToolResult summary shape shown in the UI (full text vs. truncated) — decide when
  wiring Chainlit.
