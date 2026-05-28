"""Circular confidence indicator.

A thin arc that sweeps from 0° to (value × 360°) on mount, with the
numeric confidence rendered at the centre. Used in the dashboard's
recent-reports list and the history table where space allows.

Three colour bands:
- value >= 0.75 → success colour
- value >= 0.50 → accent colour
- otherwise      → warning colour

Reading the sweep angle through a QPropertyAnimation lets reduce-motion
collapse the animation to instant.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Property,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme


class ConfidenceRing(QWidget):
    """Confidence value displayed as a progress arc + number.

    Parameters
    ----------
    value:
        0.0 – 1.0. Clamped at the boundaries.
    size:
        Edge length in pixels. Stroke + font scale with size.
    show_label:
        When True, render the value as ``.NN`` at the centre.
    """

    def __init__(
        self,
        value: float = 0.0,
        size: int = 40,
        show_label: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._size = int(size)
        self.setFixedSize(self._size, self._size)
        self._value = max(0.0, min(1.0, float(value)))
        self._sweep = 0.0  # animated 0.0 → self._value
        self._show_label = show_label
        ThemeManager.instance().theme_changed.connect(self.update)
        self._start_sweep()

    # ── Qt property for the sweep animation ────────────────────────────────
    def _get_sweep(self) -> float: return self._sweep
    def _set_sweep(self, v: float) -> None:
        self._sweep = float(v); self.update()
    sweep = Property(float, _get_sweep, _set_sweep)

    # ── public API ─────────────────────────────────────────────────────────
    def set_value(self, value: float) -> None:
        v = max(0.0, min(1.0, float(value)))
        if v == self._value:
            return
        self._value = v
        self._start_sweep()

    # ── internals ──────────────────────────────────────────────────────────
    def _start_sweep(self) -> None:
        # Always animate from current sweep to new target so re-mounts
        # mid-stream don't snap.
        anim = QPropertyAnimation(self, b"sweep", self)
        anim.setStartValue(self._sweep)
        anim.setEndValue(self._value)
        anim.setDuration(scaled(640))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._anim = anim

    def _arc_color(self) -> QColor:
        t = theme()
        if self._value >= 0.75:
            return QColor(t.ok)
        if self._value >= 0.50:
            return QColor(t.accent)
        return QColor(t.warn)

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = float(self._size)
        cx, cy = s / 2, s / 2
        # Stroke scales with widget size so the ring stays balanced
        # whether shown at 32 px in a list or 64 px in a card header.
        stroke = max(2.0, s * 0.10)
        radius = (s - stroke) / 2

        rect = QRectF(stroke / 2, stroke / 2, s - stroke, s - stroke)

        # ── background track ─────────────────────────────────────────
        track_pen = QPen(QColor(t.border_lt))
        track_pen.setWidthF(stroke)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(track_pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawArc(rect, 0, 360 * 16)

        # ── trailing tail ────────────────────────────────────────────
        # A short, soft secondary arc that *leads* the main sweep — gives
        # the ring a sense of momentum while it's still animating in.
        # The tail only appears while the sweep is in flight (sweep is
        # under the target value or briefly after).
        sweep_deg = -int(self._sweep * 360)
        tail_len = max(8, int(36 * min(1.0, self._sweep + 0.05)))
        if self._sweep > 0.01:
            tail_color = QColor(self._arc_color())
            tail_color.setAlpha(110)
            tail_pen = QPen(tail_color)
            tail_pen.setWidthF(stroke)
            tail_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(tail_pen)
            # Tail extends slightly past the current leading edge in
            # the sweep direction. Qt arc angles use 1/16 deg; CCW.
            tail_start = 90 + sweep_deg          # leading edge of the main sweep
            p.drawArc(rect, int(tail_start * 16), int(-tail_len * 16))

        # ── value arc (main) ─────────────────────────────────────────
        # Qt arc angles use sixteenths of a degree; CCW from 3 o'clock.
        # We want CW from 12 o'clock, so start at 90° and sweep negative.
        arc_pen = QPen(self._arc_color())
        arc_pen.setWidthF(stroke)
        arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(arc_pen)
        p.drawArc(rect, int(90 * 16), sweep_deg * 16)

        # ── centre label ─────────────────────────────────────────────
        if self._show_label:
            font = QFont()
            font.setPointSizeF(max(7.0, s * 0.22))
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(t.text))
            text = f".{int(round(self._sweep * 100)):02d}"
            p.drawText(QRectF(0, 0, s, s),
                       Qt.AlignmentFlag.AlignCenter, text)
