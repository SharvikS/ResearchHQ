"""Bridge from Python logging to a Qt signal so any agent log line is rendered live.

Filters HTTP/library noise unless debug mode is on (matching the CLI verbosity scheme)."""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal

_HTTP_LOGGERS = (
    "httpx", "httpcore", "urllib3", "requests", "ddgs", "primp",
    "asyncio", "google", "groq", "ollama", "openai", "anthropic",
)


class QtLogBridge(QObject):
    """Emits a signal per log record. Install once, enable() to attach to root."""
    line = Signal(str, str)  # (level_name, formatted message)

    def __init__(self) -> None:
        super().__init__()
        self._handler: _BridgeHandler | None = None
        self._debug = False

    def enable(self, debug: bool = False) -> None:
        self._debug = debug
        if self._handler is None:
            self._handler = _BridgeHandler(self)
            self._handler.setFormatter(
                logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                                  datefmt="%H:%M:%S")
            )
            logging.getLogger().addHandler(self._handler)
        self._apply_levels()

    def disable(self) -> None:
        if self._handler is not None:
            logging.getLogger().removeHandler(self._handler)
            self._handler = None

    def set_debug(self, debug: bool) -> None:
        self._debug = debug
        self._apply_levels()

    def _apply_levels(self) -> None:
        root_level = logging.DEBUG if self._debug else logging.INFO
        logging.getLogger().setLevel(root_level)
        if self._handler is not None:
            self._handler.setLevel(root_level)
        http_level = logging.DEBUG if self._debug else logging.ERROR
        for name in _HTTP_LOGGERS:
            logging.getLogger(name).setLevel(http_level)
        logging.getLogger("researchhq").setLevel(root_level)


class _BridgeHandler(logging.Handler):
    def __init__(self, bridge: QtLogBridge) -> None:
        super().__init__()
        self._bridge = bridge

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Qt signals are thread-safe across QObjects; emitting from worker thread is fine.
            self._bridge.line.emit(record.levelname, msg)
        except Exception:  # noqa: BLE001 - logging must never raise
            pass
