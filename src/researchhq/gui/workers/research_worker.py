"""ResearchWorker - runs the existing async pipeline in a QThread, dispatches typed events.

Signals emitted to the GUI thread (all payloads are plain Python types):
- stage(stage, detail)             - convenience for chip widget; mirrors agent_progress
- event(event_dict)                - raw typed event for advanced consumers
- live_stats(stats_dict)           - rolling counters: elapsed/sources/llm_calls/tokens/cost
- finished_ok(report, saved_path)  - successful run
- failed(message, traceback)
- canceled
"""

from __future__ import annotations

import asyncio
import time
import traceback

from PySide6.QtCore import QThread, QTimer, Signal

from researchhq.events import PipelineEvent
from researchhq.pipeline import run as pipeline_run
from researchhq.reports.exporter import save
from researchhq.reports.schema import ResearchReport


class ResearchWorker(QThread):
    stage = Signal(str, str)
    event = Signal(dict)
    live_stats = Signal(dict)
    finished_ok = Signal(object, str)
    failed = Signal(str, str)
    canceled = Signal()

    def __init__(
        self,
        mode: str,
        query: str,
        export_format: str = "markdown",
        workspace: str = "default",
        effort: str = "medium",
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self._mode = mode
        self._query = query
        self._fmt = export_format
        self._workspace = workspace
        self._effort = effort
        self._cancel = False

        # Rolling stats
        self._stats = {
            "elapsed_s": 0,
            "agent": "",
            "sources": 0,
            "llm_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "equivalent_cost_usd": 0.0,
        }
        self._started_at: float | None = None
        self._tick = QTimer()
        self._tick.setInterval(500)
        self._tick.timeout.connect(self._emit_tick)

    def request_cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:  # noqa: D401 - Qt method
        self._started_at = time.monotonic()
        # QTimer must be moved to the thread that runs it, but signals are thread-safe;
        # safer to drive elapsed from the event itself or via per-event recompute.
        loop = asyncio.new_event_loop()
        try:
            asyncio.set_event_loop(loop)
            try:
                report = loop.run_until_complete(self._run_pipeline())
            except asyncio.CancelledError:
                self.canceled.emit()
                return

            try:
                path = save(report, fmt=self._fmt, workspace=self._workspace)
            except Exception as e:  # noqa: BLE001
                self.failed.emit(f"Failed to save report: {e}", traceback.format_exc())
                return

            self.finished_ok.emit(report, str(path))
        except Exception as e:  # noqa: BLE001
            self.failed.emit(str(e) or type(e).__name__, traceback.format_exc())
        finally:
            try:
                loop.close()
            except Exception:  # noqa: BLE001
                pass

    async def _run_pipeline(self) -> ResearchReport:
        def _on_event(ev: PipelineEvent) -> None:
            self._handle_event(ev)

        return await pipeline_run(
            self._mode, self._query,
            on_event=_on_event,
            cancel_check=lambda: self._cancel,
            effort=self._effort,
        )

    # ---- event dispatch ----
    def _handle_event(self, ev: PipelineEvent) -> None:
        # Update rolling stats based on event type.
        if ev.type == "agent_started":
            self._stats["agent"] = ev.stage
        elif ev.type == "source_found":
            self._stats["sources"] += 1
        elif ev.type == "llm_call_finished":
            self._stats["llm_calls"] += 1
            self._stats["input_tokens"] += int(ev.data.get("input_tokens", 0))
            self._stats["output_tokens"] += int(ev.data.get("output_tokens", 0))
            self._stats["equivalent_cost_usd"] += float(ev.data.get("equivalent_cost_usd", 0.0))

        if self._started_at is not None:
            self._stats["elapsed_s"] = round(time.monotonic() - self._started_at, 1)

        # Mirror to chip widget for any progress-like event.
        if ev.type in ("agent_started", "agent_progress", "agent_finished"):
            self.stage.emit(ev.stage, ev.detail)

        # Always emit the structured event and updated stats.
        self.event.emit({"type": ev.type, "stage": ev.stage, "detail": ev.detail, "data": dict(ev.data)})
        self.live_stats.emit(dict(self._stats))

    def _emit_tick(self) -> None:  # currently unused; reserved for clock-only updates
        if self._started_at is not None:
            self._stats["elapsed_s"] = round(time.monotonic() - self._started_at, 1)
            self.live_stats.emit(dict(self._stats))
