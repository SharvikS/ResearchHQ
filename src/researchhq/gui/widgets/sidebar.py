"""Left navigation sidebar with brand wordmark + glyph-labelled nav items."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget


# Single-character geometric glyphs that match the TUI sidebar exactly.
# Keeping the same glyph language across both UIs makes the product feel
# like one identity.
_NAV_ITEMS = [
    ("dashboard", "Dashboard",  "◈"),
    ("research",  "Research",   "⌖"),
    ("history",   "History",    "⊞"),
    ("compare",   "Compare",    "⇌"),
    ("settings",  "Settings",   "◎"),
]


class Sidebar(QFrame):
    """Vertical nav. Emits ``selected(key)`` when the active item changes."""

    selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 12)
        layout.setSpacing(2)

        # Brand area — kicker, wordmark, sub.
        kicker = QLabel("STUDIO · v0.3")
        kicker.setObjectName("SidebarBrandSub")
        kicker.setContentsMargins(8, 4, 8, 0)
        layout.addWidget(kicker)

        brand = QLabel("ResearchHQ")
        brand.setObjectName("SidebarBrand")
        layout.addWidget(brand)

        sub = QLabel("multi-agent workstation")
        sub.setObjectName("SidebarBrandSub")
        layout.addWidget(sub)

        layout.addSpacing(8)

        # Nav buttons — each is "  ◈   Dashboard" with the glyph styled
        # via QSS button text. Padding handled in the QSS theme.
        self._buttons: dict[str, QPushButton] = {}
        for key, label, glyph in _NAV_ITEMS:
            btn = QPushButton(f"  {glyph}   {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            btn.clicked.connect(lambda _checked=False, k=key: self._select(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        # Footer kicker — tiny, theme-aware via SidebarBrandSub object name.
        footer = QLabel("ready · ⌘+R for research")
        footer.setObjectName("SidebarBrandSub")
        footer.setContentsMargins(8, 4, 8, 6)
        layout.addWidget(footer)

    def _select(self, key: str) -> None:
        for k, b in self._buttons.items():
            b.setProperty("active", "true" if k == key else "false")
            # Force QSS re-evaluation so the active-state border + colour
            # take effect immediately.
            b.style().unpolish(b)
            b.style().polish(b)
        self.selected.emit(key)

    def select(self, key: str) -> None:
        self._select(key)
