"""Animated status indicator dot.

Replaces the static ``● configured`` / ``○ not configured`` labels in
the dashboard's provider grid. Two states:

- ``state="on"`` — a small filled dot in the success colour with a
  slow halo pulse around it. Reads as "live and ready".
- ``state="off"`` — a hollow ring in the muted text colour. Static.

Compact (12×12 by default), composes into any layout. Uses a single
``QPropertyAnimation`` on a float halo-progress property so reduce-
motion can collapse it cleanly.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QPointF,
    QPropertyAnimation,
    Qt,
)
from PySide6.QtGui import QBrush, QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme

DotState = Literal["on", "off"]


class PulseDot(QWidget):
    """One status dot. Set state via ``set_state()`` to swap rendering."""

    def __init__(
        self,
        state: DotState = "off",
        size: int = 12,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._size = int(size)
        self.setFixedSize(self._size, self._size)
        self._state: DotState = state
        # 0.0 → 1.0 halo radius / alpha modulation. Driven by a looping
        # QPropertyAnimation when state == "on".
        self._pulse = 0.0
        self._anim: QPropertyAnimation | None = None
        ThemeManager.instance().theme_changed.connect(self.update)
        self._sync_animation()

    # ── Qt property for QPropertyAnimation ─────────────────────────────────
    def _get_pulse(self) -> float:
        return self._pulse

    def _set_pulse(self, v: float) -> None:
        self._pulse = float(v)
        self.update()

    pulse = Property(float, _get_pulse, _set_pulse)

    # ── public API ─────────────────────────────────────────────────────────
    def set_state(self, state: DotState) -> None:
        if state == self._state:
            return
        self._state = state
        self._sync_animation()
        self.update()

    def stop(self) -> None:
        """Halt the halo animation so the QObject doesn't tick after the
        widget is torn down."""
        if self._anim is not None:
            self._anim.stop()

    # ── internals ──────────────────────────────────────────────────────────
    def _sync_animation(self) -> None:
        """Start a looping halo pulse when state is 'on'; stop otherwise."""
        if self._anim is not None:
            self._anim.stop()
            self._anim = None

        if self._state != "on" or scaled(1) == 0:
            self._pulse = 0.0
            return

        anim = QPropertyAnimation(self, b"pulse", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(scaled(1400))
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        # Manual ping-pong loop — reverse direction on finish.
        def _reverse() -> None:
            s, e = anim.startValue(), anim.endValue()
            anim.setStartValue(e)
            anim.setEndValue(s)
            anim.start()

        anim.finished.connect(_reverse)
        anim.start()
        self._anim = anim

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = float(self._size)
        cx, cy = s / 2, s / 2
        core_r = s * 0.25

        if self._state == "on":
            # Halo — expands outward, fades out.
            halo_r = core_r + (s * 0.35) * self._pulse
            halo_alpha = int(120 * (1.0 - self._pulse))
            halo_color = QColor(t.ok)
            halo_color.setAlpha(halo_alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(halo_color))
            p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

            # Core — solid success dot.
            p.setBrush(QBrush(QColor(t.ok)))
            p.drawEllipse(QPointF(cx, cy), core_r, core_r)
        else:
            # Off — hollow ring in muted colour.
            pen = QPen(QColor(t.text_dim))
            pen.setWidthF(max(1.0, s * 0.10))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(QPointF(cx, cy), core_r, core_r)
