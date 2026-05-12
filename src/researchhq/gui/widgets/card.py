"""Card primitive: a rounded, bordered panel with title + optional subtitle and body."""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str = "", subtitle: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(16, 14, 16, 14)
        self._outer.setSpacing(8)

        if title:
            t = QLabel(title)
            t.setObjectName("CardTitle")
            self._outer.addWidget(t)
        if subtitle:
            s = QLabel(subtitle)
            s.setObjectName("CardSubtitle")
            self._outer.addWidget(s)

        self._body = QVBoxLayout()
        self._body.setContentsMargins(0, 4, 0, 0)
        self._body.setSpacing(8)
        self._outer.addLayout(self._body)

    def add(self, w: QWidget) -> None:
        self._body.addWidget(w)

    def add_layout(self, layout) -> None:
        self._body.addLayout(layout)


class StatCard(QFrame):
    """Small card for dashboard quick stats: big number + label."""

    def __init__(self, label: str, value: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)

        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        self._value = QLabel(value)
        self._value.setObjectName("StatValue")

        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, value: str) -> None:
        self._value.setText(value)
