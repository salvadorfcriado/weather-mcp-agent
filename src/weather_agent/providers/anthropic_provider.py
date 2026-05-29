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


def _tool_result_block(turn: ToolResultMessage) -> dict[str, Any]:
    return {
        "type": "tool_result",
        "tool_use_id": turn.tool_call_id,
        "content": turn.content,
        "is_error": turn.is_error,
    }


def _message_to_anthropic(message: Message) -> dict[str, Any]:
    if message.role == Role.USER:
        return {"role": "user", "content": message.text}

    content: list[dict[str, Any]] = []
    if message.text:
        content.append({"type": "text", "text": message.text})
    for call in message.tool_calls:
        content.append(
            {"type": "tool_use", "id": call.id, "name": call.name, "input": call.arguments}
        )
    if not content:
        # Anthropic rejects an empty content array; keep the message valid.
        content.append({"type": "text", "text": "(no content)"})
    return {"role": "assistant", "content": content}


def _to_anthropic_messages(turns: list[Turn]) -> list[dict[str, Any]]:
    """Translate the neutral transcript to Anthropic messages.

    The outcomes of a single assistant turn's tool calls arrive as one
    `ToolResultMessage` each. The Messages API requires them in a single user message
    with one `tool_result` block per call (it rejects consecutive same-role messages),
    so coalesce any run of consecutive tool results into one user message.
    """
    messages: list[dict[str, Any]] = []
    pending_results: list[dict[str, Any]] = []

    def flush_pending() -> None:
        if pending_results:
            messages.append({"role": "user", "content": list(pending_results)})
            pending_results.clear()

    for turn in turns:
        if isinstance(turn, ToolResultMessage):
            pending_results.append(_tool_result_block(turn))
            continue
        flush_pending()
        messages.append(_message_to_anthropic(turn))

    flush_pending()
    return messages


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
        a_messages = _to_anthropic_messages(messages)
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
