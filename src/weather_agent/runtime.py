"""Composition root: assemble an AgentSession from settings and an open gateway.

Shared by both frontends so wiring lives in one place.
"""

from __future__ import annotations

from weather_agent.agent import AgentSession
from weather_agent.config import Settings
from weather_agent.mcp_gateway import ToolGateway
from weather_agent.observability import LoggingTracer
from weather_agent.providers.factory import build_provider


def build_session(settings: Settings, gateway: ToolGateway) -> AgentSession:
    return AgentSession(
        build_provider(settings),
        gateway,
        LoggingTracer(),
        max_iterations=settings.agent_max_iterations,
    )
