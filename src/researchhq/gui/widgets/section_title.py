"""Animated section title with a slow gradient underline sweep.

Replaces the plain QLabel previously used for card titles. The text is
rendered normally; a 1-px-tall gradient bar sits directly under the
baseline and slides a small accent2 → accent → accent2 highlight from
left to right on a long loop. The effect is whisper-quiet — you only
notice it if you stop to look — but it makes the workspace feel alive.

Use it as a drop-in replacement for ``QLabel`` in card headers:

    title = SectionTitle("Recent reports")
    title.setObjectName("CardTitle")  # picks up CardTitle QSS

The class extends ``QLabel`` (so QSS styling still applies) and only
adds a paint hook for the underline sweep.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QRectF, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QLabel

from researchhq.gui.reduce_motion import is_reduced, ReduceMotion
from researchhq.gui.theme import ThemeManager, theme


# Long period so the sweep never feels frantic. 7s for a full traverse.
_SWEEP_PERIOD_S = 7.0
_TICK_INTERVAL_MS = 60   # ~16 fps — fine for an ambient sweep
_UNDERLINE_HEIGHT = 1.5


class SectionTitle(QLabel):
    """QLabel with a slow gradient sweep painted under the baseline."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self._phase = 0.0
        self._tick_s = _TICK_INTERVAL_MS / 1000.0
        # Tracks whether the sweep is allowed to draw. Disable when
        # reduce-motion is on.
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        if not is_reduced():
            self._timer.start()

        ReduceMotion().changed.connect(self._on_reduce_motion)
        ThemeManager.instance().theme_changed.connect(self.update)

    def _on_reduce_motion(self, reduced: bool) -> None:
        if reduced:
            self._timer.stop()
            self.update()
        elif not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        # phase walks 0 → 1 over the full period, then wraps.
        self._phase = (self._phase + self._tick_s / _SWEEP_PERIOD_S) % 1.0
        self.update()

    def paintEvent(self, ev) -> None:  # noqa: N802 - Qt method
        # Let QLabel render the text + any QSS-derived background first.
        super().paintEvent(ev)
        if is_reduced():
            return

        # Then draw the underline sweep just below the text baseline.
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # Underline sits 1 px below the visible text baseline. We
        # approximate that by placing it at (h - 2) to (h - 2 + height).
        y = max(0, h - 4)
        bar = QRectF(0, y, w, _UNDERLINE_HEIGHT)

        # Moving gradient: highlight is ~25% of the width wide, sliding
        # from off-screen-left to off-screen-right and wrapping.
        band_w = w * 0.30
        x0 = -band_w + (w + band_w) * self._phase
        x1 = x0 + band_w

        grad = QLinearGradient(x0, 0, x1, 0)
        c_clear = QColor(t.accent2); c_clear.setAlpha(0)
        c_peak  = QColor(t.accent);  c_peak.setAlpha(180)
        c_tail  = QColor(t.accent2); c_tail.setAlpha(110)
        grad.setColorAt(0.0, c_clear)
        grad.setColorAt(0.5, c_peak)
        grad.setColorAt(1.0, c_tail)
        p.fillRect(bar, grad)
