## ADDED Requirements

### Requirement: Provider-neutral LLM interface
The system SHALL define a single `LLMProvider` interface that accepts a conversation
(messages) and a set of available tools and produces an assistant turn — streamed as
provider-neutral text deltas (see "Streaming token output") — that is either text or one
or more tool-call requests. Code that depends on this interface SHALL NOT import or
reference any vendor SDK type.

#### Scenario: Agent depends only on the interface
- **WHEN** the agent loop asks the provider for the next turn
- **THEN** it does so through the `LLMProvider` interface using provider-neutral message
  and tool-call types, with no Anthropic- or OpenAI-specific types in its code

### Requirement: Streaming token output
The `LLMProvider` interface SHALL expose a streaming `chat()` that yields provider-neutral
text deltas as the model produces them and surfaces the turn's tool-call requests, so the
agent can re-emit incremental progress to any frontend. The streaming contract SHALL be
identical across adapters, so no consumer depends on a vendor's streaming format.

#### Scenario: Assistant text is streamed incrementally
- **WHEN** the provider produces an assistant turn that is free text
- **THEN** it yields the text as a sequence of neutral deltas as the model generates them,
  not only a single final block

#### Scenario: Tool calls are surfaced from the stream
- **WHEN** the model requests one or more tool calls during a streamed turn
- **THEN** the provider surfaces them as neutral tool-call requests (name + arguments + id)
  once the turn completes, so the agent can execute them — identical in shape across adapters

### Requirement: Anthropic adapter
The system SHALL provide an `LLMProvider` implementation backed by the Anthropic SDK that
translates between the neutral types and Anthropic's message and tool-use formats.

#### Scenario: Anthropic returns a tool call
- **WHEN** the Anthropic model requests a tool invocation
- **THEN** the adapter returns it as a neutral tool-call (name + arguments + id) the agent
  can execute

### Requirement: Runtime provider selection via a factory
The system SHALL resolve the active provider at runtime from the `LLM_PROVIDER`
environment variable via a factory. Adding a new provider SHALL require only registering a
new adapter behind the `LLMProvider` port — with no change to the agent, gateway, or
frontends. The Anthropic adapter is the provider shipped in this deliverable; further
providers (e.g. OpenAI) are documented as the OCP extension, not implemented here.

#### Scenario: Configured provider is resolved
- **WHEN** `LLM_PROVIDER` selects a registered provider (`anthropic`)
- **THEN** the factory returns the matching adapter and the rest of the system is unchanged

#### Scenario: Unknown provider is rejected
- **WHEN** `LLM_PROVIDER` is set to an unsupported value
- **THEN** the factory raises a clear configuration error naming the supported values

### Requirement: Environment-based configuration with no hard-coded secrets
The system SHALL read provider configuration (API key, model name, optional endpoint)
from the environment and SHALL NOT contain hard-coded secrets. When the selected
provider's API key is missing, startup SHALL fail fast with a clear, actionable message.

#### Scenario: Missing API key fails fast
- **WHEN** the selected provider is chosen but its API key is absent from the environment
- **THEN** the application exits with a clear message stating which variable to set, and
  makes no LLM API call

#### Scenario: No secrets in the repository
- **WHEN** the repository is inspected
- **THEN** no real API keys are present; only `.env.example` with placeholders is tracked,
  and `.env` is git-ignored
