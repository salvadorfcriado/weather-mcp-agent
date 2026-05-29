# Research & Foundations — Weather MCP Agent

Notes gathered before writing code, so the implementation rests on verified facts and
known-good patterns rather than guesswork. Sources: the official MCP Python SDK, the
Open-Meteo docs, and two reference repos studied in depth
(`rohitg00/ai-engineering-from-scratch` for MCP + agent internals, `mattpocock/skills`
for engineering discipline).

---

## 1. MCP — what it is and how we use it

MCP is a client–server protocol (JSON-RPC 2.0) with a three-phase lifecycle:
**initialize** (capability negotiation) → **operation** (tool calls, etc.) → **shutdown**.
Server primitives: **tools** (callable actions), **resources** (read-only content),
**prompts** (templates). We only need **tools**.

The four-step invariant under everything: **describe → decide → execute → observe**.
The server *describes* tools; the LLM *decides* which to call; the client *executes*
the call against the server; the result is *observed* back into the conversation.

### Decision: use the official `mcp` SDK (FastMCP), not a hand-rolled JSON-RPC loop
The reference curriculum teaches the protocol by hand-rolling stdio JSON-RPC. That is
great for understanding, but it explicitly names FastMCP as the "graduation path." For
a exercise judged on *correct use of the MCP protocol*, the official SDK is the right
choice: less boilerplate, schema generated from type hints, and no chance of subtly
mis-implementing the spec.

### Server pattern (verified against the official SDK README)
```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("weather")

@mcp.tool()
def get_current_weather(location: str, units: str = "celsius") -> dict:
    """Use when the user asks for current weather conditions in a named place.
    Do not use for multi-day forecasts or historical weather."""
    ...

if __name__ == "__main__":
    mcp.run()   # stdio transport by default
```
- Type annotations + the docstring auto-generate the tool's input schema and description.
- `mcp.run()` serves stdio with no extra wiring.

### Client pattern (verified against the official SDK README)
```python
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(command="uv", args=["run", "weather-server"])

async with stdio_client(server_params) as (read, write):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()                       # dynamic discovery
        result = await session.call_tool("get_current_weather",
                                          arguments={"location": "London"})
        for block in result.content:                             # list of content blocks
            if isinstance(block, types.TextContent):
                ...
```
- `list_tools()` is how Part 2's "discover tools dynamically" requirement is met — no
  tool names hard-coded on the agent side.
- `call_tool(...).content` is a list of content blocks (text/image/resource); read text
  blocks for our output.

### Transport: stdio
Client spawns the server as a child process; newline-delimited JSON over stdio; the
process identity *is* the session (no session id). It is the canonical local-integration
transport and makes "run from a clean checkout" trivial. Streamable HTTP exists for
remote servers (needs origin allow-listing, session ids) — out of scope here, but the
client wrapper will isolate transport so swapping later is a one-module change.

### Tool schema design (the description is load-bearing)
From the tool-schema lessons — these choices swing tool-selection accuracy 10–20 pts:
- **Name:** `snake_case`, verb-noun, no tense, no args in the name → `get_current_weather`.
- **Description pattern:** `Use when {condition}. Do not use for {close-but-wrong cases}.`
  The "Do not use for" line disambiguates against neighbours and curbs misfires.
- **Enum every closed set:** `units: "celsius" | "fahrenheit"`, never bare `string`.
- **Describe every field**, mark only the true minimum as required.
- **Atomic over monolithic:** one tight tool beats a `do_everything(action, ...)` switch.

### Security note (trust boundary)
Tool *descriptions* are untrusted input to the LLM — "tool poisoning" hides instructions
in them. We own this server so the risk is low, but the principle informs the SOLUTION:
the agent should treat tool metadata and tool outputs as data, never as instructions,
and we keep weather tools read-only/idempotent (no consequential actions to gate).

---

## 2. Open-Meteo integration (verified facts)

No API key required. Two endpoints, two steps: geocode the name, then fetch weather.

**Geocoding** — `GET https://geocoding-api.open-meteo.com/v1/search`
- Params: `name` (required, 2+ chars), `count`, `language`, `countryCode`.
- Response: `{ "results": [ { id, name, latitude, longitude, country, country_code,
  admin1, timezone, ... } ] }`. **`results` is absent/empty when nothing matches** —
  that is our `LocationNotFoundError` signal.
- Example: `.../v1/search?name=Berlin&count=1&language=en`

**Current weather** — `GET https://api.open-meteo.com/v1/forecast`
- Params: `latitude`, `longitude`, `current=temperature_2m,wind_speed_10m,weather_code`,
  `temperature_unit=celsius|fahrenheit`, `wind_speed_unit=kmh|ms|mph|kn`, `timezone=auto`.
- Response: `{ "current": { time, temperature_2m, wind_speed_10m, weather_code },
  "current_units": { temperature_2m: "°C", wind_speed_10m: "km/h", ... } }`.
- Units come back in `current_units` — include them in the tool output as required.

**WMO `weather_code` → description** (we own this mapping in the service layer):
`0` clear sky · `1-3` mainly clear / partly cloudy / overcast · `45,48` fog ·
`51,53,55` drizzle · `56,57` freezing drizzle · `61,63,65` rain (slight/moderate/heavy) ·
`66,67` freezing rain · `71,73,75` snowfall · `77` snow grains · `80-82` rain showers ·
`85,86` snow showers · `95` thunderstorm · `96,99` thunderstorm with hail.

Ambiguous names (e.g. "Springfield") return multiple results — we take the top-ranked
and echo the resolved `name, admin1, country` in the output so user and LLM see what was
resolved. Documented as a known limitation.

---

## 3. The agent loop (Part 2)

### Decision: a clean, bounded tool-calling loop — not a router/workflow
Anthropic's workflow patterns (prompt-chaining, routing, parallelization,
orchestrator-workers, evaluator-optimizer) are cheaper and more auditable *when steps are
enumerable in advance*. A weather agent's steps are **not** pre-enumerable: the user types
free text, and the exercise explicitly requires the LLM to *decide* which discovered tool
to call. So the right shape is the canonical agent loop (native tool use), kept small and
bounded. (We note the workflow-vs-agent trade-off in SOLUTION.md — it shows we chose
deliberately rather than by default.)

### Loop shape (ReAct / native tool use)
```
append user message
loop (max N iterations, e.g. 8):
    turn = provider.chat(messages, tools)
    if turn has tool calls:
        for each call: result = mcp_gateway.call(name, args)   # observe
        append assistant(tool_calls) + tool results to messages
        continue
    else:
        return turn.text                                       # model chose to stop
return "stopped: iteration budget reached"
```
Load-bearing details from the agent lessons:
- **Hard iteration cap** prevents runaway loops.
- **Never raise tool errors into the loop** — convert them to observation strings the
  model can read and recover from (e.g. "location not found: try a more specific name").
- **Correlate tool calls by id** when a turn emits several (both SDKs supply ids).
- **Conversation context** = the growing message buffer; that satisfies the follow-up
  requirement, kept in memory per session.

### Provider abstraction (the central SOLID demonstration)
The loop depends only on an `LLMProvider` interface (DIP). Concrete `AnthropicProvider`
and `OpenAIProvider` translate between a neutral message/tool-call shape and each SDK
(OCP — new provider = new adapter, loop untouched). A factory selects by `LLM_PROVIDER`
env var (Strategy + Factory). We deliberately avoid an aggregator like LiteLLM: it would
hide the very abstraction we are being asked to demonstrate and add a heavy dependency.

---

## 4. Engineering discipline we adopt (from `mattpocock/skills`)

Curated to fit a 2–3h exercise judged on clean architecture + communication. We adopt
the high-signal, low-overhead practices and consciously *defer* the heavy autonomous-agent
machinery (it would be over-engineering here).

**Adopt:**
- **Spec-driven via OpenSpec** — proposal → design → specs → tasks before code (already
  in place). This is our PRD/issue layer.
- **CONTEXT.md ubiquitous language** — a short domain glossary (Location, WeatherReport,
  Provider, Gateway, Tool…) so naming is consistent across code and docs.
- **ADRs** (`docs/adr/`) for the 2–3 hard-to-reverse, surprising decisions: official SDK
  vs hand-rolled, provider abstraction vs aggregator, stdio transport.
- **Deep modules** (Ousterhout): small interfaces over rich implementation; apply the
  "deletion test" — a module earns its place if deleting it would scatter complexity.
- **TDD discipline:** red-green-refactor in vertical slices; tests exercise *public
  interfaces*, survive internal refactors, no mocking of internal collaborators. Inject
  fakes for httpx and the LLM provider so tests need no network or API keys.
- **A single verification command** (`make check` / `just check` → ruff + pytest) as our
  deterministic "definition of done."

**Defer (great for a long-running autonomous agent platform; cite in "next steps"):**
agent-workbench state files (`agent_state.json`/`task_board.json`), scope contracts,
deterministic verification gates, and reviewer-agent rubrics. They shine for AFK,
multi-session agent work — not for a small, reviewer-read exercise, where they would add
ceremony without proportional value.

---

## 5. Sources

- Official MCP Python SDK — github.com/modelcontextprotocol/python-sdk (server/client API).
- Open-Meteo Geocoding & Forecast docs — open-meteo.com/en/docs (endpoints, units, WMO).
- `rohitg00/ai-engineering-from-scratch` — phases 13 (MCP) & 14 (agent engineering).
- `mattpocock/skills` — engineering skills (tdd, to-prd, improve-codebase-architecture, …).
