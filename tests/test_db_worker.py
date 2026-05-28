"""DbCallable: background QRunnable that routes results and failures to signals.

We exercise the runnable directly (without QThreadPool) so the test stays
fast and deterministic. Signals are captured via a tiny QObject collector.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")  # GUI extras gate.

from PySide6.QtCore import QCoreApplication

from researchhq.gui.workers.db_worker import DbCallable


@pytest.fixture(scope="module")
def qt_app():
    # A QCoreApplication is needed for signal/slot machinery, even though
    # we don't enter its event loop.
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


def test_callable_emits_result_then_finished(qt_app):
    job = DbCallable(lambda: 42, job_id="answer")
    results: list[tuple[str, object]] = []
    finishes: list[str] = []
    job.signals.result.connect(lambda jid, val: results.append((jid, val)))
    job.signals.finished.connect(lambda jid: finishes.append(jid))
    job.run()
    assert results == [("answer", 42)]
    assert finishes == ["answer"]


def test_callable_routes_exceptions_to_error_signal(qt_app):
    def boom() -> None:
        raise ValueError("bad payload")

    job = DbCallable(boom, job_id="kaboom")
    errors: list[tuple[str, str]] = []
    finishes: list[str] = []
    results: list = []
    job.signals.result.connect(lambda jid, val: results.append((jid, val)))
    job.signals.error.connect(lambda jid, msg, _tb: errors.append((jid, msg)))
    job.signals.finished.connect(lambda jid: finishes.append(jid))
    job.run()

    assert results == []
    assert errors == [("kaboom", "bad payload")]
    assert finishes == ["kaboom"]


def test_callable_finished_fires_even_when_emit_succeeds(qt_app):
    """The `finished` signal must fire exactly once whether we succeed or fail.

    Pages rely on this to clear their `_refresh_inflight` latch."""
    job = DbCallable(lambda: "ok", job_id="latch")
    fires = 0

    def on_fin(_jid: str) -> None:
        nonlocal fires
        fires += 1

    job.signals.finished.connect(on_fin)
    job.run()
    assert fires == 1
