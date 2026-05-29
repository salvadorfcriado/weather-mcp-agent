# 0002 — Own `LLMProvider` abstraction instead of an aggregator library

**Status:** accepted

## Context
The agent must work against a configurable LLM provider, selected at runtime, without
coupling the loop to a vendor SDK. We could adopt an aggregator (e.g. LiteLLM) that unifies
many providers behind one call, or define our own small `LLMProvider` interface with one
adapter per provider.

## Decision
Define an `LLMProvider` interface (provider-neutral message + tool-call types) chosen by a
factory reading the `LLM_PROVIDER` env var (Strategy + Factory); the agent loop depends only
on the interface. This deliverable ships the `AnthropicProvider` adapter; further providers
(e.g. `OpenAIProvider`) are new adapters behind the same port — documented in `SOLUTION.md`
as the OCP extension, not implemented here, to keep scope within the exercise's time box.

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
