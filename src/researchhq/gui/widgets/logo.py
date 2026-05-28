"""ResearchHQ brand mark.

A custom-painted geometric logo, used at multiple sizes:
- 16-32 px in the sidebar header and as the window/dock icon
- 80-128 px at the centre of the splash screen
- Anywhere else a brand glyph is helpful

Design
------
Two concentric arcs (a 220° outer ring + a 200° inner ring, rotated 35°)
wrapped around a diamond-shaped central node and a bright accent dot.
The outer ring uses the primary brand colour; the inner ring uses the
secondary accent. When animated, the rings rotate at slightly different
constant speeds in opposite directions so the mark feels alive without
being distracting (1 full rev / 12s and 1 / 18s).

Public surface
--------------
- ``LogoMark(size=64, animated=True)``     a QWidget you can drop into any
                                           layout
- ``logo_icon(size=64, animated=False)``   returns a flat ``QIcon`` of the
                                           mark for use as a window icon
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QTimer, Qt
from PySide6.QtGui import (
    QBrush, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap,
)
from PySide6.QtWidgets import QWidget

from researchhq.gui.theme import ThemeManager, theme


class LogoMark(QWidget):
    """The ResearchHQ geometric brand mark.

    Parameters
    ----------
    size:
        Edge length in pixels — the widget is square. Internally we paint
        with floating-point coordinates so the mark scales cleanly from
        16 px (sidebar) to 256 px (splash).
    animated:
        When True a 24 Hz timer rotates the two rings at different speeds
        in opposite directions. When False the mark is static (used for
        the dock icon and other one-shot rasterisations).
    """

    def __init__(
        self,
        size: int = 64,
        animated: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._size = int(size)
        self.setFixedSize(self._size, self._size)
        # Outer / inner ring rotation angles, in degrees. They tick
        # independently so the rings appear to drift past each other.
        self._a_outer = 0.0
        self._a_inner = 90.0
        self._animated = animated

        # Theme refresh — repaint when the user switches palette.
        ThemeManager.instance().theme_changed.connect(self._on_theme)

        if animated:
            self._timer = QTimer(self)
            self._timer.setInterval(42)  # ≈24 Hz, smooth but cheap
            self._timer.timeout.connect(self._tick)
            self._timer.start()

    # ── lifecycle ──────────────────────────────────────────────────────

    def _tick(self) -> None:
        # 1 rev / 12s outer, 1 rev / 18s inner — in opposite directions.
        # 360° / (12 s × 24 fps) ≈ 1.25° per frame.
        self._a_outer = (self._a_outer + 1.25) % 360
        self._a_inner = (self._a_inner - 0.83) % 360
        self.update()

    def _on_theme(self, _t) -> None:
        self.update()

    # ── public API ─────────────────────────────────────────────────────

    def stop(self) -> None:
        """Halt the rotation timer (used when the splash is closing)."""
        if self._animated:
            self._timer.stop()

    def to_pixmap(self) -> QPixmap:
        """Rasterise the current frame to a transparent pixmap. Used by
        ``logo_icon`` to mint a window icon."""
        pm = QPixmap(self._size, self._size)
        pm.fill(Qt.GlobalColor.transparent)
        # Render this widget into the pixmap directly — fast and exact.
        self.render(pm)
        return pm

    # ── painting ───────────────────────────────────────────────────────

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = float(self._size)
        cx, cy = s / 2, s / 2

        # Stroke widths scale with size so the mark reads cleanly at any
        # resolution. Min 1 px, max 4 px.
        outer_w = max(1.0, min(4.0, s * 0.045))
        inner_w = max(1.0, min(3.5, s * 0.038))

        # ── outer ring — 220° arc, accent (cyan) ───────────────────────
        margin_o = s * 0.10
        rect_o = QRectF(margin_o, margin_o, s - 2 * margin_o, s - 2 * margin_o)
        pen_o = QPen(QColor(t.accent))
        pen_o.setWidthF(outer_w)
        pen_o.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_o)
        # Qt arcs use sixteenths of a degree; angles are CCW from 3 o'clock.
        p.drawArc(rect_o, int(self._a_outer * 16), int(220 * 16))

        # ── inner ring — 200° arc, accent2 (magenta) ───────────────────
        margin_i = s * 0.22
        rect_i = QRectF(margin_i, margin_i, s - 2 * margin_i, s - 2 * margin_i)
        pen_i = QPen(QColor(t.accent2))
        pen_i.setWidthF(inner_w)
        pen_i.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen_i)
        p.drawArc(rect_i, int(self._a_inner * 16), int(200 * 16))

        # ── central diamond — rotated square, gradient fill ────────────
        diamond_half = s * 0.16
        p.save()
        p.translate(cx, cy)
        p.rotate(45)
        diamond = QRectF(-diamond_half, -diamond_half,
                         2 * diamond_half, 2 * diamond_half)
        grad = QLinearGradient(diamond.topLeft(), diamond.bottomRight())
        grad.setColorAt(0.0, QColor(t.accent))
        grad.setColorAt(1.0, QColor(t.accent2))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(t.bg_deep), max(1.0, s * 0.018)))
        p.drawRoundedRect(diamond, s * 0.02, s * 0.02)
        p.restore()

        # ── central dot — bright text colour, the focal point ──────────
        dot_r = max(1.0, s * 0.035)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(QColor(t.text)))
        p.drawEllipse(QPointF(cx, cy), dot_r, dot_r)


def logo_icon(size: int = 64) -> QIcon:
    """Return a static ``QIcon`` rasterised from the brand mark.

    Used for the application/dock/window icon. The icon is captured
    while the mark is at its default orientation (no rotation drift)."""
    mark = LogoMark(size=size, animated=False)
    pm = mark.to_pixmap()
    return QIcon(pm)
