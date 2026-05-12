"""Left navigation sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


class Sidebar(QFrame):
    selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(2)

        brand = QLabel("ResearchHQ Studio")
        brand.setObjectName("SidebarBrand")
        sub = QLabel("Multi-agent research")
        sub.setObjectName("SidebarBrandSub")
        layout.addWidget(brand)
        layout.addWidget(sub)

        self._buttons: dict[str, QPushButton] = {}
        for key, label in [
            ("dashboard", "  Dashboard"),
            ("research",  "  New Research"),
            ("history",   "  History"),
            ("compare",   "  Compare"),
            ("settings",  "  Settings"),
        ]:
            btn = QPushButton(label)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _checked=False, k=key: self._select(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        footer = QLabel("v0.3 · CLI compatible")
        footer.setStyleSheet("color: #5b6779; padding: 8px 12px; background: transparent;")
        layout.addWidget(footer)

    def _select(self, key: str) -> None:
        for k, b in self._buttons.items():
            b.setProperty("active", "true" if k == key else "false")
            b.style().unpolish(b); b.style().polish(b)
        self.selected.emit(key)

    def select(self, key: str) -> None:
        self._select(key)
