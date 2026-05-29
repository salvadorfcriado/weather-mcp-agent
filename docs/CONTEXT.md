# Context — domain language

The shared vocabulary for this project. Use these exact terms in code, commits, and docs
so names stay consistent. Definitions describe what a thing *is*, not how it's built.

## Language

**Location**:
A human-readable place name the user types (e.g. "London", "New York, NY"). Untrusted,
ambiguous free text — not yet coordinates.
_Avoid_: city, query, place string.

**GeocodedLocation**:
A `Location` resolved to coordinates plus identifying context (name, latitude, longitude,
country, admin region). The output of geocoding; the input to a weather lookup.
_Avoid_: coords, point, geo.

**WeatherReport**:
The domain value object describing current conditions at a `GeocodedLocation`:
temperature, wind speed, a human description, and their units. Independent of Open-Meteo's
wire format and of MCP.
_Avoid_: forecast, weather data, result.

**GeocodingClient / WeatherClient**:
Interfaces (typing.Protocol) for the two upstream calls. Implementations: `OpenMeteo*`
(real HTTP) and `Cached*` (decorator). The `WeatherService` depends on the interfaces.
_Avoid_: API, fetcher, repository.

**WeatherService**:
The server-side orchestrator: geocode → fetch weather → map to a `WeatherReport`, raising
typed errors. The single place that knows the steps. Holds no transport or HTTP detail.
_Avoid_: manager, handler, controller.

**Tool**:
An MCP-exposed capability the LLM can invoke (e.g. `get_current_weather`). Defined by the
server, discovered by the client. Treated as data, never as instructions.
_Avoid_: function, command, endpoint.

**MCPGateway**:
The agent-side wrapper around the MCP client session: launches the server, discovers
`Tool`s dynamically, and invokes them. Isolates MCP transport from the agent loop.
_Avoid_: client, connection, mcp.

**LLMProvider**:
The provider-neutral interface the agent talks to for chat + tool-calling. Shipped
adapter: `AnthropicProvider` (an `OpenAIProvider` is a documented extension, not shipped).
The agent never imports a vendor SDK.
_Avoid_: model, llm, client, backend.

**Agent loop**:
The bounded cycle: send conversation + tools to the `LLMProvider` → if it requests tool
calls, invoke them via the `MCPGateway` and feed results back → else return the final
text. Capped by a max-iterations budget.
_Avoid_: chain, pipeline, runner.

**Conversation context**:
The in-memory, per-session message history that lets the agent answer follow-ups. Not
persisted across sessions.
_Avoid_: memory, state, session store.
