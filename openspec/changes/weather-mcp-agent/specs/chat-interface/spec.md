## ADDED Requirements

### Requirement: Terminal REPL frontend
The system SHALL provide a terminal REPL where the user types messages and sees the
agent's responses, consuming the agent's event stream. This is the default, dependency-
light way to run the chat.

#### Scenario: Interactive conversation in the terminal
- **WHEN** the user runs the agent and types a weather question
- **THEN** the response is printed in the terminal, streamed as it is produced, and the
  user can type a follow-up in the same session

#### Scenario: Clean exit
- **WHEN** the user issues an exit command (or EOF)
- **THEN** the REPL shuts down the agent and MCP connection cleanly

### Requirement: Chainlit web UI frontend
The system SHALL provide a Chainlit (Apache-2.0) web chat as an alternative frontend over
the same agent event stream, surfacing tool calls as they happen.

#### Scenario: Web chat shows tool-call progress
- **WHEN** the user asks a weather question in the web UI
- **THEN** the UI streams the answer and visibly indicates when the agent calls a tool and
  when the result returns

### Requirement: Frontends are decoupled from the agent internals
Each frontend SHALL depend only on the agent's public contract (send a message, consume
the event stream). A frontend SHALL NOT import or reference the LLM provider SDKs or the
MCP client directly.

#### Scenario: Adding a frontend needs no agent change
- **WHEN** a new frontend is added over the same agent contract
- **THEN** it requires no change to the agent loop, the providers, or the MCP gateway
