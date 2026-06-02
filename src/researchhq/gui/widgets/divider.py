"""Theme-aware vertical hairline divider with a slow brightness pulse.

Sits between the sidebar and the main content area. The base appearance
is a 3-px band painted with a top→middle→bottom alpha gradient in the
accent colour. On top of that base we animate a bright "highlight"
band that sweeps slowly from top to bottom and wraps — gives the
divider a quiet sense of life without being distracting.

Repaints on theme change. Reduce-motion pauses the timer.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QSizePolicy, QWidget

from researchhq.gui.reduce_motion import ReduceMotion, is_reduced
from researchhq.gui.theme import ThemeManager, theme


# Period of one full top→bottom sweep, in seconds.
_PULSE_PERIOD_S = 6.0
# Tick frequency; 33 ms keeps the sweep smooth without burning cycles.
_TICK_MS = 33


class WorkspaceDivider(QWidget):
    """3-px vertical band with a base gradient + animated highlight sweep."""

    WIDTH = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("WorkspaceDivider")
        self.setFixedWidth(self.WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._color = QColor(theme().accent)
        self._phase = 0.0
        self._tick_s = _TICK_MS / 1000.0

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        if not is_reduced():
            self._timer.start()

        ThemeManager.instance().theme_changed.connect(self._on_theme_changed)
        ReduceMotion().changed.connect(self._on_reduce_motion)

    def _on_theme_changed(self, _t) -> None:
        try:
            self._color = QColor(theme().accent)
            self.update()
        except RuntimeError:
            logger.debug("Divider theme change on dying widget", exc_info=True)

    def _on_reduce_motion(self, reduced: bool) -> None:
        if reduced:
            self._timer.stop()
            self.update()
        elif not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        self._phase = (self._phase + self._tick_s / _PULSE_PERIOD_S) % 1.0
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # ── Base gradient — soft alpha taper at both ends.
        base = QLinearGradient(0, 0, 0, h)
        c_clear = QColor(self._color); c_clear.setAlpha(0)
        c_soft = QColor(self._color); c_soft.setAlpha(36)
        c_peak = QColor(self._color); c_peak.setAlpha(110)
        base.setColorAt(0.0, c_clear)
        base.setColorAt(0.15, c_soft)
        base.setColorAt(0.5, c_peak)
        base.setColorAt(0.85, c_soft)
        base.setColorAt(1.0, c_clear)
        p.fillRect(self.rect(), base)

        if is_reduced():
            return

        # ── Highlight band — bright cyan→magenta swatch that travels
        # downward and wraps. Its length is ~25% of the divider so the
        # base gradient is still visible above + below it.
        band_h = h * 0.25
        center_y = (h + band_h) * self._phase - band_h / 2
        # Highlight gradient localised to the band's vertical span.
        t = theme()
        hl = QLinearGradient(0, center_y - band_h / 2, 0, center_y + band_h / 2)
        a_clear = QColor(t.accent2); a_clear.setAlpha(0)
        a_peak1 = QColor(t.accent);  a_peak1.setAlpha(180)
        a_peak2 = QColor(t.accent2); a_peak2.setAlpha(150)
        hl.setColorAt(0.0, a_clear)
        hl.setColorAt(0.5, a_peak1)
        hl.setColorAt(0.7, a_peak2)
        hl.setColorAt(1.0, a_clear)
        p.fillRect(self.rect(), hl)
