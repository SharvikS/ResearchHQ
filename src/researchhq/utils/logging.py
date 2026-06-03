"""Verbosity-aware logging setup. Hides noisy HTTP libs unless --debug."""

from __future__ import annotations

import logging
import re

_HTTP_LOGGERS = (
    "httpx",
    "httpcore",
    "urllib3",
    "requests",
    "ddgs",
    "primp",
    "asyncio",
    "google",
    "groq",
    "ollama",
    "openai",
    "anthropic",
)

# Patterns that may carry secrets in third-party debug logs (headers, bodies).
_SECRET_PATTERNS = (
    re.compile(r"(authorization\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(r"(x-api-key\s*[:=]\s*)(\S+)", re.IGNORECASE),
    re.compile(
        r"((?:api[_-]?key|secret|token)\"?\s*[:=]\s*\"?)([A-Za-z0-9_\-]{8,})", re.IGNORECASE
    ),
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,}|gsk_[A-Za-z0-9_\-]{8,})\b"),
)


class _RedactSecretsFilter(logging.Filter):
    """Scrub credential-looking substrings from log messages before they emit.

    SDK HTTP debug logging (enabled at --debug) can otherwise print Authorization
    headers and API keys to the console.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # noqa: BLE001 — never let logging crash the app
            return True
        redacted = msg
        for pat in _SECRET_PATTERNS:
            redacted = pat.sub(
                lambda m: (m.group(1) + "***REDACTED***") if m.lastindex else "***REDACTED***",
                redacted,
            )
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


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
        handler.addFilter(_RedactSecretsFilter())
        root.addHandler(handler)
    else:
        for h in root.handlers:
            if not any(isinstance(f, _RedactSecretsFilter) for f in h.filters):
                h.addFilter(_RedactSecretsFilter())
    root.setLevel(level)

    # Hide HTTP/library noise unless debug.
    http_level = logging.DEBUG if verbosity == "debug" else logging.WARNING
    if verbosity != "debug":
        http_level = logging.ERROR
    for name in _HTTP_LOGGERS:
        logging.getLogger(name).setLevel(http_level)

    # Our own loggers should follow root.
    logging.getLogger("researchhq").setLevel(level)
