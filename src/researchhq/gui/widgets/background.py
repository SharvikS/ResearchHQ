"""Painted background widget for the main window.

Replaces the flat ``QWidget`` central pane with one that overrides
``paintEvent`` to draw a subtle radial-gradient halo from the top-left
quadrant — exactly the dimensional touch the QSS can't express on its
own. Repaints on theme change.

Layout is added through the standard Qt API (``setLayout`` /
``QHBoxLayout(self)``) — children sit on top of the painted background.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from researchhq.gui.theme import ThemeManager, theme


class BackgroundWidget(QWidget):
    """Central widget that paints a deep-navy field with an accent halo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Paint a flat fill first; the gradient is composited on top.
        self.setAutoFillBackground(False)
        ThemeManager.instance().theme_changed.connect(self.update)

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # ── Base fill — solid deep colour so child widgets read crisply.
        p.fillRect(self.rect(), QColor(t.bg_base))

        # ── Top-left halo — soft radial bloom in the accent colour.
        # Placed at ~25% from the left edge, ~20% from the top, so it
        # peeks out behind the sidebar without dominating the workspace.
        halo_center = QPointF(w * 0.18, h * 0.12)
        halo_radius = max(w, h) * 0.55
        radial = QRadialGradient(halo_center, halo_radius)
        accent_glow = QColor(t.accent)
        accent_glow.setAlpha(60)
        accent_clear = QColor(t.accent)
        accent_clear.setAlpha(0)
        radial.setColorAt(0.0, accent_glow)
        radial.setColorAt(1.0, accent_clear)
        p.fillRect(self.rect(), radial)

        # ── Bottom-right halo — secondary accent, smaller + cooler. Adds
        # a second focal point so the workspace doesn't read as a single
        # tilted gradient.
        accent2_center = QPointF(w * 0.92, h * 0.95)
        accent2_radius = max(w, h) * 0.4
        radial2 = QRadialGradient(accent2_center, accent2_radius)
        a2_glow = QColor(t.accent2)
        a2_glow.setAlpha(40)
        a2_clear = QColor(t.accent2)
        a2_clear.setAlpha(0)
        radial2.setColorAt(0.0, a2_glow)
        radial2.setColorAt(1.0, a2_clear)
        p.fillRect(self.rect(), radial2)

        # ── Top-edge highlight — a 1 px gradient bar to suggest the
        # window has a subtle "light from above" relationship with its
        # chrome. Almost invisible but adds dimensionality on wide
        # monitors.
        edge = QLinearGradient(0, 0, 0, 2)
        edge_top = QColor(t.text); edge_top.setAlpha(16)
        edge_clear = QColor(t.text); edge_clear.setAlpha(0)
        edge.setColorAt(0.0, edge_top)
        edge.setColorAt(1.0, edge_clear)
        p.fillRect(0, 0, w, 2, edge)
