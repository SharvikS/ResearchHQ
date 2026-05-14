"""Logging configuration for ResearchHQ.

Activated once at process startup (by the API server or CLI entry points).

Two output formats:
  text (default) — human-readable, coloured level prefix, HH:MM:SS timestamp
  json           — newline-delimited JSON for log aggregators (Loki, CloudWatch, etc.)
                   activate with LOG_FORMAT=json environment variable

Extra fields added via logger.info("msg", extra={"key": val}) are included
in JSON output and silently ignored in text output.

Usage:
    from researchhq.logging_config import configure
    configure(level="INFO")        # reads LOG_FORMAT from env automatically
    configure(json_format=True)    # force JSON regardless of env
"""

from __future__ import annotations

import json
import logging
import os
import time

# Standard LogRecord attributes we don't want to re-emit as extra fields
_STDLIB_ATTRS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename",
    "funcName", "id", "levelname", "levelno", "lineno", "message",
    "module", "msecs", "msg", "name", "pathname", "process",
    "processName", "relativeCreated", "stack_info", "thread", "threadName",
    "taskName",
})


class _JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        log: dict = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.message,
        }
        if record.exc_info:
            log["exc"] = self.formatException(record.exc_info)
        if record.stack_info:
            log["stack"] = self.formatStack(record.stack_info)
        # Include any extra= fields passed by the caller
        for key, val in record.__dict__.items():
            if key not in _STDLIB_ATTRS:
                log[key] = val
        return json.dumps(log, default=str)


class _TextFormatter(logging.Formatter):
    _LEVEL_COLORS = {
        "DEBUG":    "\033[36m",   # cyan
        "INFO":     "\033[32m",   # green
        "WARNING":  "\033[33m",   # yellow
        "ERROR":    "\033[31m",   # red
        "CRITICAL": "\033[35m",   # magenta
    }
    _RESET = "\033[0m"

    def __init__(self, use_color: bool = True) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
            datefmt="%H:%M:%S",
        )
        self._use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        if self._use_color:
            color = self._LEVEL_COLORS.get(record.levelname, "")
            line = f"{color}{line}{self._RESET}"
        return line


def configure(
    level: str | None = None,
    json_format: bool | None = None,
) -> None:
    """Configure the root logger. Call once at process startup.

    Args:
        level: log level string (DEBUG/INFO/WARNING/ERROR). Reads LOG_LEVEL env if None.
        json_format: True → JSON output; False → coloured text; None → reads LOG_FORMAT env.
    """
    effective_level = level or os.environ.get("LOG_LEVEL", "INFO")
    if json_format is None:
        json_format = os.environ.get("LOG_FORMAT", "").lower() == "json"

    use_color = not json_format and os.environ.get("NO_COLOR", "") == ""

    handler = logging.StreamHandler()
    handler.setFormatter(
        _JsonFormatter() if json_format else _TextFormatter(use_color=use_color)
    )

    logging.basicConfig(
        level=effective_level.upper(),
        handlers=[handler],
        force=True,
    )

    # Silence noisy third-party libraries unless in DEBUG mode
    if effective_level.upper() != "DEBUG":
        for lib in ("httpx", "httpcore", "urllib3", "hpack", "asyncio",
                    "multipart", "uvicorn.access"):
            logging.getLogger(lib).setLevel(logging.WARNING)
