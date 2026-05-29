# 0003 — Cache upstream data with a Decorator over the clients

**Status:** accepted

## Context
Geocoding a name always yields the same coordinates; current weather changes roughly every
~15 minutes. Within a chat session the agent may re-query the same place repeatedly. We
want to avoid redundant HTTP calls (latency, and courtesy to a free API) without
complicating the `WeatherService`.

## Decision
Add `CachedGeocodingClient` / `CachedWeatherClient` that implement the same client
interfaces and wrap a real client (Decorator). Geocoding is cached for the session;
current weather uses a short TTL (`WEATHER_CACHE_TTL_SECONDS`, `0` disables it). Caching is
wired in the factory; stdlib only, no new dependency.

## Why (alternatives considered)
- **Cache inside `WeatherService`** — rejected: mixes caching with orchestration, violating
  SRP and making the service harder to test.
- **External cache (Redis/Memcached)** — rejected: operational overhead unjustified for a
  local single-process tool; also a heavier dependency/license surface.
- **LLM prompt caching** — out of scope (deferred to "next steps"): marginal benefit for
  short conversations and provider-specific.

## Consequences
- (+) Open/Closed: caching added without touching the real clients or the service (which
  depend on the interface, so they can't tell the difference — Liskov).
- (+) Testable in isolation; tests can inject the un-cached client.
- (−) In-process cache only — not shared across processes; acceptable for this scope.
