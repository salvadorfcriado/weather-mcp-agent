## 1. Project setup

- [x] 1.1 Add runtime deps to `pyproject.toml` (`chainlit`) and confirm dev deps; refresh `uv.lock` with `uv lock`
- [x] 1.2 `uv sync --extra dev` and confirm `make check` runs (ruff + pytest) on the empty tree
- [x] 1.3 Add `tests/conftest.py` fixtures: fake httpx transport, fake `LLMProvider`, fake `MCPGateway`

## 2. MCP server — domain (Part 1, no I/O)

- [x] 2.1 `domain/models.py`: `GeocodedLocation`, `WeatherReport` (pydantic) — pure, no wire formats
- [x] 2.2 `domain/errors.py`: `LocationNotFoundError`, `UpstreamWeatherError`
- [x] 2.3 `wmo.py`: WMO `weather_code` → description map (+ unit tests)

## 3. MCP server — clients & caching

- [x] 3.1 `clients/base.py`: `GeocodingClient` / `WeatherClient` Protocols
- [x] 3.2 `clients/open_meteo.py`: async httpx implementations (geocoding + current weather); map non-success/timeout to `UpstreamWeatherError`, empty results to `LocationNotFoundError` (tests via fake transport)
- [x] 3.3 `clients/cache.py`: `CachedGeocodingClient` (session) + `CachedWeatherClient` (TTL) Decorators (tests: cache hit, TTL expiry, TTL=0 disables)

## 4. MCP server — service & tool

- [x] 4.1 `service.py`: `WeatherService` orchestrates geocode → fetch → map to `WeatherReport`, raising typed errors (tests with fake clients, incl. both error paths)
- [x] 4.2 `server.py`: register `get_current_weather` on FastMCP — schema (location + `units` enum `metric|imperial`, default `metric`, mapped to Open-Meteo `temperature_unit`/`wind_speed_unit`), description ("Use when… Do not use for…"), map domain result/errors to MCP tool output (`isError`)
- [x] 4.3 `__main__.py`: build cached clients → service → server; `main()` runs over stdio
- [x] 4.4 Smoke-test the server via an in-process MCP client: list tools, call with a known and an unknown location

## 5. LLM provider abstraction (Part 2)

- [ ] 5.1 `providers/base.py`: neutral types (`Message`, `ToolSpec`, `ToolCall`, `ToolResultMessage`) + `LLMProvider` interface with a streaming `chat()`
- [ ] 5.2 `providers/anthropic_provider.py`: adapter translating neutral ⇄ Anthropic (incl. tool-use + streaming) (tests with a stubbed SDK client)
- [ ] 5.3 `config.py` (pydantic-settings) + `providers/factory.py`: select by `LLM_PROVIDER` (registered: `anthropic`), fail fast on missing key, reject unknown provider naming supported values (tests)

## 6. Agent core

- [ ] 6.1 `mcp_gateway.py`: launch server via stdio, `initialize`, discover tools, `call_tool`; expose tool specs + a `call(name, args)`; surface tool errors as data
- [ ] 6.2 `observability.py`: `Tracer` seam + `LoggingTracer` (structured logging of provider/tool steps + latency; no secrets)
- [ ] 6.3 `agent.py`: `AgentSession.send()` bounded loop yielding `AgentEvent`s; tool errors → observations; in-session context; honor `AGENT_MAX_ITERATIONS` (tests with fake provider + fake gateway: tool path, follow-up context, iteration cap, error recovery)

## 7. Frontends

- [ ] 7.1 `ui/repl.py`: terminal REPL consuming the event stream (streamed deltas + tool lines, clean exit)
- [ ] 7.2 `ui/web.py`: Chainlit app over the same `AgentSession`, surfacing tool-call steps live
- [ ] 7.3 `weather_agent/__main__.py`: wire config → provider → gateway → agent → REPL; document how to launch the Chainlit UI

## 8. Packaging & docs

- [ ] 8.1 `Dockerfile` + `docker-compose.yml`: one-command run of the agent (spawns the server); document the env file
- [ ] 8.2 `.env.example`: finalize defaults (provider, model names, iteration cap, cache TTL, log level)
- [ ] 8.3 `SOLUTION.md`: language/choices, setup from clean checkout, architecture & trade-offs, dependency licenses, what I'd do next (extra tools, **additional LLM provider adapters e.g. OpenAI** behind the `LLMProvider` port, Langfuse adapter, LLM prompt caching)
- [ ] 8.4 Update `README.md` if commands changed; ensure `docs/` links resolve

## 9. Verification

- [ ] 9.1 `make check` passes (ruff clean, all tests green)
- [ ] 9.2 Manual end-to-end: real LLM key, ask a weather question + a follow-up, in REPL and in Chainlit
- [ ] 9.3 Clean-checkout dry run: fresh clone, `uv sync`, `.env`, run — confirm instructions are complete
- [ ] 9.4 Self-review with `/code-review` (SOLID, separation of concerns) and address findings
