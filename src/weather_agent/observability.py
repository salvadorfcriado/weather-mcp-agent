"""Observability seam: a `Tracer` port plus a structured-logging implementation.

The agent loop reports each step through `Tracer.span`. `LoggingTracer` ships by
default. Another backend (e.g. Langfuse) is a new `Tracer` implementation — no change to
the loop. No secrets or raw payloads are logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Protocol


class Tracer(Protocol):
    """Records a unit of work (a span) with attributes and elapsed time."""

    def span(self, name: str, **attributes: Any) -> Any:
        """Context manager wrapping a step; records name, attributes, and duration."""
        ...


class LoggingTracer:
    """Default tracer: emits one structured log line per span with its duration."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._log = logger or logging.getLogger("weather_agent.trace")

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        start = time.monotonic()
        ok = True
        try:
            yield
        except Exception:
            ok = False
            raise
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            self._log.info(
                "span=%s ok=%s elapsed_ms=%.0f attrs=%s", name, ok, elapsed_ms, attributes
            )


class NullTracer:
    """No-op tracer (useful in tests or when tracing is disabled)."""

    @contextmanager
    def span(self, name: str, **attributes: Any) -> Iterator[None]:
        yield
