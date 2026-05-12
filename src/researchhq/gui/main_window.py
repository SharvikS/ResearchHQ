"""Main window: sidebar nav + stacked pages, owns the global log bridge."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from researchhq.config import settings
from researchhq.gui import state as gstate
from researchhq.gui.pages.compare_page import ComparePage
from researchhq.gui.pages.dashboard import DashboardPage
from researchhq.gui.pages.history_page import HistoryPage
from researchhq.gui.pages.research_page import ResearchPage
from researchhq.gui.pages.settings_page import SettingsPage
from researchhq.gui.widgets.sidebar import Sidebar
from researchhq.gui.workers.log_handler import QtLogBridge
from researchhq.reports.exporter import to_markdown
from researchhq.reports.schema import ResearchReport

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ResearchHQ Studio")
        self.resize(1320, 860)

        # Restore persisted preferences before pages read settings.
        self._restore_persisted_settings()

        # Layout: sidebar | stacked pages
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = Sidebar()
        layout.addWidget(self._sidebar)

        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # Pages
        self._dashboard = DashboardPage()
        self._research = ResearchPage()
        self._history = HistoryPage()
        self._compare = ComparePage()
        self._settings = SettingsPage()

        for p in (self._dashboard, self._research, self._history, self._compare, self._settings):
            self._stack.addWidget(p)

        # Sidebar wiring
        self._sidebar.selected.connect(self._on_nav)
        self._sidebar.select("dashboard")

        # Cross-page wiring
        self._dashboard.open_research.connect(lambda: self._sidebar.select("research"))
        self._dashboard.open_report_path.connect(self._open_report_from_path)
        self._history.open_report_path.connect(self._open_report_from_path)
        self._history.duplicate_to_research.connect(self._duplicate_to_research)
        self._research.run_finished.connect(self._on_run_finished)

        # Log bridge -> research page
        self._log_bridge = QtLogBridge()
        self._log_bridge.line.connect(self._research.append_log)
        self._log_bridge.enable(debug=False)
        self._research.log_debug_changed.connect(self._log_bridge.set_debug)

        # Periodically refresh dashboard so it picks up new reports & cost.
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(3000)
        self._refresh_timer.timeout.connect(self._dashboard.refresh)
        self._refresh_timer.start()

    # ---------- nav ----------
    def _on_nav(self, key: str) -> None:
        idx = {"dashboard": 0, "research": 1, "history": 2, "compare": 3, "settings": 4}.get(key, 0)
        self._stack.setCurrentIndex(idx)
        # Refresh the page being shown so it reflects latest state.
        page = self._stack.currentWidget()
        if hasattr(page, "refresh"):
            try:
                page.refresh()
            except Exception:  # noqa: BLE001
                pass

    # ---------- open report ----------
    def _open_report_from_path(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self, "Report missing", f"Cannot find:\n{path}")
            return
        try:
            data = gstate.load_report(path)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", f"Failed to read JSON: {e}")
            return

        # Render markdown from the schema for the preview.
        try:
            report = ResearchReport.model_validate(data)
            md = to_markdown(report)
        except Exception:  # noqa: BLE001
            # Older / partial JSON: fall back to whatever Markdown sibling exists, else stub.
            sibling = path.with_suffix(".md")
            md = sibling.read_text(encoding="utf-8") if sibling.exists() else "_Report could not be parsed._"

        self._sidebar.select("research")
        self._research.show_report_dict(data, md)

    # ---------- persisted prefs ----------
    def _restore_persisted_settings(self) -> None:
        qs = QSettings()
        provider = qs.value("provider/default", settings.default_provider)
        model = qs.value("provider/model", "")
        output_folder = qs.value("output/folder", settings.output_folder)
        output_format = qs.value("output/format", settings.default_format)
        engines = qs.value("search/engines", ",".join(settings.search_engines))
        max_sources = qs.value("search/max_sources", settings.max_total_sources, type=int)
        per_query = qs.value("search/per_query", settings.max_results_per_query, type=int)

        if provider:
            settings.default_provider = str(provider)
        if model and provider:
            settings.models[str(provider)] = str(model)
        if output_folder:
            settings.output_folder = str(output_folder)
        if output_format:
            settings.default_format = str(output_format)
        if engines:
            settings.search_engines = [e for e in str(engines).split(",") if e]
        try:
            settings.max_total_sources = int(max_sources)
            settings.max_results_per_query = int(per_query)
        except Exception:  # noqa: BLE001
            pass

    # ---------- duplicate-to-research / post-run refresh ----------
    def _duplicate_to_research(self, query: str, mode: str) -> None:
        self._sidebar.select("research")
        self._research.prefill_query(query, mode)

    def _on_run_finished(self) -> None:
        # Pulled to refresh dashboard + history snapshots immediately after a run.
        try:
            self._dashboard.refresh()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._history.refresh()
        except Exception:  # noqa: BLE001
            pass
        try:
            self._compare.refresh()
        except Exception:  # noqa: BLE001
            pass

    # ---------- close ----------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt method
        # Stop any running worker so background threads don't leak.
        try:
            self._research._on_cancel()  # noqa: SLF001 - safe internal use
        except Exception:  # noqa: BLE001
            pass
        super().closeEvent(event)
