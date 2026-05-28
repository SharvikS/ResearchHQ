"""Dashboard page: quick stats, provider/model status, recent reports, saved exports.

All SQLite + file IO is dispatched to QThreadPool via DbCallable so the UI
thread never blocks. Refreshes are event-driven (sidebar navigation, post-run
hooks) — there is no polling timer.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from researchhq.config import settings
from researchhq.gui import state as gstate
from researchhq.gui.widgets.card import Card, StatCard
from researchhq.gui.workers.db_worker import DbCallable

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DashboardSnapshot:
    """One immutable payload covering everything the dashboard renders.

    Computed on a worker thread; passed back to the GUI thread via a signal
    so widget mutation always happens on the main thread.
    """
    rows: list[Any]
    agg: dict[str, Any]
    reindexed: int  # number of files reindexed in this refresh, if any
    exports: list[tuple[Path, str]]  # (path, suffix-without-dot)
    exports_folder: Path
    exports_folder_existed: bool


def _build_snapshot() -> _DashboardSnapshot:
    """Worker-side: gather everything the dashboard needs in one trip.

    Runs on a QThreadPool thread — must not touch widgets.
    """
    from researchhq import history as histdb

    rows = histdb.list_runs(workspace="all", limit=6)
    reindexed = 0
    if not rows:
        reindexed = histdb.reindex_from_folder()
        if reindexed > 0:
            rows = histdb.list_runs(workspace="all", limit=6)

    agg = histdb.aggregate(workspace="all")

    folder = gstate.reports_dir()
    exports: list[tuple[Path, str]] = []
    existed = folder.exists()
    if existed:
        try:
            for p in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
                if p.is_file() and p.suffix in (".md", ".html", ".json"):
                    exports.append((p, p.suffix.lstrip(".")))
        except OSError:
            logger.exception("Could not list exports folder %s", folder)

    return _DashboardSnapshot(
        rows=rows,
        agg=agg,
        reindexed=reindexed,
        exports=exports,
        exports_folder=folder,
        exports_folder_existed=existed,
    )


class DashboardPage(QWidget):
    open_research = Signal()                 # user wants to start a new research
    open_report_path = Signal(str)           # path to a JSON report

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._refresh_inflight = False

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header with primary CTA + loading indicator
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setObjectName("PageTitle")
        header.addWidget(title)

        self._busy = QProgressBar()
        self._busy.setObjectName("BusyBar")
        self._busy.setRange(0, 0)  # indeterminate
        self._busy.setMaximumWidth(140)
        self._busy.setMaximumHeight(6)
        self._busy.setTextVisible(False)
        self._busy.hide()
        header.addWidget(self._busy)

        header.addStretch(1)
        self._new_btn = QPushButton("+ New Research")
        self._new_btn.setObjectName("Primary")
        self._new_btn.clicked.connect(self.open_research.emit)
        header.addWidget(self._new_btn)
        layout.addLayout(header)

        # Quick stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._stat_reports = StatCard("Total reports", "0")
        self._stat_sources = StatCard("Sources collected", "0")
        self._stat_cost = StatCard("Last run (equiv $)", "$0.0000")
        stats_row.addWidget(self._stat_reports)
        stats_row.addWidget(self._stat_sources)
        stats_row.addWidget(self._stat_cost)
        layout.addLayout(stats_row)

        # Two-column: provider status + recent reports
        cols = QHBoxLayout()
        cols.setSpacing(12)

        providers_card = Card("Providers", "Configured LLM providers and models")
        self._providers_grid = QGridLayout()
        self._providers_grid.setHorizontalSpacing(12)
        self._providers_grid.setVerticalSpacing(6)
        providers_card.add_layout(self._providers_grid)
        cols.addWidget(providers_card, 1)

        recent_card = Card("Recent reports", "Double-click to open")
        self._recent_list = QListWidget()
        self._recent_list.itemActivated.connect(self._on_open_recent)
        recent_card.add(self._recent_list)
        cols.addWidget(recent_card, 1)

        layout.addLayout(cols)

        # Saved exports
        exports_card = Card("Saved exports", "Files in your reports folder")
        self._exports_list = QListWidget()
        self._exports_list.itemActivated.connect(self._on_open_export)
        exports_card.add(self._exports_list)
        layout.addWidget(exports_card)

        layout.addStretch(1)

        # Render synchronous bits immediately; kick off async DB query.
        self._refresh_providers()
        self.refresh()

    # ------------- public -------------
    def refresh(self) -> None:
        """Refresh provider grid synchronously; load DB-backed data in the
        background. Safe to call repeatedly — overlapping requests are
        coalesced into the in-flight refresh."""
        self._refresh_providers()
        if self._refresh_inflight:
            return
        self._refresh_inflight = True
        self._busy.show()

        job = DbCallable(_build_snapshot, job_id="dashboard.snapshot")
        job.signals.result.connect(self._on_snapshot_ready)
        job.signals.error.connect(self._on_snapshot_error)
        job.signals.finished.connect(self._on_snapshot_finished)
        self._pool.start(job)

    # ------------- internals -------------
    def _refresh_providers(self) -> None:
        # Clear grid
        while self._providers_grid.count():
            it = self._providers_grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        rows = [
            ("Groq",      bool(settings.groq_api_key),      settings.models.get("groq", "")),
            ("Gemini",    bool(settings.gemini_api_key),    settings.models.get("gemini", "")),
            ("OpenAI",    bool(settings.openai_api_key),    settings.models.get("openai", "")),
            ("Anthropic", bool(settings.anthropic_api_key), settings.models.get("anthropic", "")),
            ("Ollama",    True,                              settings.models.get("ollama", "")),
        ]
        for r, (name, configured, model) in enumerate(rows):
            n = QLabel(name)
            n.setObjectName("ProviderName")
            status = QLabel("● configured" if configured else "○ not configured")
            status.setObjectName("StatusOk" if configured else "StatusOff")
            m = QLabel(model or "-")
            m.setObjectName("Muted")
            self._providers_grid.addWidget(n, r, 0)
            self._providers_grid.addWidget(status, r, 1)
            self._providers_grid.addWidget(m, r, 2)

    def _on_snapshot_ready(self, _job_id: str, payload: object) -> None:
        if not isinstance(payload, _DashboardSnapshot):
            logger.error("Dashboard snapshot job returned unexpected type %r", type(payload))
            return
        self._render_recent(payload.rows)
        self._render_aggregate(payload.agg)
        self._render_exports(payload)

    def _on_snapshot_error(self, _job_id: str, message: str, _tb: str) -> None:
        # Render the page with empty data so the user isn't left with a blank screen.
        self._render_recent([])
        self._render_aggregate({"total_reports": 0, "total_sources": 0, "last_run_cost": 0.0})
        self._exports_list.clear()
        self._exports_list.addItem(QListWidgetItem(f"Could not load dashboard data: {message}"))

    def _on_snapshot_finished(self, _job_id: str) -> None:
        self._refresh_inflight = False
        self._busy.hide()

    def _render_recent(self, rows: list[Any]) -> None:
        self._recent_list.clear()
        if not rows:
            empty = QListWidgetItem("No reports yet. Click 'New Research' to start.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recent_list.addItem(empty)
            return
        for r in rows:
            label = f"[{r.mode}] {r.query}"
            if r.confidence is not None:
                label += f"   ·   confidence {r.confidence:.2f}"
            label += f"   ·   {r.sources_count} sources"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.json_path)
            it.setToolTip(r.json_path)
            self._recent_list.addItem(it)

    def _render_aggregate(self, agg: dict[str, Any]) -> None:
        self._stat_reports.set_value(str(agg.get("total_reports", 0)))
        self._stat_sources.set_value(str(agg.get("total_sources", 0)))
        self._stat_cost.set_value(f"${agg.get('last_run_cost', 0.0):.4f}")

    def _render_exports(self, snap: _DashboardSnapshot) -> None:
        self._exports_list.clear()
        if not snap.exports_folder_existed:
            self._exports_list.addItem(
                QListWidgetItem(
                    f"Reports folder will be created at: {snap.exports_folder.resolve()}"
                )
            )
            return
        if not snap.exports:
            self._exports_list.addItem(QListWidgetItem("No exports yet."))
            return
        for p, suffix in snap.exports:
            it = QListWidgetItem(f"{p.name}   ·   {suffix}")
            it.setData(Qt.ItemDataRole.UserRole, str(p))
            self._exports_list.addItem(it)

    def _on_open_recent(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.open_report_path.emit(path)

    def _on_open_export(self, item: QListWidgetItem) -> None:
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        # If user clicks a JSON, treat it as a report; otherwise open externally.
        if path.endswith(".json"):
            self.open_report_path.emit(path)
            return
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))
