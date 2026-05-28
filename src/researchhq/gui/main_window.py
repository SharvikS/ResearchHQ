"""Main window: sidebar nav + stacked pages, owns the global log bridge.

Refreshes are strictly event-driven — there is no polling timer. The window
owns no business logic; cross-page coordination happens via Qt signals so
no widget reaches into another widget's privates.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)
from pydantic import ValidationError

from researchhq.config import settings
from researchhq.gui import state as gstate
from researchhq.gui.motion import cross_fade, fade_in
from researchhq.gui.pages.compare_page import ComparePage
from researchhq.gui.pages.dashboard import DashboardPage
from researchhq.gui.pages.history_page import HistoryPage
from researchhq.gui.pages.research_page import ResearchPage
from researchhq.gui.pages.settings_page import SettingsPage
from researchhq.gui.widgets.divider import WorkspaceDivider
from researchhq.gui.widgets.sidebar import Sidebar
from researchhq.gui.workers.log_handler import QtLogBridge
from researchhq.reports.exporter import to_markdown
from researchhq.reports.schema import ResearchReport

logger = logging.getLogger(__name__)

# Page order in the QStackedWidget. Keep in sync with sidebar keys.
_PAGE_INDEX = {"dashboard": 0, "research": 1, "history": 2, "compare": 3, "settings": 4}


class MainWindow(QMainWindow):
    """Top-level shell. Emits `about_to_close` so the active research worker
    can drain gracefully without reaching into private widget state."""

    about_to_close = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ResearchHQ Studio")

        # Scalable sizing: respect DPI + the user's screen. resize() the
        # window to a comfortable default for the current screen, then let
        # Qt's layouts handle the rest.
        self._apply_initial_geometry()

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

        # Theme-aware gradient hairline between sidebar + content.
        self._divider = WorkspaceDivider()
        layout.addWidget(self._divider)

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

        # Graceful shutdown: window broadcasts intent to close; the research
        # page handles its own worker cancellation. No private method calls.
        self.about_to_close.connect(self._research.shutdown)

        # Log bridge -> research page
        self._log_bridge = QtLogBridge()
        self._log_bridge.line.connect(self._research.append_log)
        self._log_bridge.enable(debug=False)
        self._research.log_debug_changed.connect(self._log_bridge.set_debug)

    # ---------- nav ----------
    def _on_nav(self, key: str) -> None:
        idx = _PAGE_INDEX.get(key, 0)
        # Animated cross-fade between pages instead of an instant swap.
        cross_fade(self._stack, idx)
        # Refresh the page being shown so it reflects latest state. Page
        # refreshes dispatch their own background work — they never block.
        page = self._stack.currentWidget()
        refresh = getattr(page, "refresh", None)
        if callable(refresh):
            try:
                refresh()
            except (RuntimeError, OSError):
                logger.exception("Page refresh on nav('%s') raised", key)

    def showEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().showEvent(event)
        # Reveal the window with a subtle opacity fade on first paint.
        if not getattr(self, "_did_intro_fade", False):
            self._did_intro_fade = True
            fade_in(self)

    # ---------- open report ----------
    def _open_report_from_path(self, path_str: str) -> None:
        path = Path(path_str)
        if not path.exists():
            QMessageBox.warning(self, "Report missing", f"Cannot find:\n{path}")
            return
        try:
            data = gstate.load_report(path)
        except (OSError, ValueError) as exc:
            logger.exception("Failed to read report JSON %s", path)
            QMessageBox.critical(self, "Load failed", f"Failed to read JSON: {exc}")
            return

        # Render markdown from the schema for the preview. Older / partial
        # JSON falls back to the sibling .md file, then to a stub.
        try:
            report = ResearchReport.model_validate(data)
            md = to_markdown(report)
        except ValidationError:
            logger.info("Report at %s did not match schema; using sibling .md fallback", path)
            sibling = path.with_suffix(".md")
            md = sibling.read_text(encoding="utf-8") if sibling.exists() else "_Report could not be parsed._"

        self._sidebar.select("research")
        self._research.show_report_dict(data, md)

    # ---------- persisted prefs ----------
    def _apply_initial_geometry(self) -> None:
        """Pick a window size that scales with the user's primary screen.

        Replaces the previous hard-coded 1320x860 — that was too big on
        13" laptops and too small on 4K displays. We also set a minimum
        size so the layout has room for the sidebar + content."""
        screen = self.screen()
        if screen is None:
            self.resize(1280, 800)
        else:
            available = screen.availableGeometry()
            # 80% of available area, capped to a comfortable max for very large displays.
            w = min(int(available.width() * 0.80), 1600)
            h = min(int(available.height() * 0.85), 1000)
            self.resize(max(w, 980), max(h, 640))
        self.setMinimumSize(980, 640)

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
        except (TypeError, ValueError):
            logger.debug("Persisted source caps unreadable; keeping defaults")

    # ---------- duplicate-to-research / post-run refresh ----------
    def _duplicate_to_research(self, query: str, mode: str) -> None:
        self._sidebar.select("research")
        self._research.prefill_query(query, mode)

    def _on_run_finished(self) -> None:
        # Pages dispatch their refresh onto QThreadPool — these calls return
        # immediately. Any background failure is logged inside the worker.
        for page in (self._dashboard, self._history, self._compare):
            try:
                page.refresh()
            except RuntimeError:
                logger.exception("Refresh after run_finished failed for %s", type(page).__name__)

    # ---------- close ----------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt method
        # Tell the research page (and anyone else listening) to drain its
        # background worker. We do NOT call private methods on it.
        self.about_to_close.emit()
        super().closeEvent(event)
