"""Tests for the agent loop, with a fake provider and fake gateway (no network)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from weather_agent.agent import AgentSession, Done, TextDelta, ToolCallStarted, ToolResult
from weather_agent.mcp_gateway import ToolOutcome
from weather_agent.providers.base import (
    CompletedTurn,
    Message,
    ProviderEvent,
    Role,
    ToolCall,
    ToolSpec,
    Turn,
)
from weather_agent.providers.base import TextDelta as ProviderTextDelta

WEATHER_TOOL = ToolSpec("get_current_weather", "desc", {"type": "object"})


def text_turn(text: str, deltas: list[str] | None = None) -> tuple[list[str], Message]:
    return deltas or [], Message(role=Role.ASSISTANT, text=text)


def tool_turn(call: ToolCall) -> tuple[list[str], Message]:
    return [], Message(role=Role.ASSISTANT, text="", tool_calls=(call,))


class FakeProvider:
    """Replays scripted turns; repeats the last one if the script is exhausted."""

    def __init__(self, script: list[tuple[list[str], Message]]) -> None:
        self._script = list(script)
        self.seen_histories: list[list[Turn]] = []
        self.seen_tools: list[list[ToolSpec]] = []

    async def chat(
        self, messages: list[Turn], tools: list[ToolSpec], system: str
    ) -> AsyncIterator[ProviderEvent]:
        self.seen_histories.append(list(messages))
        self.seen_tools.append(list(tools))
        deltas, message = self._script[0] if len(self._script) == 1 else self._script.pop(0)
        for delta in deltas:
            yield ProviderTextDelta(text=delta)
        yield CompletedTurn(message=message)


class FakeGateway:
    def __init__(self, outcome: ToolOutcome, tools: list[ToolSpec] | None = None) -> None:
        self._outcome = outcome
        self._tools = tools or [WEATHER_TOOL]
        self.calls: list[tuple[str, dict]] = []

    @property
    def tools(self) -> list[ToolSpec]:
        return self._tools

    async def call(self, name: str, arguments: dict) -> ToolOutcome:
        self.calls.append((name, arguments))
        return self._outcome


async def _collect(session: AgentSession, text: str) -> list:
    return [event async for event in session.send(text)]


async def test_weather_question_calls_tool_then_answers() -> None:
    call = ToolCall("t1", "get_current_weather", {"location": "London"})
    provider = FakeProvider([tool_turn(call), text_turn("It's 14°C and clear in London.")])
    gateway = FakeGateway(ToolOutcome(content="14°C, Clear sky", is_error=False))
    session = AgentSession(provider, gateway)

    events = await _collect(session, "weather in London?")

    assert any(isinstance(e, ToolCallStarted) and e.tool == "get_current_weather" for e in events)
    assert gateway.calls == [("get_current_weather", {"location": "London"})]
    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert tool_results and tool_results[0].is_error is False
    done = events[-1]
    assert isinstance(done, Done) and "London" in done.final_text


async def test_streams_text_deltas() -> None:
    provider = FakeProvider([text_turn("Hello there", deltas=["Hello", " there"])])
    session = AgentSession(provider, FakeGateway(ToolOutcome("x", False)))
    events = await _collect(session, "hi")
    assert [e.text for e in events if isinstance(e, TextDelta)] == ["Hello", " there"]


async def test_follow_up_uses_prior_context() -> None:
    provider = FakeProvider([text_turn("first"), text_turn("second")])
    session = AgentSession(provider, FakeGateway(ToolOutcome("x", False)))
    await _collect(session, "weather in London?")
    await _collect(session, "and tomorrow?")

    # The second provider call must include the earlier user turn in its history.
    second_history = provider.seen_histories[1]
    user_texts = [m.text for m in second_history if isinstance(m, Message) and m.role == Role.USER]
    assert "weather in London?" in user_texts
    assert "and tomorrow?" in user_texts


async def test_iteration_budget_is_enforced() -> None:
    call = ToolCall("t1", "get_current_weather", {"location": "London"})
    provider = FakeProvider([tool_turn(call)])  # repeats → always wants a tool call
    gateway = FakeGateway(ToolOutcome("14°C", False))
    session = AgentSession(provider, gateway, max_iterations=3)

    events = await _collect(session, "loop forever")

    assert len(gateway.calls) == 3
    done = events[-1]
    assert isinstance(done, Done) and "allowed number of steps" in done.final_text


async def test_parallel_tool_calls_in_one_turn_all_execute_in_order() -> None:
    calls = (
        ToolCall("t1", "get_current_weather", {"location": "London"}),
        ToolCall("t2", "get_current_weather", {"location": "Paris"}),
    )
    provider = FakeProvider(
        [([], Message(Role.ASSISTANT, "", tool_calls=calls)), text_turn("compared")]
    )
    gateway = FakeGateway(ToolOutcome("ok", False))
    session = AgentSession(provider, gateway)

    events = await _collect(session, "compare London and Paris")

    # Both tools ran; results are emitted in the calls' original order (ids line up).
    assert [args["location"] for _, args in gateway.calls] == ["London", "Paris"]
    assert [e.id for e in events if isinstance(e, ToolResult)] == ["t1", "t2"]


async def test_tool_error_becomes_observation_and_recovers() -> None:
    call = ToolCall("t1", "get_current_weather", {"location": "Atlantis"})
    provider = FakeProvider(
        [tool_turn(call), text_turn("I couldn't find Atlantis — can you clarify?")]
    )
    gateway = FakeGateway(ToolOutcome(content="Location not found", is_error=True))
    session = AgentSession(provider, gateway)

    events = await _collect(session, "weather in Atlantis?")

    tool_results = [e for e in events if isinstance(e, ToolResult)]
    assert tool_results[0].is_error is True
    done = events[-1]
    assert isinstance(done, Done) and "clarify" in done.final_text.lower()
    # The error was fed back to the provider as a tool-result message.
    from weather_agent.providers.base import ToolResultMessage

    second_history = provider.seen_histories[1]
    assert any(isinstance(m, ToolResultMessage) and m.is_error for m in second_history)
