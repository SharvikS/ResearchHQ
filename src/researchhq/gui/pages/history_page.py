"""History page: DB-backed list with search/filter, open, delete, duplicate-to-research."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from researchhq import history as histdb
from researchhq.gui.state import delete_report

ALL_MODES = ["all", "topic", "company", "competitor", "technology", "market", "news", "academic"]


class HistoryPage(QWidget):
    open_report_path = Signal(str)
    duplicate_to_research = Signal(str, str)  # (query, mode)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        title = QLabel("History")
        title.setStyleSheet("font-size: 20px; font-weight: 700; background: transparent;")
        outer.addWidget(title)

        controls = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search query / mode / provider...")
        self._search.textChanged.connect(self._refresh)
        controls.addWidget(self._search, 2)

        self._workspace = QComboBox()
        self._workspace.addItem("default")
        self._workspace.currentTextChanged.connect(lambda _t: self._refresh())
        controls.addWidget(QLabel("Workspace"))
        controls.addWidget(self._workspace, 1)

        self._mode = QComboBox()
        self._mode.addItems(ALL_MODES)
        self._mode.currentTextChanged.connect(lambda _t: self._refresh())
        controls.addWidget(QLabel("Mode"))
        controls.addWidget(self._mode, 1)

        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self.refresh)
        controls.addWidget(refresh)

        reindex = QPushButton("Reindex")
        reindex.setToolTip("Rebuild the history index from files in the reports folder.")
        reindex.clicked.connect(self._on_reindex)
        controls.addWidget(reindex)

        outer.addLayout(controls)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels(
            ["Mode", "Query", "Provider", "Confidence", "Sources", "Cost (eq)", "Generated"]
        )
        self._table.setAlternatingRowColors(True)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        h = self._table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self._table.cellDoubleClicked.connect(self._on_open)
        outer.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._open_btn = QPushButton("Open")
        self._open_btn.clicked.connect(lambda: self._on_open(self._table.currentRow(), 0))
        actions.addWidget(self._open_btn)
        self._dup_btn = QPushButton("Duplicate query")
        self._dup_btn.setToolTip("Open the Research page pre-filled with this query and mode.")
        self._dup_btn.clicked.connect(self._on_duplicate)
        actions.addWidget(self._dup_btn)
        self._del_btn = QPushButton("Delete")
        self._del_btn.setObjectName("Danger")
        self._del_btn.clicked.connect(self._on_delete)
        actions.addWidget(self._del_btn)
        actions.addStretch(1)
        self._empty_label = QLabel("")
        self._empty_label.setStyleSheet("color: #8a96a8; background: transparent;")
        actions.addWidget(self._empty_label)
        outer.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        self._refresh_workspaces()
        self._refresh()

    def _refresh_workspaces(self) -> None:
        current = self._workspace.currentText()
        try:
            workspaces = histdb.list_workspaces()
        except Exception:  # noqa: BLE001
            workspaces = ["default"]
        self._workspace.blockSignals(True)
        self._workspace.clear()
        for w in workspaces:
            self._workspace.addItem(w)
        if current and current in workspaces:
            self._workspace.setCurrentText(current)
        self._workspace.blockSignals(False)

    def _refresh(self) -> None:
        text = self._search.text().strip() or None
        mode = self._mode.currentText()
        ws = self._workspace.currentText() or "default"
        try:
            rows = histdb.list_runs(workspace=ws, mode=None if mode == "all" else mode, text=text)
        except Exception as e:  # noqa: BLE001
            self._empty_label.setText(f"History DB error: {e}")
            self._table.setRowCount(0)
            return

        self._table.setRowCount(0)
        for r in rows:
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(r.mode))
            q = QTableWidgetItem(r.query)
            q.setData(Qt.ItemDataRole.UserRole, r.json_path)
            q.setData(Qt.ItemDataRole.UserRole + 1, r.mode)
            q.setToolTip(r.json_path)
            self._table.setItem(row, 1, q)
            self._table.setItem(row, 2, QTableWidgetItem(r.provider or "-"))
            conf = "-" if r.confidence is None else f"{r.confidence:.2f}"
            self._table.setItem(row, 3, QTableWidgetItem(conf))
            self._table.setItem(row, 4, QTableWidgetItem(str(r.sources_count)))
            self._table.setItem(row, 5, QTableWidgetItem(f"${r.equivalent_cost_usd:.4f}"))
            self._table.setItem(row, 6, QTableWidgetItem(r.generated_at[:19].replace("T", " ")))

        self._empty_label.setText(
            "No reports yet. Run one from the Research page." if not rows else ""
        )

    def _on_reindex(self) -> None:
        try:
            n = histdb.reindex_from_folder()
            self._empty_label.setText(f"Indexed {n} report(s) from disk.")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Reindex failed", str(e))
        self._refresh_workspaces()
        self._refresh()

    def _on_open(self, row: int, _col: int) -> None:
        if row < 0:
            return
        item = self._table.item(row, 1)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if path:
            self.open_report_path.emit(path)

    def _on_duplicate(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 1)
        if not item:
            return
        query = item.text()
        mode = item.data(Qt.ItemDataRole.UserRole + 1) or "topic"
        self.duplicate_to_research.emit(query, mode)

    def _on_delete(self) -> None:
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 1)
        if not item:
            return
        path = item.data(Qt.ItemDataRole.UserRole)
        if not path:
            return
        confirm = QMessageBox.question(
            self, "Delete report",
            f"Delete this report and its sibling exports?\n\n{path}",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_report(Path(path))
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Delete failed", str(e))
            return
        try:
            histdb.delete_run(path)
        except Exception:  # noqa: BLE001
            pass
        self._refresh()
