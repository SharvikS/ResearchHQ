"""Report viewer with tabs: Executive Summary | Full Report | Sources | Evidence | JSON | Logs."""

from __future__ import annotations

import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHeaderView,
    QPlainTextEdit,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from researchhq.gui.widgets.source_table import SourceTable


class ReportViewer(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._tabs = QTabWidget()

        self._summary = QTextBrowser()
        self._summary.setOpenExternalLinks(True)
        self._tabs.addTab(self._summary, "Executive Summary")

        self._full = QTextBrowser()
        self._full.setOpenExternalLinks(True)
        self._tabs.addTab(self._full, "Full Report")

        self._sources = SourceTable()
        self._tabs.addTab(self._sources, "Sources")

        self._evidence = QTableWidget(0, 4)
        self._evidence.setHorizontalHeaderLabels(["Rule / Violation", "Severity", "Status", "Detail"])
        self._evidence.setAlternatingRowColors(True)
        self._evidence.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._evidence.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._evidence.verticalHeader().setVisible(False)
        h = self._evidence.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._tabs.addTab(self._evidence, "Evidence")

        self._json = QPlainTextEdit()
        self._json.setReadOnly(True)
        self._tabs.addTab(self._json, "JSON")

        self._logs_tab = QPlainTextEdit()
        self._logs_tab.setReadOnly(True)
        self._tabs.addTab(self._logs_tab, "Logs")

        layout.addWidget(self._tabs)
        self._placeholder("No report loaded yet. Run a research query or open one from History.")

    def _placeholder(self, text: str) -> None:
        self._summary.setMarkdown(f"### Welcome\n\n{text}")
        self._full.setMarkdown("")
        self._sources.populate([])
        self._evidence.setRowCount(0)
        self._json.setPlainText("")
        self._logs_tab.setPlainText("")

    def show_report(self, report_dict: dict, full_markdown: str, logs_text: str | None = None) -> None:
        sections = report_dict.get("sections", [])
        exec_section = next(
            (s for s in sections if s.get("heading", "").lower().startswith("executive")), None,
        )
        if exec_section:
            self._summary.setMarkdown(
                f"# {report_dict.get('query', '')}\n\n## Executive summary\n\n"
                + exec_section.get("body", "")
            )
        else:
            self._summary.setMarkdown(full_markdown)

        self._full.setMarkdown(full_markdown)
        self._sources.populate(report_dict.get("sources", []))
        self._populate_evidence(report_dict.get("verifier") or {})
        self._json.setPlainText(json.dumps(report_dict, indent=2, ensure_ascii=False))
        if logs_text is not None:
            self._logs_tab.setPlainText(logs_text)

    def current_markdown(self) -> str:
        return self._full.toMarkdown()

    def _populate_evidence(self, verifier: dict) -> None:
        rules = verifier.get("rules", []) or []
        violations = verifier.get("violations", []) or []
        self._evidence.setRowCount(0)

        for r in rules:
            row = self._evidence.rowCount()
            self._evidence.insertRow(row)
            self._evidence.setItem(row, 0, QTableWidgetItem(str(r.get("name", "?"))))
            self._evidence.setItem(row, 1, QTableWidgetItem(str(r.get("severity", ""))))
            passed = r.get("passed", False)
            status_item = QTableWidgetItem("PASS" if passed else "FAIL")
            self._evidence.setItem(row, 2, status_item)
            self._evidence.setItem(row, 3, QTableWidgetItem(str(r.get("message", ""))))

        for v in violations:
            row = self._evidence.rowCount()
            self._evidence.insertRow(row)
            kind = str(v.get("kind", "violation"))
            self._evidence.setItem(row, 0, QTableWidgetItem(f"[violation] {kind}"))
            self._evidence.setItem(row, 1, QTableWidgetItem("warn"))
            self._evidence.setItem(row, 2, QTableWidgetItem("FLAG"))
            url = v.get("url", "")
            detail = v.get("detail", "")
            text = f"{detail}{(' — ' + url) if url else ''} @ {v.get('location', '')}"
            self._evidence.setItem(row, 3, QTableWidgetItem(text))
