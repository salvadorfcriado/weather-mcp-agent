## ADDED Requirements

### Requirement: Expose a current-weather MCP tool
The server SHALL expose an MCP tool named `get_current_weather` over the MCP protocol.
The tool SHALL accept a human-readable `location` string and an optional `units`
parameter constrained to the enum `metric` | `imperial` (default `metric`), where
`metric` yields °C and km/h and `imperial` yields °F and mph. The tool's description SHALL
state when to use it and when not to, so an LLM selects it correctly.

#### Scenario: Tool is discoverable with a typed schema
- **WHEN** an MCP client lists the server's tools
- **THEN** `get_current_weather` appears with a description and an input schema declaring
  `location` (string, required) and `units` (enum metric/imperial, optional)

#### Scenario: Invalid units are rejected by the schema
- **WHEN** the tool is called with `units` outside the allowed enum
- **THEN** the call is rejected as a schema/validation error rather than reaching the
  upstream API

### Requirement: Resolve a human-readable location to coordinates
The server SHALL geocode the `location` string to coordinates using the Open-Meteo
geocoding API before fetching weather.

#### Scenario: Known place resolves
- **WHEN** the tool is called with `location` "London"
- **THEN** the server resolves it to coordinates and includes the resolved name and
  country in the response so the caller can see what was matched

#### Scenario: Ambiguous name resolves to the top match
- **WHEN** the tool is called with an ambiguous `location` that returns several matches
- **THEN** the server uses the top-ranked match and reports the resolved name/region

### Requirement: Return current weather with units
For a resolved location the server SHALL return current temperature, wind speed, and a
human-readable conditions description derived from the WMO weather code, each accompanied
by its unit.

#### Scenario: Successful current-weather lookup
- **WHEN** the tool is called with a valid, resolvable `location`
- **THEN** the response includes temperature, wind speed, and a conditions description,
  each with its unit (e.g. °C, km/h), reflecting the requested `units`

### Requirement: Handle location-not-found gracefully
When geocoding returns no match, the server SHALL return a clear, typed tool result
indicating the location was not found, never an unhandled exception or stack trace.

#### Scenario: Unknown location
- **WHEN** the tool is called with a `location` that geocoding cannot match
- **THEN** the tool returns a result flagged as an error with a human-readable message
  (e.g. "location not found: try a more specific name"), and the process keeps running

### Requirement: Handle upstream failure gracefully
The server SHALL return a clear, typed tool result describing the upstream failure —
never a raw stack trace — when an Open-Meteo request fails (network error, timeout, or
non-success status).

#### Scenario: Upstream API error
- **WHEN** the upstream weather request fails or times out
- **THEN** the tool returns a result flagged as an error with a concise message, and the
  server remains available for subsequent calls

### Requirement: Cache upstream data
The server SHALL cache upstream calls behind the client interfaces: geocoding results for
the lifetime of the process, and current-weather results for a configurable TTL
(`WEATHER_CACHE_TTL_SECONDS`, `0` disables weather caching). Caching SHALL be added
without modifying the orchestrating service.

#### Scenario: Repeated geocoding is served from cache
- **WHEN** the same `location` is requested twice in one session
- **THEN** geocoding is performed once and the second request reuses the cached coordinates

#### Scenario: Weather cache respects its TTL
- **WHEN** the same location's weather is requested again within the TTL
- **THEN** the cached weather is returned without a new upstream call; after the TTL
  expires a fresh call is made

### Requirement: Serve over stdio
The server SHALL run over the MCP stdio transport so a client can launch it as a child
process with no network ports.

#### Scenario: Server starts on stdio
- **WHEN** the server process is launched
- **THEN** it speaks MCP over stdin/stdout and responds to initialize and tool requests
