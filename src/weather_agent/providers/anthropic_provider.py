"""Anthropic adapter for the `LLMProvider` port.

Translates the provider-neutral types to/from the Anthropic Messages API and streams
text deltas, surfacing tool-use requests as neutral `ToolCall`s when the turn completes.
The SDK client is injectable so tests can drive it without network or keys.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

from weather_agent.providers.base import (
    CompletedTurn,
    Message,
    ProviderEvent,
    Role,
    TextDelta,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
    Turn,
)


def _to_anthropic(turn: Turn) -> dict[str, Any]:
    if isinstance(turn, ToolResultMessage):
        return {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": turn.tool_call_id,
                    "content": turn.content,
                    "is_error": turn.is_error,
                }
            ],
        }
    if turn.role == Role.USER:
        return {"role": "user", "content": turn.text}

    content: list[dict[str, Any]] = []
    if turn.text:
        content.append({"type": "text", "text": turn.text})
    for call in turn.tool_calls:
        content.append(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        )
    if not content:
        # Anthropic rejects an empty content array; keep the message valid.
        content.append({"type": "text", "text": "(no content)"})
    return {"role": "assistant", "content": content}


def _from_anthropic(message: Any) -> Message:
    text_parts: list[str] = []
    tool_calls: list[ToolCall] = []
    for block in message.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append(ToolCall(id=block.id, name=block.name, arguments=dict(block.input)))
    return Message(role=Role.ASSISTANT, text="".join(text_parts), tool_calls=tuple(tool_calls))


class AnthropicProvider:
    """`LLMProvider` backed by the Anthropic Messages API (streaming + tool use)."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        client: AsyncAnthropic | None = None,
        max_tokens: int = 1024,
    ) -> None:
        self._client = client or AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def chat(
        self,
        messages: list[Turn],
        tools: list[ToolSpec],
        system: str,
    ) -> AsyncIterator[ProviderEvent]:
        a_messages = [_to_anthropic(turn) for turn in messages]
        a_tools = [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]
        async with self._client.messages.stream(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            tools=a_tools,
            messages=a_messages,
        ) as stream:
            async for text in stream.text_stream:
                yield TextDelta(text=text)
            final = await stream.get_final_message()
        yield CompletedTurn(message=_from_anthropic(final))
