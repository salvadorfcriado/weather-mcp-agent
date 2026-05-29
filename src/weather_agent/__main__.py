"""Entrypoint for the chat agent — runs the terminal REPL.

    uv run weather-agent

The Chainlit web UI is a separate entrypoint over the same agent:

    uv run chainlit run src/weather_agent/ui/web.py
"""

from __future__ import annotations

from weather_agent.ui.repl import main

if __name__ == "__main__":
    main()
