"""``ShimmerButton`` — primary CTA with hover-time shimmer + magnetic pull.

Two effects compose:

1. **Shimmer.** A bright accent→accent2 gradient band slides diagonally
   across the button's surface while the cursor is over it. The phase
   loops continuously; alpha cross-fades in on enter, out on leave so
   the band doesn't pop.

2. **Magnetic pull.** The button's painted contents (text + icon) shift
   a few pixels toward the cursor as it moves across the surface. The
   button geometry never changes — only the rendered translation —
   so surrounding layout stays put.

The class derives from ``QPushButton`` and keeps QSS styling intact:
the background, border, and any QSS state pseudo-classes are still
drawn by Qt's native style. Only the shimmer + magnetic translation
are added on top.

Usage::

    btn = ShimmerButton("+ New Research")
    btn.setObjectName("Primary")  # picks up the primary QSS rules
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPoint, QPointF, QPropertyAnimation,
    QTimer, Qt, Property,
)
from PySide6.QtGui import (
    QColor, QLinearGradient, QPainter, QPainterPath, QPaintEvent,
)
from PySide6.QtWidgets import QPushButton, QStyle, QStyleOptionButton, QStylePainter

from researchhq.gui.reduce_motion import is_reduced, ReduceMotion
from researchhq.gui.theme import ThemeManager, theme


class ShimmerButton(QPushButton):
    """Primary-action button with shimmer + magnetic feedback."""

    # Max distance the magnetic content offset is allowed to wander.
    MAGNETIC_LIMIT_X = 3.0
    MAGNETIC_LIMIT_Y = 2.0

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Track magnetic state — animated to/from the latest cursor
        # offset on every mouseMoveEvent.
        self._mag_x = 0.0
        self._mag_y = 0.0
        # Shimmer phase — 0.0 → 1.0 wraps continuously. Mapped to a
        # diagonal gradient origin in paintEvent.
        self._shimmer_phase = 0.0
        # Shimmer alpha — fades in on enter, out on leave so the band
        # doesn't pop into existence.
        self._shimmer_alpha = 0.0

        # Cheap timer drives the phase. The alpha + magnetic_x/y are
        # animated separately through QPropertyAnimation so they can
        # ease in / out independently of the phase loop.
        self._timer = QTimer(self)
        self._timer.setInterval(30)  # ~33 fps
        self._timer.timeout.connect(self._tick)

        self._alpha_anim = QPropertyAnimation(self, b"shimmerAlpha", self)
        self._alpha_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._mag_x_anim = QPropertyAnimation(self, b"magneticX", self)
        self._mag_x_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._mag_y_anim = QPropertyAnimation(self, b"magneticY", self)
        self._mag_y_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        ReduceMotion().changed.connect(self._on_reduce_motion)
        ThemeManager.instance().theme_changed.connect(self.update)
        # Enable hover tracking so mouseMoveEvent fires across the widget.
        self.setMouseTracking(True)

    # ── Qt properties so QPropertyAnimation can drive them ─────────────────

    def _get_phase(self) -> float: return self._shimmer_phase
    def _set_phase(self, v: float) -> None:
        self._shimmer_phase = float(v); self.update()
    shimmerPhase = Property(float, _get_phase, _set_phase)

    def _get_alpha(self) -> float: return self._shimmer_alpha
    def _set_alpha(self, v: float) -> None:
        self._shimmer_alpha = float(v); self.update()
    shimmerAlpha = Property(float, _get_alpha, _set_alpha)

    def _get_mag_x(self) -> float: return self._mag_x
    def _set_mag_x(self, v: float) -> None:
        self._mag_x = float(v); self.update()
    magneticX = Property(float, _get_mag_x, _set_mag_x)

    def _get_mag_y(self) -> float: return self._mag_y
    def _set_mag_y(self, v: float) -> None:
        self._mag_y = float(v); self.update()
    magneticY = Property(float, _get_mag_y, _set_mag_y)

    # ── lifecycle ──────────────────────────────────────────────────────────

    def _tick(self) -> None:
        # Phase moves ~2% per frame — full cycle every ~1.5 s.
        self._shimmer_phase = (self._shimmer_phase + 0.022) % 1.0
        self.update()

    def _on_reduce_motion(self, reduced: bool) -> None:
        if reduced:
            self._timer.stop()
            self._shimmer_alpha = 0.0
            self._mag_x = self._mag_y = 0.0
            self.update()

    # ── enter / leave / move ───────────────────────────────────────────────

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().enterEvent(event)
        if is_reduced():
            return
        if not self._timer.isActive():
            self._timer.start()
        self._alpha_anim.stop()
        self._alpha_anim.setStartValue(self._shimmer_alpha)
        self._alpha_anim.setEndValue(1.0)
        self._alpha_anim.setDuration(200)
        self._alpha_anim.start()

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().leaveEvent(event)
        # Fade shimmer out + magnet content back to centre. Keep the
        # timer running until alpha hits zero, then stop it in the
        # animation's finished slot.
        self._alpha_anim.stop()
        self._alpha_anim.setStartValue(self._shimmer_alpha)
        self._alpha_anim.setEndValue(0.0)
        self._alpha_anim.setDuration(240)
        try:
            self._alpha_anim.finished.disconnect()
        except RuntimeError:
            pass
        self._alpha_anim.finished.connect(self._on_alpha_zero)
        self._alpha_anim.start()

        # Magnetic snap-back to centre.
        for anim, val in ((self._mag_x_anim, "magneticX"),
                          (self._mag_y_anim, "magneticY")):
            anim.stop()
            anim.setStartValue(getattr(self, val[0].lower() + val[1:]))
            anim.setEndValue(0.0)
            anim.setDuration(220)
            anim.start()

    def _on_alpha_zero(self) -> None:
        if self._shimmer_alpha <= 0.001:
            self._timer.stop()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().mouseMoveEvent(event)
        if is_reduced():
            return
        # Cursor relative to button centre.
        cx = self.width() / 2
        cy = self.height() / 2
        try:
            pos = event.position()
            dx = float(pos.x()) - cx
            dy = float(pos.y()) - cy
        except (AttributeError, TypeError):
            p = event.pos()
            dx = float(p.x()) - cx
            dy = float(p.y()) - cy

        # Scale to ±MAGNETIC_LIMIT range — strong near centre, capped.
        target_x = max(-self.MAGNETIC_LIMIT_X,
                       min(self.MAGNETIC_LIMIT_X, dx * 0.08))
        target_y = max(-self.MAGNETIC_LIMIT_Y,
                       min(self.MAGNETIC_LIMIT_Y, dy * 0.08))

        # Animate to the new target so the magnetic pull eases smoothly
        # rather than tracking the cursor 1:1.
        self._mag_x_anim.stop()
        self._mag_x_anim.setStartValue(self._mag_x)
        self._mag_x_anim.setEndValue(target_x)
        self._mag_x_anim.setDuration(140)
        self._mag_x_anim.start()

        self._mag_y_anim.stop()
        self._mag_y_anim.setStartValue(self._mag_y)
        self._mag_y_anim.setEndValue(target_y)
        self._mag_y_anim.setDuration(140)
        self._mag_y_anim.start()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt method
        # 1. Render the native button (background, border, focus ring) at
        # the current magnetic offset. QStylePainter lets us use Qt's
        # built-in QStyle to render the button, so QSS rules still apply.
        painter = QStylePainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self._mag_x, self._mag_y)
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        painter.drawControl(QStyle.ControlElement.CE_PushButton, opt)
        painter.resetTransform()

        # 2. Composite the shimmer band on top, clipped to the rounded
        # rectangle of the button. This sits above the QSS-painted
        # surface so it reads as a moving highlight rather than a fill
        # change.
        if self._shimmer_alpha > 0.001:
            self._paint_shimmer(painter)

    def _paint_shimmer(self, painter: QPainter) -> None:
        t = theme()
        w, h = self.width(), self.height()
        # Clip to the same rounded shape the QSS uses for the button.
        # The QSS template sets border-radius: 8px on QPushButton#Primary.
        clip = QPainterPath()
        clip.addRoundedRect(0, 0, w, h, 8, 8)
        painter.save()
        painter.setClipPath(clip)

        # Diagonal gradient — origin slides from off-screen-top-left
        # through the button to off-screen-bottom-right as phase walks
        # from 0 → 1.
        span = math.hypot(w, h) + 80  # extra so the band never starts inside the button
        cx = -40 + (w + 80) * self._shimmer_phase
        cy = -40 + (h + 80) * self._shimmer_phase
        # Band thickness ~ 28% of the diagonal.
        thickness = span * 0.28
        # Gradient is perpendicular to the diagonal axis (rotate by 90°).
        # We compute the endpoints by walking from (cx,cy) along the
        # diagonal normal.
        nx = math.cos(math.radians(-30))  # angle of the band (~-30° from horizontal)
        ny = math.sin(math.radians(-30))
        x0 = cx - nx * thickness
        y0 = cy - ny * thickness
        x1 = cx + nx * thickness
        y1 = cy + ny * thickness

        grad = QLinearGradient(x0, y0, x1, y1)
        c_clear = QColor(t.accent2); c_clear.setAlpha(0)
        c_peak  = QColor(t.accent2)
        c_peak.setAlpha(int(140 * self._shimmer_alpha))
        c_tail  = QColor(t.accent); c_tail.setAlpha(int(60 * self._shimmer_alpha))
        grad.setColorAt(0.0, c_clear)
        grad.setColorAt(0.5, c_peak)
        grad.setColorAt(1.0, c_tail)
        painter.fillRect(self.rect(), grad)

        painter.restore()
