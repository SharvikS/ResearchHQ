"""Left navigation sidebar.

Layout
------
Brand block (logo + wordmark + subtitle) → section header → 5 nav
buttons → flexible spacer → footer pills. A single thin indicator bar
sits on top of the nav stack and animates its geometry to track the
active button, replacing the old per-button QSS active state.

Animations
----------
- Sliding accent bar (``_NavIndicator``) — geometry tweens to the
  selected button's row with ``OutCubic`` over ``DURATION.PAGE_FADE``.
- Logo runs in ``mode="idle"`` (static layout + gentle core pulse).
- Buttons themselves get hover-glow + ripple via the global motion
  installer; we don't re-instrument them here.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QPropertyAnimation,
    QRect,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from researchhq.gui.design_tokens import DURATION, EASING
from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme

# Glyphs match the TUI sidebar 1:1.
_NAV_ITEMS = [
    ("dashboard", "Dashboard", "◈"),
    ("research", "Research", "⌖"),
    ("history", "History", "⊞"),
    ("compare", "Compare", "⇌"),
    ("settings", "Settings", "◎"),
]


class _NavIndicator(QWidget):
    """Thin vertical accent bar that slides to the active nav button.

    Painted with a vertical gradient so it has a soft glow at top + bottom
    and is brightest in the middle. Repaints on theme change."""

    WIDTH = 3

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setFixedWidth(self.WIDTH)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        ThemeManager.instance().theme_changed.connect(self.update)

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        from PySide6.QtGui import QLinearGradient

        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        h = self.height()
        if h <= 0:
            return
        grad = QLinearGradient(0, 0, 0, h)
        c_dim = QColor(t.accent)
        c_dim.setAlpha(0)
        c_soft = QColor(t.accent)
        c_soft.setAlpha(80)
        c_peak = QColor(t.accent)
        c_peak.setAlpha(255)
        c_peak2 = QColor(t.accent2)
        c_peak2.setAlpha(200)
        grad.setColorAt(0.0, c_dim)
        grad.setColorAt(0.15, c_soft)
        grad.setColorAt(0.5, c_peak)
        grad.setColorAt(0.8, c_peak2)
        grad.setColorAt(1.0, c_dim)
        p.fillRect(self.rect(), grad)


class Sidebar(QFrame):
    """Vertical nav rail. Emits ``selected(key)`` on click."""

    selected = Signal(str)

    SIDEBAR_WIDTH = 240

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(self.SIDEBAR_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 14, 8, 14)
        layout.setSpacing(2)

        # ── Brand block: logo on the left, wordmark stack on the right ───
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(10, 0, 10, 0)
        brand_row.setSpacing(12)

        try:
            from researchhq.gui.widgets.logo import LogoMark

            # "idle" — outer nodes + filaments static, core pulses gently.
            self._logo = LogoMark(size=40, mode="idle")
        except ImportError:  # pragma: no cover
            self._logo = QWidget()
            self._logo.setFixedSize(QSize(40, 40))
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
        layout.addSpacing(14)

        section = QLabel("WORKSPACE")
        section.setObjectName("SidebarBrandSub")
        section.setContentsMargins(14, 8, 8, 4)
        layout.addWidget(section)

        # ── Nav button container — also hosts the sliding indicator ──────
        # We use a plain QWidget here so the indicator can be a child
        # whose geometry references the buttons' row positions inside
        # this same container.
        self._nav_host = QWidget(self)
        nav_layout = QVBoxLayout(self._nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(2)

        self._buttons: dict[str, QPushButton] = {}
        for key, label, glyph in _NAV_ITEMS:
            btn = QPushButton(f"  {glyph}   {label}")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFlat(True)
            btn.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _checked=False, k=key: self._select(k))
            self._buttons[key] = btn
            nav_layout.addWidget(btn)

        layout.addWidget(self._nav_host)

        # Sliding indicator — sits as a child of the nav host so it can
        # use that widget's coordinate space. Geometry is computed in
        # _move_indicator() after first show.
        self._indicator = _NavIndicator(self._nav_host)
        self._indicator.hide()
        self._indicator_anim: QPropertyAnimation | None = None
        self._active_key: str | None = None

        layout.addStretch(1)

        # ── Footer pills (two stacked lines so nothing truncates) ─────────
        version = QLabel("STUDIO · v0.3")
        version.setObjectName("SidebarBrandSub")
        version.setContentsMargins(14, 4, 8, 0)
        layout.addWidget(version)

        hint = QLabel("⌘K · command palette")
        hint.setObjectName("SidebarBrandSub")
        hint.setContentsMargins(14, 0, 8, 4)
        layout.addWidget(hint)

    # ── public API ─────────────────────────────────────────────────────────

    def _select(self, key: str) -> None:
        if key not in self._buttons:
            return
        prev = self._active_key
        self._active_key = key
        # Visually mark the active button so its label colour changes
        # via the QSS [active="true"] selector. The slide bar still does
        # the heavy lifting; the QSS rule now just recolours the text.
        for k, b in self._buttons.items():
            b.setProperty("active", "true" if k == key else "false")
            b.style().unpolish(b)
            b.style().polish(b)
        self._move_indicator(animate=prev is not None)
        self.selected.emit(key)

    def select(self, key: str) -> None:
        self._select(key)

    # ── internals ──────────────────────────────────────────────────────────

    def showEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().showEvent(event)
        # Compute the indicator's initial position after the layout
        # has settled. One-shot — subsequent selections animate.
        QTimer.singleShot(0, lambda: self._move_indicator(animate=False))

    def _move_indicator(self, *, animate: bool) -> None:
        if self._active_key is None:
            return
        btn = self._buttons.get(self._active_key)
        if btn is None or btn.height() == 0:
            return
        # Target rect = a thin bar on the LEFT edge of the active button,
        # vertically inset 6 px top + bottom so it doesn't slam against
        # adjacent rows.
        x = 0
        y_inset = 6
        target = QRect(x, btn.y() + y_inset, _NavIndicator.WIDTH, btn.height() - 2 * y_inset)

        if not self._indicator.isVisible():
            self._indicator.setGeometry(target)
            self._indicator.show()
            self._indicator.raise_()
            return

        if not animate:
            self._indicator.setGeometry(target)
            return

        # Animate the indicator's geometry to the new row.
        anim = QPropertyAnimation(self._indicator, b"geometry", self)
        anim.setStartValue(self._indicator.geometry())
        anim.setEndValue(target)
        anim.setDuration(scaled(DURATION.PAGE_FADE))
        anim.setEasingCurve(EASING.OUT)
        # Cancel any prior in-flight slide so the latest selection wins.
        if self._indicator_anim is not None:
            self._indicator_anim.stop()
        anim.start()
        self._indicator_anim = anim
