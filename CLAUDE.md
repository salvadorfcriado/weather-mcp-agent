# CLAUDE.md — Weather MCP Agent

Short router for any AI assistant (Claude, Cursor) working in this repo. Read the linked
docs on demand; don't duplicate their content here.

## What this is
A weather agent built on the Model Context Protocol, as a time-boxed engineering exercise. Two parts: an **MCP weather server**
(`src/weather_mcp/`, Part 1) and a **provider-agnostic chat agent** (`src/weather_agent/`,
Part 2). Scope and trade-offs: [`SOLUTION.md`](SOLUTION.md).

## Where things live
- [`docs/CONTEXT.md`](docs/CONTEXT.md) — domain glossary (use this vocabulary in code & docs).
- [`docs/RESEARCH.md`](docs/RESEARCH.md) — verified foundations + sources for decisions.
- [`docs/adr/`](docs/adr/) — the hard-to-reverse decisions and their rationale.
- `openspec/changes/` — the active spec (proposal → design → specs → tasks).
- `SOLUTION.md` — the reviewer-facing deliverable (written last).

## How we work
- **Spec-driven (OpenSpec):** no feature code before its change has design + tasks.
- **Co-decide:** present options + a recommendation, then wait for the maintainer's pick.
- **TDD:** red → green → refactor in vertical slices. Tests hit public interfaces, use
  injected fakes (no network, no API keys). 
- **Definition of done:** `make check` (ruff + pytest) exits 0.

## Architecture principles (what matters most)
- **SOLID, applied.** The agent loop depends on the `LLMProvider` and `MCPGateway`
  abstractions only (DIP); a new provider is a new adapter, loop untouched (OCP).
- **Clean layering.** `domain/` is pure (no MCP, no httpx). The two packages never import
  each other — they talk only over MCP.
- **Typed graceful errors;** never leak stack traces to the user or the LLM.
- **No secrets in code** — all config via env (`pydantic-settings`); `.env` is git-ignored.
- **Permissive licenses only** (MIT/BSD/Apache-2.0).
