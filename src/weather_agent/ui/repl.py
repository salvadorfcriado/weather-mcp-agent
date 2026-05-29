"""Terminal REPL frontend — consumes the agent's event stream.

Thin I/O only: it renders events and reads input. It knows nothing about the LLM or MCP.
"""

from __future__ import annotations

import asyncio
from typing import Any

from weather_agent.agent import Done, TextDelta, ToolCallStarted, ToolResult
from weather_agent.config import Settings
from weather_agent.logging import configure_logging
from weather_agent.mcp_gateway import MCPGateway
from weather_agent.runtime import build_session

_BANNER = (
    "🌤  Weather agent — ask about the current weather anywhere.\n"
    "    Type your question, or 'exit' to quit.\n"
)
_EXIT = {"exit", "quit", ":q"}


def _fmt_args(arguments: dict[str, Any]) -> str:
    return ", ".join(f"{key}={value!r}" for key, value in arguments.items())


def _short(text: str, limit: int = 200) -> str:
    text = text.replace("\n", " ")
    return text if len(text) <= limit else text[:limit] + "…"


async def _read(prompt: str) -> str:
    return await asyncio.to_thread(input, prompt)


async def run() -> None:
    settings = Settings()
    configure_logging(settings.log_level)
    print(_BANNER)

    async with MCPGateway() as gateway:
        session = build_session(settings, gateway)
        while True:
            try:
                user_text = (await _read("you ▸ ")).strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            if not user_text:
                continue
            if user_text.lower() in _EXIT:
                break

            streamed = False
            print("bot ▸ ", end="", flush=True)
            async for event in session.send(user_text):
                if isinstance(event, TextDelta):
                    print(event.text, end="", flush=True)
                    streamed = True
                elif isinstance(event, ToolCallStarted):
                    print(f"\n  ⟳ {event.tool}({_fmt_args(event.arguments)})", flush=True)
                elif isinstance(event, ToolResult):
                    mark = "✗" if event.is_error else "✓"
                    print(f"  {mark} {_short(event.summary)}", flush=True)
                elif isinstance(event, Done) and not streamed:
                    print(event.final_text, end="", flush=True)
            print("\n")

    print("bye! 👋")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
