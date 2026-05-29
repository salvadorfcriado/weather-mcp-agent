## ADDED Requirements

### Requirement: Connect to the MCP server and discover tools dynamically
The agent SHALL connect to the weather MCP server as a client and discover the available
tools at runtime. Tool names and schemas SHALL NOT be hard-coded in the agent.

#### Scenario: Tools are discovered at startup
- **WHEN** the agent starts and connects to the server
- **THEN** it lists the server's tools and exposes their schemas to the LLM without any
  tool name hard-coded in the agent

#### Scenario: Tool set drives what the LLM can call
- **WHEN** the server exposes a tool
- **THEN** the agent advertises exactly that tool to the LLM, so adding a server tool
  needs no agent change

### Requirement: Bounded tool-calling loop
The agent SHALL run a loop that sends the conversation and available tools to the
`LLMProvider`; when the model requests tool calls, the agent SHALL invoke them via the MCP
gateway, feed the results back, and continue until the model returns a final answer. The
loop SHALL be bounded by a configurable maximum number of iterations
(`AGENT_MAX_ITERATIONS`).

#### Scenario: A weather question triggers a tool call and a final answer
- **WHEN** the user asks for the weather in a place
- **THEN** the LLM calls `get_current_weather`, the agent executes it via the gateway,
  returns the result to the LLM, and the LLM produces a final natural-language answer

#### Scenario: Iteration budget prevents runaway loops
- **WHEN** the model keeps requesting tool calls without finishing
- **THEN** the loop stops at `AGENT_MAX_ITERATIONS` and returns a clear "stopped" message
  instead of looping forever

### Requirement: Tool errors are returned as observations
When a tool invocation fails or returns an error result, the agent SHALL convert it into
an observation passed back to the model, never raising an exception out of the loop.

#### Scenario: Location-not-found is recoverable
- **WHEN** the tool returns a location-not-found error
- **THEN** the agent feeds that message back to the model as a tool result, allowing the
  model to ask the user to clarify rather than crashing

### Requirement: Maintain in-session conversation context
The agent SHALL retain the conversation history within a session so the user can ask
follow-up questions that depend on earlier turns. Context SHALL NOT be persisted across
process restarts.

#### Scenario: Follow-up question uses prior context
- **WHEN** the user asks "and in Paris?" after asking about another city's current weather
- **THEN** the agent infers the weather intent from the conversation history and calls
  `get_current_weather` for Paris, rather than treating the message as a new, contextless
  request

### Requirement: Emit an event stream
The agent SHALL expose its progress as a stream of typed events — at minimum text deltas,
tool-call-started, tool-result, and done — so any frontend can render progress live. The
agent SHALL NOT depend on any specific frontend.

#### Scenario: Frontend renders streaming progress
- **WHEN** a frontend consumes a turn
- **THEN** it receives incremental text and tool-call events it can display in real time,
  ending with a done event

### Requirement: Observability through an extensible seam
The agent SHALL report loop activity (provider calls, tool invocations with arguments and
outcome, latency) through a `Tracer` seam. A structured-logging tracer SHALL be provided.
Adding another backend (e.g. Langfuse) SHALL require only a new tracer implementation, not
changes to the loop.

#### Scenario: Tool-call flow is traceable
- **WHEN** the agent runs a turn that calls a tool
- **THEN** the tracer records the provider call and the tool invocation with its arguments
  and outcome, via structured logs by default

#### Scenario: Tracer backend is swappable
- **WHEN** a different observability backend is desired
- **THEN** it is added as a new `Tracer` implementation selected by configuration, with no
  change to the agent loop
