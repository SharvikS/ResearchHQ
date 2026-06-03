"""Animated indeterminate progress bar.

Replaces the stock QProgressBar (range 0,0) chunk with a custom-painted
moving gradient that flows left-to-right across the track. The flow
loops continuously so the user knows work is happening, but the
animation is subtle enough not to distract.

Use this anywhere we want a "busy" affordance during background work
(history refresh, dashboard snapshot, PDF export).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from researchhq.gui.reduce_motion import ReduceMotion, is_reduced
from researchhq.gui.theme import ThemeManager, theme


class AnimatedBusyBar(QWidget):
    """A 4-px-tall indeterminate progress bar.

    The bar shows a moving gradient when ``running == True``; otherwise
    it's hidden (so call sites can simply ``.start()`` / ``.stop()``
    around their async work)."""

    HEIGHT = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT)
        # Default to ~140 px wide so it slots beside a page title; pages
        # can override with setFixedWidth or setMaximumWidth.
        self.setMaximumWidth(160)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._phase = 0.0  # 0.0 → 1.0 → wraps
        self._running = False
        self._timer = QTimer(self)
        self._timer.setInterval(30)  # ~33 fps — flow looks smooth at this rate
        self._timer.timeout.connect(self._tick)

        ReduceMotion().changed.connect(self._on_reduce_motion)
        ThemeManager.instance().theme_changed.connect(self.update)
        self.hide()

    def _on_reduce_motion(self, _v: bool) -> None:
        # When reduce-motion flips, pause/resume the timer to match the
        # current running state.
        if self._running:
            if is_reduced():
                self._timer.stop()
            elif not self._timer.isActive():
                self._timer.start()
            self.update()

    def _tick(self) -> None:
        # Move the gradient origin right by ~2% per frame. At 33 fps
        # this is a full cycle every ~1.5 s — a comfortable flow rate.
        self._phase = (self._phase + 0.022) % 1.0
        self.update()

    # ── public API ─────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self.show()
        if not is_reduced():
            self._timer.start()
        self.update()

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._timer.stop()
        self.hide()

    @property
    def running(self) -> bool:
        return self._running

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # Round the bar's track so it reads as a slim pill.
        path = QPainterPath()
        path.addRoundedRect(0, 0, w, h, h / 2, h / 2)
        p.setClipPath(path)

        # ── Track fill ──────────────────────────────────────────────
        p.fillRect(0, 0, w, h, QColor(t.bg_hover))

        if not self._running:
            return

        # ── Moving gradient highlight ───────────────────────────────
        # The gradient is roughly 40% of the bar wide; it slides from
        # off-screen-left across to off-screen-right and wraps. We do
        # this by giving the linear gradient a start point that's
        # phase-offset by (-band_w → w) so the band travels.
        band_w = w * 0.4
        x0 = -band_w + (w + band_w) * self._phase
        x1 = x0 + band_w

        grad = QLinearGradient(x0, 0, x1, 0)
        c_clear = QColor(t.accent)
        c_clear.setAlpha(0)
        c_peak = QColor(t.accent)
        c_peak.setAlpha(255)
        c_tail = QColor(t.accent2)
        c_tail.setAlpha(180)
        grad.setColorAt(0.0, c_clear)
        grad.setColorAt(0.5, c_peak)
        grad.setColorAt(1.0, c_tail)
        p.fillRect(0, 0, w, h, grad)
