"""``AnimatedComboBox`` — QComboBox subclass with a rotating chevron.

Overrides ``showPopup`` / ``hidePopup`` so the dropdown arrow rotates
180° when the popup opens and rotates back when it closes. Animation
routes through a ``QPropertyAnimation`` on a single ``chevronAngle``
float, so reduce-motion collapses it cleanly.

The native QStyle arrow is suppressed via QSS (a small marker the
theme template recognises by object name); the chevron we paint
ourselves sits in the same drop-down area.
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, Qt, Property,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QComboBox

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme


class AnimatedComboBox(QComboBox):
    """ComboBox with a rotating custom chevron on open/close."""

    # Width reserved for our chevron — matches the QSS drop-down width
    # so the chevron sits inside the native drop-down area.
    _ARROW_W = 22

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # Suppress Qt's stock arrow by hiding the drop-down image —
        # the theme QSS template includes a rule for this object name.
        self.setObjectName("AnimatedComboBox")
        self._chevron_angle = 0.0    # 0 = down, 180 = up
        self._anim = QPropertyAnimation(self, b"chevronAngle", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        ThemeManager.instance().theme_changed.connect(self.update)

    # ── Qt property for the animation ──────────────────────────────────────
    def _get_angle(self) -> float: return self._chevron_angle
    def _set_angle(self, v: float) -> None:
        self._chevron_angle = float(v); self.update()
    chevronAngle = Property(float, _get_angle, _set_angle)

    # ── popup lifecycle ────────────────────────────────────────────────────

    def showPopup(self) -> None:  # noqa: N802 - Qt method
        self._animate_chevron_to(180.0, duration=260)
        super().showPopup()

    def hidePopup(self) -> None:  # noqa: N802 - Qt method
        self._animate_chevron_to(0.0, duration=240)
        super().hidePopup()

    def _animate_chevron_to(self, target: float, duration: int) -> None:
        self._anim.stop()
        self._anim.setStartValue(self._chevron_angle)
        self._anim.setEndValue(target)
        self._anim.setDuration(scaled(duration))
        self._anim.start()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, ev) -> None:  # noqa: N802 - Qt method
        # Let the QSS-styled combobox render normally first.
        super().paintEvent(ev)

        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Chevron centred in the drop-down strip on the right edge.
        cx = w - self._ARROW_W / 2 - 4
        cy = h / 2
        arm = 4.0
        pen = QPen(QColor(t.accent))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)

        # Build the chevron in local coords (apex below centre), then
        # rotate by the current angle so it flips between down and up
        # smoothly.
        p.save()
        p.translate(cx, cy)
        p.rotate(self._chevron_angle)
        # Two short lines forming a "v".
        from PySide6.QtCore import QLineF
        p.drawLine(QLineF(-arm, -arm * 0.35, 0.0, arm * 0.35))
        p.drawLine(QLineF(0.0, arm * 0.35, arm, -arm * 0.35))
        p.restore()
