"""Research page: query input, mode selector, run/cancel, live pipeline + stats + report."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from researchhq.config import settings
from researchhq.effort import DEFAULT_EFFORT, PROFILES
from researchhq.gui.presets import PRESETS, Preset
from researchhq.gui.widgets.card import Card
from researchhq.gui.widgets.log_console import LogConsole
from researchhq.gui.widgets.pipeline_status import PipelineStatus
from researchhq.gui.widgets.report_viewer import ReportViewer
from researchhq.gui.workers.research_worker import ResearchWorker
from researchhq.reports.exporter import to_html, to_json, to_markdown
from researchhq.reports.schema import ResearchReport

MODES = [
    ("topic",      "General topic"),
    ("company",    "Company"),
    ("competitor", "Competitor"),
    ("technology", "Technology"),
    ("market",     "Market"),
    ("news",       "News / Recent"),
    ("academic",   "Academic"),
]

FORMATS = [("markdown", "Markdown"), ("json", "JSON"), ("html", "HTML"), ("pdf", "PDF")]


class ResearchPage(QWidget):
    log_debug_changed = Signal(bool)
    run_finished = Signal()  # main window can refresh dashboard/history

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(14)

        # ---- Header ----
        header = QHBoxLayout()
        title = QLabel("New research")
        title.setStyleSheet("font-size: 20px; font-weight: 700; background: transparent;")
        header.addWidget(title)
        header.addStretch(1)

        self._preset_box = QComboBox()
        self._preset_box.addItem("Apply preset...", userData=None)
        for p in PRESETS:
            self._preset_box.addItem(p.name, userData=p)
        self._preset_box.currentIndexChanged.connect(self._on_preset)
        header.addWidget(self._preset_box)
        outer.addLayout(header)

        # ---- Controls ----
        controls = Card("Query", "Pick a mode and what to investigate. Ctrl+Enter to run.")
        form = QVBoxLayout()
        self._query = QLineEdit()
        self._query.setPlaceholderText("e.g. AI agents in cybersecurity, or 'Supabase'")
        self._query.setStyleSheet("font-size: 14px; padding: 12px;")
        form.addWidget(self._query)

        params = QHBoxLayout()
        params.setSpacing(10)

        self._mode = QComboBox()
        for key, label in MODES:
            self._mode.addItem(label, userData=key)
        params.addWidget(QLabel("Mode")); params.addWidget(self._mode)

        self._provider = QComboBox()
        for p in ["auto"] + ["groq", "gemini", "openai", "anthropic", "ollama"]:
            self._provider.addItem(p)
        params.addWidget(QLabel("Provider")); params.addWidget(self._provider)

        self._max_sources = QSpinBox(); self._max_sources.setRange(3, 50)
        self._max_sources.setValue(settings.max_total_sources)
        params.addWidget(QLabel("Max sources")); params.addWidget(self._max_sources)

        self._depth = QSpinBox(); self._depth.setRange(1, 12)
        self._depth.setValue(settings.max_results_per_query)
        self._depth.setToolTip("Search depth: results per generated search query.")
        params.addWidget(QLabel("Depth")); params.addWidget(self._depth)

        self._effort = QComboBox()
        for level in PROFILES:
            p = PROFILES[level]
            self._effort.addItem(level.capitalize(), userData=level)
            ix = self._effort.count() - 1
            self._effort.setItemData(
                ix,
                f"queries {p.planner_min_queries}-{p.planner_max_queries}, "
                f"sources {p.max_total_sources}, fetch {p.fetch_top_n}×{p.per_page_chars}, "
                f"depth {p.synth_depth}",
                Qt.ItemDataRole.ToolTipRole,
            )
        ix = next((i for i in range(self._effort.count())
                   if self._effort.itemData(i) == DEFAULT_EFFORT), 1)
        self._effort.setCurrentIndex(ix)
        self._effort.setToolTip(
            "Effort dial — low (fast scan), medium (balanced default), "
            "high (deep dive; ~3× tokens)."
        )
        params.addWidget(QLabel("Effort")); params.addWidget(self._effort)

        self._format = QComboBox()
        for key, label in FORMATS:
            self._format.addItem(label, userData=key)
        ix = next((i for i in range(self._format.count())
                   if self._format.itemData(i) == settings.default_format), 0)
        self._format.setCurrentIndex(ix)
        params.addWidget(QLabel("Format")); params.addWidget(self._format)
        params.addStretch(1)

        self._run_btn = QPushButton("Run Research")
        self._run_btn.setObjectName("Primary")
        self._run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._run_btn.setToolTip("Ctrl+Enter")
        self._run_btn.clicked.connect(self._on_run)
        params.addWidget(self._run_btn)

        self._pause_btn = QPushButton("Pause")
        self._pause_btn.setEnabled(False)
        self._pause_btn.setToolTip("Pause/Resume coming soon.")
        params.addWidget(self._pause_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("Danger")
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setToolTip("Esc")
        self._cancel_btn.clicked.connect(self._on_cancel)
        params.addWidget(self._cancel_btn)

        form.addLayout(params)
        controls.add_layout(form)
        outer.addWidget(controls)

        # ---- Live stats strip ----
        self._stats_card = Card("Live stats", "Updates as the pipeline runs.")
        stats_row = QHBoxLayout(); stats_row.setSpacing(18)
        self._stat_widgets: dict[str, QLabel] = {}
        for key, label in [
            ("elapsed", "Elapsed"),
            ("agent",   "Current agent"),
            ("sources", "Sources"),
            ("llm_calls", "LLM calls"),
            ("tokens",  "Tokens"),
            ("cost",    "Equiv $"),
        ]:
            block = QVBoxLayout(); block.setSpacing(2)
            l = QLabel(label); l.setObjectName("StatLabel"); block.addWidget(l)
            v = QLabel("-"); v.setObjectName("StatValue"); v.setStyleSheet("font-size: 16px;")
            self._stat_widgets[key] = v; block.addWidget(v)
            stats_row.addLayout(block)
        stats_row.addStretch(1)
        self._stats_card.add_layout(stats_row)
        outer.addWidget(self._stats_card)

        # ---- Pipeline status ----
        pipe_card = Card("Pipeline", "Live agent progress")
        self._pipeline = PipelineStatus()
        pipe_card.add(self._pipeline)
        outer.addWidget(pipe_card)

        # ---- Splitter: report | logs ----
        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        report_card = Card("Report", "Tabs: Summary / Full / Sources / Evidence / JSON / Logs")
        self._viewer = ReportViewer()
        report_card.add(self._viewer)

        exports = QHBoxLayout(); exports.setSpacing(8)
        self._btn_md = QPushButton("Export .md")
        self._btn_md.clicked.connect(lambda: self._export("markdown"))
        self._btn_json = QPushButton("Export .json")
        self._btn_json.clicked.connect(lambda: self._export("json"))
        self._btn_html = QPushButton("Export .html")
        self._btn_html.clicked.connect(lambda: self._export("html"))
        self._btn_pdf = QPushButton("Export .pdf")
        self._btn_pdf.clicked.connect(self._export_pdf)
        self._btn_copy_full = QPushButton("Copy full")
        self._btn_copy_full.clicked.connect(self._copy_full)
        self._btn_copy_summary = QPushButton("Copy summary")
        self._btn_copy_summary.clicked.connect(self._copy_summary)
        for b in (self._btn_md, self._btn_json, self._btn_html, self._btn_pdf,
                  self._btn_copy_full, self._btn_copy_summary):
            b.setEnabled(False)
            exports.addWidget(b)
        exports.addStretch(1)
        report_card.add_layout(exports)
        split.addWidget(report_card)

        logs_card = Card("Logs", "Live agent + system logs")
        self._logs = LogConsole()
        self._logs.debug_toggle.toggled.connect(self.log_debug_changed.emit)
        logs_card.add(self._logs)
        split.addWidget(logs_card)

        split.setStretchFactor(0, 3)
        split.setStretchFactor(1, 2)
        outer.addWidget(split, 1)

        self._worker: ResearchWorker | None = None
        self._last_report: ResearchReport | None = None

        # Keyboard shortcuts (page-scoped)
        QShortcut(QKeySequence("Ctrl+Return"), self, activated=self._on_run)
        QShortcut(QKeySequence("Ctrl+Enter"),  self, activated=self._on_run)
        QShortcut(QKeySequence("Esc"),         self, activated=self._on_cancel)
        QShortcut(QKeySequence("Ctrl+S"),      self, activated=self._on_save_default)
        QShortcut(QKeySequence("Ctrl+K"),      self, activated=self._query.setFocus)

    # --------------- external API ---------------
    def append_log(self, level: str, msg: str) -> None:
        self._logs.append(level, msg)

    def show_report_dict(self, report_dict: dict, full_md: str) -> None:
        self._viewer.show_report(report_dict, full_md, logs_text=None)
        self._enable_exports(True)

    def prefill_query(self, q: str = "", mode: str = "") -> None:
        if q:
            self._query.setText(q)
        if mode:
            ix = next((i for i in range(self._mode.count())
                       if self._mode.itemData(i) == mode), -1)
            if ix >= 0:
                self._mode.setCurrentIndex(ix)
        self._query.setFocus()

    # --------------- handlers ---------------
    def _on_preset(self, _ix: int) -> None:
        p: Preset | None = self._preset_box.currentData()
        if not p:
            return
        # Set mode to preset.mode
        ix = next((i for i in range(self._mode.count())
                   if self._mode.itemData(i) == p.mode), -1)
        if ix >= 0:
            self._mode.setCurrentIndex(ix)
        self._max_sources.setValue(p.max_sources)
        self._query.setPlaceholderText(p.placeholder)
        # Don't auto-fill; let user type their subject. Description shown as tooltip.
        self._query.setToolTip(p.description)
        self._query.setFocus()

    def _on_run(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        query = self._query.text().strip()
        if not query:
            QMessageBox.warning(self, "Missing query", "Type a research query first.")
            return

        # Apply preset template if any
        preset: Preset | None = self._preset_box.currentData()
        if preset and preset.template != "{q}":
            query = preset.template.format(q=query)

        # Settings overrides for this run
        settings.max_total_sources = int(self._max_sources.value())
        settings.max_results_per_query = int(self._depth.value())
        provider_choice = self._provider.currentText()
        if provider_choice != "auto":
            settings.default_provider = provider_choice
            # Rebuild router for the new preference order
            try:
                from researchhq.llm import router as _r
                _r.router = _r.LLMRouter()
            except Exception:  # noqa: BLE001
                pass

        if not self._has_any_provider_config():
            QMessageBox.warning(
                self, "No LLM provider configured",
                "Add an API key (e.g. GROQ_API_KEY) to your .env file or run a local Ollama. "
                "Open Settings to see provider status.",
            )
            return

        mode = self._mode.currentData()
        fmt = self._format.currentData()
        effort = self._effort.currentData() or DEFAULT_EFFORT

        self._pipeline.reset()
        self._logs.clear()
        self._reset_stats()
        self._enable_exports(False)
        self._set_running(True)

        export_fmt = fmt if fmt != "pdf" else "markdown"  # save as markdown; PDF is on-demand

        self._worker = ResearchWorker(
            mode=mode, query=query, export_format=export_fmt,
            workspace="default", effort=effort, parent=self,
        )
        self._worker.stage.connect(self._pipeline.on_stage)
        self._worker.live_stats.connect(self._update_stats)
        self._worker.finished_ok.connect(self._on_done)
        self._worker.failed.connect(self._on_failed)
        self._worker.canceled.connect(self._on_canceled)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.request_cancel()
            self._cancel_btn.setEnabled(False)

    def _on_save_default(self) -> None:
        if self._last_report is None:
            return
        fmt = self._format.currentData()
        if fmt == "pdf":
            self._export_pdf()
        else:
            self._export(fmt)

    def _on_done(self, report: ResearchReport, saved_path: str) -> None:
        self._last_report = report
        self._pipeline.mark_done()
        self._set_running(False)
        self._viewer.show_report(
            report.model_dump(mode="json"),
            to_markdown(report),
            logs_text=self._logs._view.toPlainText(),
        )
        self._enable_exports(True)
        self._logs.append("INFO", f"Saved report: {saved_path}")
        self.run_finished.emit()

    def _on_failed(self, message: str, tb: str) -> None:
        self._pipeline.mark_failed(message)
        self._set_running(False)
        self._logs.append("ERROR", message)
        if tb:
            self._logs.append("DEBUG", tb)
        QMessageBox.critical(self, "Research failed", message + "\n\nSee log panel for details.")

    def _on_canceled(self) -> None:
        self._pipeline.mark_canceled()
        self._set_running(False)
        self._logs.append("WARNING", "Run canceled by user.")

    # --------------- helpers ---------------
    def _set_running(self, running: bool) -> None:
        self._run_btn.setEnabled(not running)
        self._cancel_btn.setEnabled(running)
        for w in (self._query, self._mode, self._provider, self._max_sources,
                  self._depth, self._effort, self._format, self._preset_box):
            w.setEnabled(not running)

    def _enable_exports(self, on: bool) -> None:
        for b in (self._btn_md, self._btn_json, self._btn_html, self._btn_pdf,
                  self._btn_copy_full, self._btn_copy_summary):
            b.setEnabled(on)

    def _has_any_provider_config(self) -> bool:
        # Always at least Ollama; remote keys may be missing but that's fine.
        return True

    def _reset_stats(self) -> None:
        self._stat_widgets["elapsed"].setText("0.0s")
        self._stat_widgets["agent"].setText("-")
        self._stat_widgets["sources"].setText("0")
        self._stat_widgets["llm_calls"].setText("0")
        self._stat_widgets["tokens"].setText("0/0")
        self._stat_widgets["cost"].setText("$0.0000")

    def _update_stats(self, s: dict) -> None:
        self._stat_widgets["elapsed"].setText(f"{s.get('elapsed_s', 0):.1f}s")
        self._stat_widgets["agent"].setText(s.get("agent") or "-")
        self._stat_widgets["sources"].setText(str(s.get("sources", 0)))
        self._stat_widgets["llm_calls"].setText(str(s.get("llm_calls", 0)))
        self._stat_widgets["tokens"].setText(
            f"{s.get('input_tokens', 0)}/{s.get('output_tokens', 0)}"
        )
        self._stat_widgets["cost"].setText(f"${s.get('equivalent_cost_usd', 0.0):.4f}")

    def _export(self, fmt: str) -> None:
        if self._last_report is None:
            return
        ext = {"markdown": ".md", "json": ".json", "html": ".html"}[fmt]
        path, _ = QFileDialog.getSaveFileName(
            self, "Save report",
            f"{self._last_report.mode}__{_slug(self._last_report.query)}{ext}",
            f"*{ext}",
        )
        if not path:
            return
        text = {"markdown": to_markdown, "json": to_json, "html": to_html}[fmt](self._last_report)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            self._logs.append("INFO", f"Exported: {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(e))

    def _export_pdf(self) -> None:
        """PDF via QTextDocument print → QPrinter (no extra deps)."""
        if self._last_report is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save PDF",
            f"{self._last_report.mode}__{_slug(self._last_report.query)}.pdf",
            "*.pdf",
        )
        if not path:
            return
        try:
            from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
            from PySide6.QtPrintSupport import QPrinter

            doc = QTextDocument()
            doc.setMarkdown(to_markdown(self._last_report))
            printer = QPrinter(QPrinter.PrinterMode.PrinterResolution)
            printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
            printer.setOutputFileName(path)
            printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)
            doc.print_(printer)
            self._logs.append("INFO", f"Exported PDF: {path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "PDF export failed", str(e))

    def _copy_full(self) -> None:
        if self._last_report is None:
            return
        QGuiApplication.clipboard().setText(to_markdown(self._last_report))
        self._logs.append("INFO", "Full report copied to clipboard.")

    def _copy_summary(self) -> None:
        if self._last_report is None:
            return
        exec_section = next(
            (s for s in self._last_report.sections
             if s.heading.lower().startswith("executive")), None,
        )
        text = exec_section.body if exec_section else to_markdown(self._last_report)
        QGuiApplication.clipboard().setText(text)
        self._logs.append("INFO", "Executive summary copied to clipboard.")


def _slug(s: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "report"
