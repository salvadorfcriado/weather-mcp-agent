"""Chainlit web frontend over the same agent event stream.

Run with:  uv run chainlit run src/weather_agent/ui/web.py

Like the REPL, this depends only on the agent's public contract; it surfaces tool calls
as Chainlit steps so you can watch the tool-calling loop live.
"""

from __future__ import annotations

import chainlit as cl

from weather_agent.agent import Done, TextDelta, ToolCallStarted, ToolResult
from weather_agent.config import Settings
from weather_agent.logging import configure_logging
from weather_agent.mcp_gateway import MCPGateway
from weather_agent.runtime import build_session


@cl.on_chat_start
async def on_chat_start() -> None:
    settings = Settings()
    configure_logging(settings.log_level)

    gateway = MCPGateway()
    await gateway.__aenter__()  # kept open for the chat session, closed on_chat_end
    session = build_session(settings, gateway)

    cl.user_session.set("gateway", gateway)
    cl.user_session.set("session", session)

    await cl.Message(
        content="🌤️ Hi! Ask me about the current weather anywhere — e.g. *“What's the "
        "weather in Tokyo?”*"
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    session = cl.user_session.get("session")
    reply = cl.Message(content="")
    await reply.send()

    steps: dict[str, cl.Step] = {}
    async for event in session.send(message.content):
        if isinstance(event, TextDelta):
            await reply.stream_token(event.text)
        elif isinstance(event, ToolCallStarted):
            step = cl.Step(name=event.tool, type="tool")
            step.input = event.arguments
            await step.send()
            steps[event.id] = step
        elif isinstance(event, ToolResult):
            step = steps.get(event.id)
            if step is not None:
                step.output = event.summary
                step.is_error = event.is_error
                await step.update()
        elif isinstance(event, Done) and not reply.content:
            reply.content = event.final_text

    await reply.update()


@cl.on_chat_end
async def on_chat_end() -> None:
    gateway = cl.user_session.get("gateway")
    if gateway is not None:
        await gateway.__aexit__(None, None, None)
