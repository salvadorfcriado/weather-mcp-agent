"""Shared pytest fixtures: fakes at the ports so tests need no network or API keys."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest


@pytest.fixture
def make_http() -> Callable[[Callable[[httpx.Request], httpx.Response]], httpx.AsyncClient]:
    """Build an `httpx.AsyncClient` driven by a request→response handler.

    Exercises the real httpx request building and our response parsing without hitting
    the network.
    """

    def _build(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
        return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    return _build
