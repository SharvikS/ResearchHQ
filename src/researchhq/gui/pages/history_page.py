"""History page: DB-backed list with search/filter, open, delete, duplicate-to-research.

All histdb queries (list_workspaces, list_runs, reindex_from_folder, delete_run)
run on QThreadPool — the UI never blocks waiting for SQLite. A QProgressBar
shows while a refresh is in flight.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PySide6.QtCore import QThreadPool, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from researchhq.gui.widgets.animated_list import AnimatedTableWidget

from researchhq.gui.state import delete_report
from researchhq.gui.workers.db_worker import DbCallable

logger = logging.getLogger(__name__)

ALL_MODES = ["all", "topic", "company", "competitor", "technology", "market", "news", "academic"]

# Debounce interval (ms) for type-as-you-search; avoids hammering the DB
# while the user is still typing the query.
_SEARCH_DEBOUNCE_MS = 250


@dataclass(frozen=True)
class _ListPayload:
    """Result of a list_runs query (paired with workspaces so a single round-
    trip can refresh the workspace dropdown alongside the table)."""
    workspaces: list[str]
    rows: list[Any]


def _fetch_list_payload(workspace: str, mode: str | None, text: str | None) -> _ListPayload:
    """Worker-side: pull workspaces + runs in one trip so we never re-enter
    the SQLite connection from two refresh jobs back-to-back."""
    from researchhq import history as histdb

    workspaces = histdb.list_workspaces()
    rows = histdb.list_runs(workspace=workspace, mode=mode, text=text)
    return _ListPayload(workspaces=workspaces, rows=rows)


def _reindex_then_list(workspace: str, mode: str | None, text: str | None) -> tuple[int, _ListPayload]:
    """Worker-side: reindex from disk, then re-fetch the list. Returns count."""
    from researchhq import history as histdb

    n = histdb.reindex_from_folder()
    workspaces = histdb.list_workspaces()
    rows = histdb.list_runs(workspace=workspace, mode=mode, text=text)
    return n, _ListPayload(workspaces=workspaces, rows=rows)


def _delete_run(json_path: str) -> None:
    """Worker-side: delete the DB row. Disk files are removed on the GUI side
    (delete_report) because that is synchronous, cheap, and gives immediate
    UX feedback."""
    from researchhq import history as histdb

    histdb.delete_run(json_path)


class HistoryPage(QWidget):
    open_report_path = Signal(str)
    duplicate_to_research = Signal(str, str)  # (query, mode)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool.globalInstance()
        self._refresh_inflight = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(12)

        # Title + busy indicator
        title_row = QHBoxLayout()
        title = QLabel("History")
        title.setObjectName("PageTitle")
        title_row.addWidget(title)
        self._busy = QProgressBar()
        self._busy.setObjectName("BusyBar")
        self._busy.setRange(0, 0)
        self._busy.setMaximumWidth(140)
        self._busy.setMaximumHeight(6)
        self._busy.setTextVisible(False)
        self._busy.hide()
        title_row.addWidget(self._busy)
        title_row.addStretch(1)
        outer.addLayout(title_row)

        # Filter row
        controls = QHBoxLayout()
        self._search = QLineEdit()
        self._search.setPlaceholderText("Search query / mode / provider...")

        # Debounce search input so each keystroke doesn't kick off a DB query.
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(_SEARCH_DEBOUNCE_MS)
        self._search_debounce.timeout.connect(self._refresh)
        self._search.textChanged.connect(lambda _t: self._search_debounce.start())
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

        self._reindex_btn = QPushButton("Reindex")
        self._reindex_btn.setToolTip("Rebuild the history index from files in the reports folder.")
        self._reindex_btn.clicked.connect(self._on_reindex)
        controls.addWidget(self._reindex_btn)

        outer.addLayout(controls)

        # AnimatedTableWidget paints a sliding accent bar on the
        # hovered row, matching the dashboard's recent-reports list.
        self._table = AnimatedTableWidget(0, 7)
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
        self._status_label = QLabel("")
        self._status_label.setObjectName("Muted")
        actions.addWidget(self._status_label)
        outer.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        self._refresh()

    # ------------- background-driven refresh -------------
    def _refresh(self) -> None:
        if self._refresh_inflight:
            return
        self._refresh_inflight = True
        self._busy.show()

        workspace = self._workspace.currentText() or "default"
        mode_text = self._mode.currentText()
        mode = None if mode_text == "all" else mode_text
        text = self._search.text().strip() or None

        job = DbCallable(
            lambda: _fetch_list_payload(workspace, mode, text),
            job_id="history.list",
        )
        job.signals.result.connect(self._on_list_ready)
        job.signals.error.connect(self._on_db_error)
        job.signals.finished.connect(self._on_refresh_finished)
        self._pool.start(job)

    def _on_list_ready(self, _job_id: str, payload: object) -> None:
        if not isinstance(payload, _ListPayload):
            logger.error("History list job returned unexpected type %r", type(payload))
            return
        self._sync_workspace_dropdown(payload.workspaces)
        self._render_rows(payload.rows)

    def _on_db_error(self, _job_id: str, message: str, _tb: str) -> None:
        self._status_label.setText(f"History DB error: {message}")
        self._table.setRowCount(0)

    def _on_refresh_finished(self, _job_id: str) -> None:
        self._refresh_inflight = False
        self._busy.hide()

    def _sync_workspace_dropdown(self, workspaces: list[str]) -> None:
        current = self._workspace.currentText()
        self._workspace.blockSignals(True)
        self._workspace.clear()
        for w in workspaces:
            self._workspace.addItem(w)
        if current and current in workspaces:
            self._workspace.setCurrentText(current)
        self._workspace.blockSignals(False)

    def _render_rows(self, rows: list[Any]) -> None:
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

        self._status_label.setText(
            "No reports yet. Run one from the Research page." if not rows else ""
        )

    # ------------- reindex -------------
    def _on_reindex(self) -> None:
        if self._refresh_inflight:
            return
        self._refresh_inflight = True
        self._reindex_btn.setEnabled(False)
        self._busy.show()
        self._status_label.setText("Reindexing reports folder…")

        workspace = self._workspace.currentText() or "default"
        mode_text = self._mode.currentText()
        mode = None if mode_text == "all" else mode_text
        text = self._search.text().strip() or None

        job = DbCallable(
            lambda: _reindex_then_list(workspace, mode, text),
            job_id="history.reindex",
        )
        job.signals.result.connect(self._on_reindex_done)
        job.signals.error.connect(self._on_reindex_error)
        job.signals.finished.connect(self._on_reindex_finished)
        self._pool.start(job)

    def _on_reindex_done(self, _job_id: str, payload: object) -> None:
        if not isinstance(payload, tuple) or len(payload) != 2:
            logger.error("Reindex job returned unexpected payload %r", payload)
            return
        n, list_payload = payload
        if isinstance(list_payload, _ListPayload):
            self._sync_workspace_dropdown(list_payload.workspaces)
            self._render_rows(list_payload.rows)
        self._status_label.setText(f"Indexed {n} report(s) from disk.")

    def _on_reindex_error(self, _job_id: str, message: str, _tb: str) -> None:
        QMessageBox.critical(self, "Reindex failed", message)
        self._status_label.setText("Reindex failed — see logs.")

    def _on_reindex_finished(self, _job_id: str) -> None:
        self._refresh_inflight = False
        self._reindex_btn.setEnabled(True)
        self._busy.hide()

    # ------------- row actions -------------
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

        # Sibling file delete is cheap (3 unlinks) — do it on the GUI thread
        # so the user sees immediate feedback. DB delete moves to the worker.
        try:
            delete_report(Path(path))
        except OSError as exc:
            logger.exception("Failed to remove report files for %s", path)
            QMessageBox.critical(self, "Delete failed", str(exc))
            return

        job = DbCallable(lambda: _delete_run(path), job_id="history.delete")
        job.signals.error.connect(self._on_db_error)
        job.signals.finished.connect(lambda _jid: self._refresh())
        self._pool.start(job)
