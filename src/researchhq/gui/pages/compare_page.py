"""Compare page: pick 2 reports from history, render side by side, export combined markdown.

For MVP we compare existing saved reports rather than running new pipelines from inside
this page. Users can run the underlying queries on the Research page first.

Report list refreshes run on QThreadPool so the dropdowns never freeze the UI.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from PySide6.QtCore import Qt, QThreadPool
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from researchhq.gui.workers.db_worker import DbCallable
from researchhq.reports.exporter import to_markdown
from researchhq.reports.schema import ResearchReport

logger = logging.getLogger(__name__)


def _list_all_runs() -> list[Any]:
    """Worker-side: pull every workspace's runs for the comparison dropdowns."""
    from researchhq import history as histdb

    return histdb.list_runs(workspace="all", limit=400)


class ComparePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._refresh_inflight = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        title = QLabel("Compare reports")
        title.setObjectName("PageTitle")
        outer.addWidget(title)

        sub = QLabel(
            "Pick two saved reports to view side by side. To create a new report, use Research."
        )
        sub.setObjectName("Muted")
        outer.addWidget(sub)

        controls = QHBoxLayout()
        self._left = QComboBox()
        self._right = QComboBox()
        self._left.setMinimumWidth(280)
        self._right.setMinimumWidth(280)
        controls.addWidget(QLabel("A"))
        controls.addWidget(self._left, 1)
        controls.addWidget(QLabel("vs"))
        controls.addWidget(self._right, 1)
        load = QPushButton("Compare")
        load.setObjectName("Primary")
        load.clicked.connect(self._on_compare)
        controls.addWidget(load)
        export = QPushButton("Export combined .md")
        export.clicked.connect(self._on_export)
        controls.addWidget(export)
        refresh = QPushButton("Refresh list")
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)
        outer.addLayout(controls)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)
        self._left_view = QTextBrowser()
        self._left_view.setOpenExternalLinks(True)
        self._right_view = QTextBrowser()
        self._right_view.setOpenExternalLinks(True)
        split.addWidget(self._left_view)
        split.addWidget(self._right_view)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 1)
        outer.addWidget(split, 1)

        self._loaded_left: dict | None = None
        self._loaded_right: dict | None = None
        self.refresh()

    def refresh(self) -> None:
        if self._refresh_inflight:
            return
        self._refresh_inflight = True
        job = DbCallable(_list_all_runs, job_id="compare.list")
        job.signals.result.connect(self._on_list_ready)
        job.signals.error.connect(self._on_db_error)
        job.signals.finished.connect(self._on_refresh_finished)
        self._pool.start(job)

    def _on_list_ready(self, _job_id: str, rows: object) -> None:
        if not isinstance(rows, list):
            logger.error("Compare list job returned unexpected type %r", type(rows))
            rows = []

        for box in (self._left, self._right):
            box.blockSignals(True)
            current = box.currentData()
            box.clear()
            if not rows:
                box.addItem("No reports yet", userData=None)
            for r in rows:
                box.addItem(f"[{r.mode}] {r.query}", userData=r.json_path)
            if current is not None:
                ix = box.findData(current)
                if ix >= 0:
                    box.setCurrentIndex(ix)
            box.blockSignals(False)

    def _on_db_error(self, _job_id: str, message: str, _tb: str) -> None:
        for box in (self._left, self._right):
            box.blockSignals(True)
            box.clear()
            box.addItem(f"Could not load list: {message}", userData=None)
            box.blockSignals(False)

    def _on_refresh_finished(self, _job_id: str) -> None:
        self._refresh_inflight = False

    def _on_compare(self) -> None:
        a = self._left.currentData()
        b = self._right.currentData()
        if not a or not b:
            QMessageBox.information(self, "Pick two", "Select a report on each side.")
            return
        try:
            self._loaded_left = json.loads(Path(a).read_text(encoding="utf-8"))
            self._loaded_right = json.loads(Path(b).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.exception("Compare failed to load one of the reports")
            QMessageBox.critical(self, "Load failed", str(exc))
            return
        self._left_view.setMarkdown(self._render_md(self._loaded_left))
        self._right_view.setMarkdown(self._render_md(self._loaded_right))

    def _render_md(self, data: dict) -> str:
        try:
            return to_markdown(ResearchReport.model_validate(data))
        except ValidationError:
            logger.debug("Compare: schema validation failed; using raw query header", exc_info=True)
            return f"# {data.get('query', '')}\n\n_(report could not be parsed)_"

    def _on_export(self) -> None:
        if not (self._loaded_left and self._loaded_right):
            QMessageBox.information(self, "Nothing to export", "Run Compare first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save comparison",
            f"compare__{_slug(self._loaded_left.get('query', 'a'))}__vs__{_slug(self._loaded_right.get('query', 'b'))}.md",
            "*.md",
        )
        if not path:
            return
        a_md = self._render_md(self._loaded_left)
        b_md = self._render_md(self._loaded_right)
        combined = (
            f"# Comparison\n\n"
            f"## A: {self._loaded_left.get('query', '')}\n\n{a_md}\n\n---\n\n"
            f"## B: {self._loaded_right.get('query', '')}\n\n{b_md}\n"
        )
        try:
            Path(path).write_text(combined, encoding="utf-8")
        except OSError as exc:
            logger.exception("Could not write comparison export to %s", path)
            QMessageBox.critical(self, "Export failed", str(exc))


def _slug(s: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "x"
