"""Streaming log console — append-only text view with level color coding."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

LEVEL_COLORS = {
    "DEBUG":    "#8a96a8",
    "INFO":     "#a9b6c8",
    "WARNING":  "#f4b740",
    "ERROR":    "#ef5b5b",
    "CRITICAL": "#ef5b5b",
}


class LogConsole(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        controls = QHBoxLayout()
        self._debug_toggle = QCheckBox("Debug logs")
        self._debug_toggle.setToolTip(
            "Show DEBUG-level logs and HTTP/library noise. Off by default."
        )
        controls.addWidget(self._debug_toggle)
        controls.addStretch(1)
        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        controls.addWidget(clear)
        outer.addLayout(controls)

        self._view = QPlainTextEdit()
        self._view.setReadOnly(True)
        self._view.setMaximumBlockCount(2000)  # cap memory; older lines roll off
        self._view.setPlaceholderText("Live agent logs will stream here.")
        f = self._view.font()
        f.setFamily("Consolas, 'Courier New', monospace")
        self._view.setFont(f)
        outer.addWidget(self._view)

    def append(self, level: str, msg: str) -> None:
        color = LEVEL_COLORS.get(level, "#a9b6c8")
        cursor = self._view.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(msg + "\n")
        self._view.setTextCursor(cursor)
        self._view.ensureCursorVisible()

    def clear(self) -> None:
        self._view.clear()

    @property
    def debug_toggle(self) -> QCheckBox:
        return self._debug_toggle
