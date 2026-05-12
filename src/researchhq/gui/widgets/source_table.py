"""Sources table — URL, source type/tier, credibility (score), and a relevance score."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
)


class SourceTable(QTableWidget):
    HEADERS = ["#", "Title / URL", "Source type", "Credibility", "Relevance"]

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.verticalHeader().setVisible(False)

        h = self.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.cellDoubleClicked.connect(self._open_url)

    def populate(self, sources: list[dict]) -> None:
        """`sources` items expect keys: title, url, tier, score (credibility)."""
        self.setRowCount(0)
        max_score = max((s.get("score", 0) for s in sources), default=1) or 1
        for i, s in enumerate(sources, 1):
            row = self.rowCount()
            self.insertRow(row)
            self.setItem(row, 0, QTableWidgetItem(str(i)))

            title = s.get("title") or s.get("url", "")
            url = s.get("url", "")
            cell = QTableWidgetItem(f"{title}\n{url}")
            cell.setToolTip(url)
            cell.setData(Qt.ItemDataRole.UserRole, url)
            self.setItem(row, 1, cell)

            self.setItem(row, 2, QTableWidgetItem(str(s.get("tier", "?"))))

            score = int(s.get("score", 0))
            cred = QTableWidgetItem(f"{score}")
            cred.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 3, cred)

            # Relevance: rank position is the practical relevance proxy here.
            rel_pct = int(round(100 * (1.0 - (i - 1) / max(1, len(sources)))))
            rel = QTableWidgetItem(f"{rel_pct}%")
            rel.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.setItem(row, 4, rel)

    def _open_url(self, row: int, _col: int) -> None:
        item = self.item(row, 1)
        if not item:
            return
        url = item.data(Qt.ItemDataRole.UserRole)
        if url:
            QDesktopServices.openUrl(QUrl(url))
