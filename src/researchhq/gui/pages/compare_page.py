"""Compare page: pick 2 reports from history, render side by side, export combined markdown.

For MVP we compare existing saved reports rather than running new pipelines from inside
this page. Users can run the underlying queries on the Research page first.
"""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
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

from researchhq import history as histdb
from researchhq.reports.exporter import to_markdown
from researchhq.reports.schema import ResearchReport


class ComparePage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        title = QLabel("Compare reports")
        title.setStyleSheet("font-size: 20px; font-weight: 700; background: transparent;")
        outer.addWidget(title)

        sub = QLabel("Pick two saved reports to view side by side. To create a new report, use Research.")
        sub.setStyleSheet("color: #8a96a8; background: transparent;")
        outer.addWidget(sub)

        controls = QHBoxLayout()
        self._left = QComboBox()
        self._right = QComboBox()
        self._left.setMinimumWidth(280)
        self._right.setMinimumWidth(280)
        controls.addWidget(QLabel("A")); controls.addWidget(self._left, 1)
        controls.addWidget(QLabel("vs")); controls.addWidget(self._right, 1)
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
        try:
            rows = histdb.list_runs(workspace="all", limit=400)
        except Exception:  # noqa: BLE001
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

    def _on_compare(self) -> None:
        a = self._left.currentData()
        b = self._right.currentData()
        if not a or not b:
            QMessageBox.information(self, "Pick two", "Select a report on each side.")
            return
        try:
            self._loaded_left = json.loads(Path(a).read_text(encoding="utf-8"))
            self._loaded_right = json.loads(Path(b).read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", str(e))
            return
        self._left_view.setMarkdown(self._render_md(self._loaded_left))
        self._right_view.setMarkdown(self._render_md(self._loaded_right))

    def _render_md(self, data: dict) -> str:
        try:
            return to_markdown(ResearchReport.model_validate(data))
        except Exception:  # noqa: BLE001
            return f"# {data.get('query', '')}\n\n_(report could not be parsed)_"

    def _on_export(self) -> None:
        if not (self._loaded_left and self._loaded_right):
            QMessageBox.information(self, "Nothing to export", "Run Compare first.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save comparison",
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
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Export failed", str(e))


def _slug(s: str) -> str:
    cleaned = "".join(c.lower() if c.isalnum() else "_" for c in s).strip("_")
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned or "x"
