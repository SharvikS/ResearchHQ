"""Verbosity-aware logging setup. Hides noisy HTTP libs unless --debug."""

from __future__ import annotations

import logging

_HTTP_LOGGERS = (
    "httpx", "httpcore", "urllib3", "requests", "ddgs", "primp",
    "asyncio", "google", "groq", "ollama", "openai", "anthropic",
)


def configure(verbosity: str) -> None:
    """verbosity in {'quiet','normal','verbose','debug'}."""
    level_map = {
        "quiet": logging.ERROR,
        "normal": logging.WARNING,
        "verbose": logging.INFO,
        "debug": logging.DEBUG,
    }
    level = level_map.get(verbosity, logging.WARNING)

    root = logging.getLogger()
    # Only configure once. Reuse existing handlers if any so we don't double-print.
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(handler)
    root.setLevel(level)

    # Hide HTTP/library noise unless debug.
    http_level = logging.DEBUG if verbosity == "debug" else logging.WARNING
    if verbosity != "debug":
        http_level = logging.ERROR
    for name in _HTTP_LOGGERS:
        logging.getLogger(name).setLevel(http_level)

    # Our own loggers should follow root.
    logging.getLogger("researchhq").setLevel(level)
