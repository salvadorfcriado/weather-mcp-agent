"""Tests for the Anthropic adapter: neutral⇄SDK translation and streaming.

A stubbed SDK client drives the adapter — no network, no API key.
"""

from __future__ import annotations

from types import SimpleNamespace

from weather_agent.providers.anthropic_provider import AnthropicProvider
from weather_agent.providers.base import (
    CompletedTurn,
    Message,
    Role,
    TextDelta,
    ToolCall,
    ToolResultMessage,
    ToolSpec,
)


class _FakeStream:
    def __init__(self, deltas: list[str], final: object) -> None:
        self._deltas = deltas
        self._final = final

    async def __aenter__(self) -> _FakeStream:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    @property
    def text_stream(self):
        async def _gen():
            for delta in self._deltas:
                yield delta

        return _gen()

    async def get_final_message(self) -> object:
        return self._final


class _FakeMessages:
    def __init__(self, deltas: list[str], final: object) -> None:
        self._deltas = deltas
        self._final = final
        self.captured: dict | None = None

    def stream(self, **kwargs: object) -> _FakeStream:
        self.captured = kwargs
        return _FakeStream(self._deltas, self._final)


class _FakeClient:
    def __init__(self, deltas: list[str], final: object) -> None:
        self.messages = _FakeMessages(deltas, final)


def _text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _tool_block(id: str, name: str, input: dict) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id, name=name, input=input)


def _provider(deltas, final) -> tuple[AnthropicProvider, _FakeClient]:
    client = _FakeClient(deltas, final)
    return AnthropicProvider(api_key="x", model="m", client=client), client


async def _collect(aiter):
    return [event async for event in aiter]


async def test_streams_text_then_completed_turn() -> None:
    final = SimpleNamespace(content=[_text_block("Hello!")])
    provider, _ = _provider(["Hel", "lo!"], final)
    events = await _collect(provider.chat([Message(Role.USER, "hi")], [], "sys"))

    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Hel", "lo!"]
    completed = [e for e in events if isinstance(e, CompletedTurn)]
    assert len(completed) == 1
    assert completed[0].message.text == "Hello!"
    assert completed[0].message.tool_calls == ()


async def test_surfaces_tool_calls_as_neutral() -> None:
    final = SimpleNamespace(
        content=[_tool_block("t1", "get_current_weather", {"location": "London"})]
    )
    provider, _ = _provider([], final)
    events = await _collect(provider.chat([Message(Role.USER, "weather?")], [], "sys"))

    completed = next(e for e in events if isinstance(e, CompletedTurn))
    assert completed.message.tool_calls == (
        ToolCall(id="t1", name="get_current_weather", arguments={"location": "London"}),
    )


async def test_empty_assistant_turn_serializes_to_nonempty_content() -> None:
    # Anthropic rejects an empty content array; the adapter must keep it valid.
    final = SimpleNamespace(content=[_text_block("ok")])
    provider, client = _provider([], final)
    await _collect(provider.chat([Message(Role.ASSISTANT, "")], [], "sys"))
    sent = client.messages.captured["messages"]
    assert sent[0]["content"], "assistant content array must not be empty"


async def test_translates_transcript_and_tools_to_anthropic() -> None:
    final = SimpleNamespace(content=[_text_block("ok")])
    provider, client = _provider([], final)
    transcript = [
        Message(Role.USER, "weather in London?"),
        Message(
            Role.ASSISTANT,
            "",
            tool_calls=(ToolCall("t1", "get_current_weather", {"location": "London"}),),
        ),
        ToolResultMessage(tool_call_id="t1", content="14°C", is_error=False),
    ]
    tools = [ToolSpec("get_current_weather", "desc", {"type": "object"})]

    await _collect(provider.chat(transcript, tools, "you are a weather agent"))

    captured = client.messages.captured
    assert captured["system"] == "you are a weather agent"
    assert captured["tools"][0]["name"] == "get_current_weather"
    assert captured["tools"][0]["input_schema"] == {"type": "object"}

    sent = captured["messages"]
    assert sent[0] == {"role": "user", "content": "weather in London?"}
    assert sent[1]["role"] == "assistant"
    assert sent[1]["content"][0] == {
        "type": "tool_use",
        "id": "t1",
        "name": "get_current_weather",
        "input": {"location": "London"},
    }
    assert sent[2]["content"][0]["type"] == "tool_result"
    assert sent[2]["content"][0]["tool_use_id"] == "t1"


async def test_parallel_tool_results_coalesce_into_one_user_message() -> None:
    # A single assistant turn with two tool calls yields two ToolResultMessages; the
    # Messages API requires both tool_results in ONE user message (no consecutive
    # same-role messages), so the adapter must merge them.
    final = SimpleNamespace(content=[_text_block("ok")])
    provider, client = _provider([], final)
    transcript = [
        Message(Role.USER, "compare London and Paris"),
        Message(
            Role.ASSISTANT,
            "",
            tool_calls=(
                ToolCall("t1", "get_current_weather", {"location": "London"}),
                ToolCall("t2", "get_current_weather", {"location": "Paris"}),
            ),
        ),
        ToolResultMessage(tool_call_id="t1", content="14°C", is_error=False),
        ToolResultMessage(tool_call_id="t2", content="18°C", is_error=False),
    ]

    await _collect(provider.chat(transcript, [], "sys"))

    sent = client.messages.captured["messages"]
    # user, assistant(2 tool_use), single user with both tool_results.
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    results = sent[2]["content"]
    assert [b["type"] for b in results] == ["tool_result", "tool_result"]
    assert [b["tool_use_id"] for b in results] == ["t1", "t2"]
