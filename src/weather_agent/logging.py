"""Structured logging setup for the agent (observability).

Logs go to stderr so they never mix with the REPL conversation on stdout.
"""

from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stderr,
        format=_FORMAT,
    )
