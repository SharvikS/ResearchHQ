"""Left navigation sidebar.

Layout
------
Brand block — kicker / wordmark with the animated LogoMark / sub-tag —
followed by the navigation buttons, a flexible spacer, and a footer
status pill. Everything wraps inside elide-safe labels so nothing ever
truncates mid-word at the sidebar's fixed width.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)


# Single-character geometric glyphs matched 1:1 with the TUI sidebar so
# the two interfaces look like one product family.
_NAV_ITEMS = [
    ("dashboard", "Dashboard", "◈"),
    ("research",  "Research",  "⌖"),
    ("history",   "History",   "⊞"),
    ("compare",   "Compare",   "⇌"),
    ("settings",  "Settings",  "◎"),
]


class Sidebar(QFrame):
    """Vertical nav rail. Emits ``selected(key)`` on click."""

    selected = Signal(str)

    SIDEBAR_WIDTH = 232

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 14)
        layout.setSpacing(2)

        # ── Brand block ────────────────────────────────────────────────
        # A horizontal row with the LogoMark on the left and the wordmark
        # text stacked beside it. Lazy import keeps card.py / sidebar.py
        # importable from headless test contexts.
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(8, 0, 8, 0)
        brand_row.setSpacing(10)

        try:
            from researchhq.gui.widgets.logo import LogoMark
            self._logo = LogoMark(size=36, animated=True)
        except ImportError:  # pragma: no cover - dev safety
            self._logo = QWidget()
            self._logo.setFixedSize(QSize(36, 36))
        brand_row.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignVCenter)

        wordmark_box = QVBoxLayout()
        wordmark_box.setContentsMargins(0, 0, 0, 0)
        wordmark_box.setSpacing(0)

        brand = QLabel("ResearchHQ")
        brand.setObjectName("SidebarBrand")
        brand.setContentsMargins(0, 0, 0, 0)
        wordmark_box.addWidget(brand)

        sub = QLabel("multi-agent workstation")
        sub.setObjectName("SidebarBrandSub")
        sub.setContentsMargins(0, 0, 0, 0)
        wordmark_box.addWidget(sub)
        brand_row.addLayout(wordmark_box, 1)

        layout.addLayout(brand_row)
        layout.addSpacing(12)

        # Section header.
        section = QLabel("WORKSPACE")
        section.setObjectName("SidebarBrandSub")
        section.setContentsMargins(12, 8, 8, 4)
        layout.addWidget(section)

        # ── Nav buttons ───────────────────────────────────────────────
        self._buttons: dict[str, QPushButton] = {}
        for key, label, glyph in _NAV_ITEMS:
            btn = QPushButton(f"  {glyph}   {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(36)
            btn.clicked.connect(lambda _checked=False, k=key: self._select(k))
            self._buttons[key] = btn
            layout.addWidget(btn)

        layout.addStretch(1)

        # ── Footer status pill ────────────────────────────────────────
        # Two stacked lines instead of one wide line so the text always
        # fits inside the 232-px-wide sidebar without elision.
        version = QLabel("STUDIO · v0.3")
        version.setObjectName("SidebarBrandSub")
        version.setContentsMargins(12, 4, 8, 0)
        layout.addWidget(version)

        hint = QLabel("⌘+R · new research")
        hint.setObjectName("SidebarBrandSub")
        hint.setContentsMargins(12, 0, 8, 4)
        layout.addWidget(hint)

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
