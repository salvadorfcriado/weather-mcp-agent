# 0002 — Own `LLMProvider` abstraction instead of an aggregator library

**Status:** accepted

## Context
The agent must work with both Anthropic and OpenAI, selected at runtime. We could adopt an
aggregator (e.g. LiteLLM) that unifies many providers behind one call, or define our own
small `LLMProvider` interface with one adapter per provider.

## Decision
Define an `LLMProvider` interface (provider-neutral message + tool-call types) with
`AnthropicProvider` and `OpenAIProvider` adapters, chosen by a factory reading the
`LLM_PROVIDER` env var (Strategy + Factory). The agent loop depends only on the interface.

## Why (alternatives considered)
- **Aggregator (LiteLLM, etc.)** — rejected: it hides the very abstraction this exercise
  asks us to demonstrate (DIP/OCP), adds a heavy dependency, and we'd inherit someone
  else's tool-call normalization and its license surface.
- **Code directly against one SDK** — rejected: couples the loop to a vendor, breaking
  Open/Closed; adding a provider would mean editing the loop.

## Consequences
- (+) Adding a provider = one new adapter; the agent loop never changes (OCP).
- (+) The loop is unit-testable with a fake `LLMProvider` — no API keys, no network.
- (+) Clear, visible demonstration of DIP — the central architectural signal here.
- (−) We maintain the translation between our neutral types and each SDK's tool-call shape;
  contained at the adapter boundary and covered by tests.
