"""The `LLMProvider` port and its provider-neutral types.

Everything the agent loop needs to talk to an LLM, with no vendor SDK types leaking
out. Adapters (e.g. Anthropic) translate between these types and a concrete SDK.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


@dataclass(frozen=True)
class ToolSpec:
    """A tool the model may call, as discovered from the MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """A model's request to invoke a tool."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Message:
    """A user or assistant message. Assistant messages may carry tool calls."""

    role: Role
    text: str = ""
    tool_calls: tuple[ToolCall, ...] = ()


@dataclass(frozen=True)
class ToolResultMessage:
    """The outcome of a tool call, fed back to the model as an observation."""

    tool_call_id: str
    content: str
    is_error: bool = False


# A transcript entry.
Turn = Message | ToolResultMessage


# --- Streaming events yielded by LLMProvider.chat() ---


@dataclass(frozen=True)
class TextDelta:
    """An incremental chunk of assistant text as the model produces it."""

    text: str


@dataclass(frozen=True)
class CompletedTurn:
    """Emitted once the turn finishes: the full assembled assistant message."""

    message: Message


ProviderEvent = TextDelta | CompletedTurn


class LLMProvider(Protocol):
    """Provider-neutral chat with tool-calling, streamed.

    Implementations translate to/from a vendor SDK. The streaming contract is identical
    across adapters, so no consumer depends on a vendor's streaming format.
    """

    def chat(
        self,
        messages: list[Turn],
        tools: list[ToolSpec],
        system: str,
    ) -> AsyncIterator[ProviderEvent]:
        """Stream the next assistant turn: text deltas, then one CompletedTurn."""
        ...
