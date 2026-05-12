"""Dashboard page: quick stats, provider/model status, recent reports, saved exports."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from researchhq.config import settings
from researchhq.gui import state as gstate
from researchhq.gui.widgets.card import Card, StatCard
from researchhq.llm.cost_tracker import tracker


class DashboardPage(QWidget):
    open_research = Signal()                 # user wants to start a new research
    open_report_path = Signal(str)           # path to a JSON report

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

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

        # Header with primary CTA
        header = QHBoxLayout()
        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 20px; font-weight: 700; background: transparent;")
        header.addWidget(title)
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

        self.refresh()

    # ------------- public -------------
    def refresh(self) -> None:
        self._refresh_providers()
        self._refresh_reports()
        self._refresh_exports()
        self._refresh_cost()

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
            n = QLabel(name); n.setStyleSheet("background: transparent;")
            status = QLabel("● configured" if configured else "○ not configured")
            status.setStyleSheet(
                f"color: {'#3ecf8e' if configured else '#8a96a8'}; background: transparent;"
            )
            m = QLabel(model or "-")
            m.setStyleSheet("color: #8a96a8; background: transparent;")
            self._providers_grid.addWidget(n, r, 0)
            self._providers_grid.addWidget(status, r, 1)
            self._providers_grid.addWidget(m, r, 2)

    def _refresh_reports(self) -> None:
        from researchhq import history as histdb
        self._recent_list.clear()
        try:
            rows = histdb.list_runs(workspace="all", limit=6)
        except Exception:  # noqa: BLE001
            rows = []

        # If DB is empty but folder has reports, run a one-shot reindex.
        if not rows:
            try:
                if histdb.reindex_from_folder() > 0:
                    rows = histdb.list_runs(workspace="all", limit=6)
            except Exception:  # noqa: BLE001
                pass

        if not rows:
            empty = QListWidgetItem("No reports yet. Click 'New Research' to start.")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self._recent_list.addItem(empty)
        for r in rows:
            label = f"[{r.mode}] {r.query}"
            if r.confidence is not None:
                label += f"   ·   confidence {r.confidence:.2f}"
            label += f"   ·   {r.sources_count} sources"
            it = QListWidgetItem(label)
            it.setData(Qt.ItemDataRole.UserRole, r.json_path)
            it.setToolTip(r.json_path)
            self._recent_list.addItem(it)

        try:
            agg = histdb.aggregate(workspace="all")
        except Exception:  # noqa: BLE001
            agg = {"total_reports": 0, "total_sources": 0, "last_run_cost": 0.0}
        self._stat_reports.set_value(str(agg["total_reports"]))
        self._stat_sources.set_value(str(agg["total_sources"]))
        self._stat_cost.set_value(f"${agg.get('last_run_cost', 0.0):.4f}")

    def _refresh_exports(self) -> None:
        self._exports_list.clear()
        folder = gstate.reports_dir()
        if not folder.exists():
            self._exports_list.addItem(
                QListWidgetItem(f"Reports folder will be created at: {folder.resolve()}")
            )
            return
        for p in sorted(folder.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if p.is_file() and p.suffix in (".md", ".html", ".json"):
                it = QListWidgetItem(f"{p.name}   ·   {p.suffix.lstrip('.')}")
                it.setData(Qt.ItemDataRole.UserRole, str(p))
                self._exports_list.addItem(it)
        if self._exports_list.count() == 0:
            self._exports_list.addItem(QListWidgetItem("No exports yet."))

    def _refresh_cost(self) -> None:
        # last-run cost is set in _refresh_reports from DB aggregate;
        # this method exists for backward compat with the timer tick.
        return

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
        else:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl.fromLocalFile(path))
