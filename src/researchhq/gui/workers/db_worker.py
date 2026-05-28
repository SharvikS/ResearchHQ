"""Reusable background workers for database / file IO operations.

All `researchhq.history` calls hit SQLite synchronously. Running them on the
Qt main thread freezes the UI as the dataset grows. The workers here move
those calls onto QThreadPool runnables and deliver results via thread-safe
Qt signals, so pages can stay event-driven without polling.

Pattern:

    self._pool = QThreadPool.globalInstance()
    job = DbCallable(lambda: histdb.list_runs(workspace=ws, mode=mode))
    job.signals.result.connect(self._on_rows)
    job.signals.error.connect(self._on_db_error)
    self._pool.start(job)

Signals are always emitted from the worker thread; the receiving Qt slot
runs on whichever thread owns the connected QObject. With direct connections
to widget slots, Qt automatically queues the call onto the GUI thread.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, Signal

logger = logging.getLogger(__name__)


class _Signals(QObject):
    # Successful completion: (job_id, result).
    result = Signal(str, object)
    # Failure: (job_id, message, traceback_text).
    error = Signal(str, str, str)
    # Always emitted last, success or failure: (job_id,).
    finished = Signal(str)


class DbCallable(QRunnable):
    """Run any zero-arg callable on the QThreadPool and emit its result.

    The `job_id` lets a single page route multiple in-flight jobs through one
    set of slots (e.g. workspace-refresh vs. run-list). Keep callables short
    and side-effect-free where possible — emit signals back to the GUI thread
    rather than mutating widgets directly from inside the callable.
    """

    def __init__(self, fn: Callable[[], Any], *, job_id: str = "") -> None:
        super().__init__()
        self.signals = _Signals()
        self._fn = fn
        self._job_id = job_id
        self.setAutoDelete(True)

    def run(self) -> None:  # noqa: D401 - Qt method
        try:
            result = self._fn()
        except Exception as exc:  # noqa: BLE001 - we re-emit; never swallow
            tb = traceback.format_exc()
            logger.exception("Background job '%s' failed", self._job_id or "<unnamed>")
            try:
                self.signals.error.emit(self._job_id, str(exc) or type(exc).__name__, tb)
            finally:
                self.signals.finished.emit(self._job_id)
            return
        try:
            self.signals.result.emit(self._job_id, result)
        finally:
            self.signals.finished.emit(self._job_id)
