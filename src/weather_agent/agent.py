"""The bounded LLM tool-calling loop.

`AgentSession.send()` streams typed `AgentEvent`s. It depends only on the `LLMProvider`,
`ToolGateway`, and `Tracer` abstractions — no SDK or transport detail — so it is fully
unit-testable with fakes. Conversation context is kept in memory for the session.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from weather_agent.mcp_gateway import ToolGateway, ToolOutcome
from weather_agent.observability import NullTracer, Tracer
from weather_agent.providers.base import (
    CompletedTurn,
    LLMProvider,
    Message,
    Role,
    ToolCall,
    ToolResultMessage,
    Turn,
)
from weather_agent.providers.base import TextDelta as ProviderTextDelta

SYSTEM_PROMPT = (
    "You are a concise weather assistant. When the user asks about current weather, "
    "temperature, or wind for a place, you MUST call the get_current_weather tool to "
    "fetch real data rather than guessing. When you call the tool, pass the location's "
    "common English name (e.g. 'New York', not 'Nueva York'; 'London', not 'Londres'), "
    "since the geocoder works best in English. Reply in the same language the user wrote "
    "in. Use the conversation so far to resolve follow-up questions (e.g. 'and tomorrow?' "
    "or 'what about Paris?'). If a location cannot be found, ask the user to clarify. "
    "Keep answers short and friendly."
)


# --- Agent events (UI-neutral) ---


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCallStarted:
    id: str
    tool: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    id: str
    summary: str
    is_error: bool


@dataclass(frozen=True)
class Done:
    final_text: str


AgentEvent = TextDelta | ToolCallStarted | ToolResult | Done


class AgentSession:
    """Holds one conversation and runs the tool-calling loop per user message."""

    def __init__(
        self,
        provider: LLMProvider,
        gateway: ToolGateway,
        tracer: Tracer | None = None,
        *,
        max_iterations: int = 8,
        system_prompt: str = SYSTEM_PROMPT,
    ) -> None:
        self._provider = provider
        self._gateway = gateway
        self._tracer = tracer or NullTracer()
        self._max_iterations = max_iterations
        self._system = system_prompt
        self._history: list[Turn] = []

    async def send(self, user_text: str) -> AsyncIterator[AgentEvent]:
        """Run one user turn to completion, streaming events as they happen."""
        self._history.append(Message(role=Role.USER, text=user_text))

        for _ in range(self._max_iterations):
            # Stream the assistant turn: re-emit text deltas, capture the final message.
            assistant: Message | None = None
            with self._tracer.span("llm.chat"):
                stream = self._provider.chat(self._history, self._gateway.tools, self._system)
                async for event in stream:
                    if isinstance(event, ProviderTextDelta):
                        yield TextDelta(text=event.text)
                    elif isinstance(event, CompletedTurn):
                        assistant = event.message
            if assistant is None:  # provider always ends with CompletedTurn
                assistant = Message(role=Role.ASSISTANT, text="")
            self._history.append(assistant)

            if not assistant.tool_calls:
                yield Done(final_text=assistant.text)
                return

            for call in assistant.tool_calls:
                yield ToolCallStarted(id=call.id, tool=call.name, arguments=call.arguments)

            outcomes = await asyncio.gather(
                *(self._invoke_tool(call) for call in assistant.tool_calls)
            )

            for call, outcome in zip(assistant.tool_calls, outcomes, strict=True):
                yield ToolResult(id=call.id, summary=outcome.content, is_error=outcome.is_error)
                self._history.append(
                    ToolResultMessage(
                        tool_call_id=call.id,
                        content=outcome.content,
                        is_error=outcome.is_error,
                    )
                )

        yield Done(
            final_text="I couldn't finish that within the allowed number of steps. "
            "Please try rephrasing your question."
        )

    async def _invoke_tool(self, call: ToolCall) -> ToolOutcome:
        with self._tracer.span("tool.call", tool=call.name):
            return await self._gateway.call(call.name, call.arguments)
