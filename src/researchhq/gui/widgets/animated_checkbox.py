"""Slide-toggle checkbox.

A ``QCheckBox`` subclass that paints a pill-shaped switch instead of
the standard tick box. The thumb (a small filled circle) animates
between the off and on positions through a ``QPropertyAnimation`` on
a ``thumbProgress`` float (0 = off, 1 = on). The track recolours from
muted to accent in the same animation.

The original ``QCheckBox`` checkbox indicator is suppressed via QSS
so we don't double-draw. Hit-testing + keyboard activation use the
default ``QCheckBox`` behaviour.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF, Qt, Property,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QCheckBox

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme


# Switch dimensions — track width / height, in px.
_TRACK_W = 36
_TRACK_H = 18
_THUMB_INSET = 2


class AnimatedCheckBox(QCheckBox):
    """Slide-toggle. Drop-in replacement for QCheckBox; same signals."""

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("AnimatedCheckBox")
        self._thumb_progress = 1.0 if self.isChecked() else 0.0

        # Reserve enough left margin for the painted switch so the
        # label text doesn't overlap it. QCheckBox honours
        # contentsMargins for its label.
        self.setContentsMargins(_TRACK_W + 12, 0, 0, 0)
        self.setMinimumHeight(_TRACK_H + 6)

        self._anim = QPropertyAnimation(self, b"thumbProgress", self)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.stateChanged.connect(self._on_state_changed)
        ThemeManager.instance().theme_changed.connect(self.update)

    # ── Qt property for the animation ──────────────────────────────────────

    def _get_thumb(self) -> float: return self._thumb_progress
    def _set_thumb(self, v: float) -> None:
        self._thumb_progress = float(v); self.update()
    thumbProgress = Property(float, _get_thumb, _set_thumb)

    # ── state ──────────────────────────────────────────────────────────────

    def _on_state_changed(self, state) -> None:
        target = 1.0 if self.isChecked() else 0.0
        self._anim.stop()
        self._anim.setStartValue(self._thumb_progress)
        self._anim.setEndValue(target)
        self._anim.setDuration(scaled(220))
        self._anim.start()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, ev) -> None:  # noqa: N802 - Qt method
        # 1. Let the QCheckBox text + focus rect render normally. We've
        # already pushed the text to the right via contentsMargins so
        # the switch we paint on the left doesn't collide with it.
        super().paintEvent(ev)

        # 2. Paint the pill switch in the reserved space on the left.
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Track is vertically centred in the widget.
        h = self.height()
        track_y = (h - _TRACK_H) / 2
        track_rect = QRectF(0, track_y, _TRACK_W, _TRACK_H)

        # Track colour blends from muted (off) to accent (on).
        track_off = QColor(t.bg_hover)
        track_on  = QColor(t.accent)
        track_color = _blend(track_off, track_on, self._thumb_progress)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(track_color)
        p.drawRoundedRect(track_rect, _TRACK_H / 2, _TRACK_H / 2)

        # Thumb position interpolates between left and right insets.
        thumb_d = _TRACK_H - 2 * _THUMB_INSET
        x_min = _THUMB_INSET
        x_max = _TRACK_W - thumb_d - _THUMB_INSET
        thumb_x = x_min + (x_max - x_min) * self._thumb_progress
        thumb_rect = QRectF(thumb_x, track_y + _THUMB_INSET, thumb_d, thumb_d)
        # Thumb is light by default; when "on" we recolour to the
        # window's text colour for high contrast against the accent
        # track.
        thumb_color = _blend(QColor(t.text), QColor(t.bg_deep), self._thumb_progress)
        p.setBrush(thumb_color)
        p.drawEllipse(thumb_rect)


def _blend(a: QColor, b: QColor, t: float) -> QColor:
    """Linear interpolation between two colours."""
    t = max(0.0, min(1.0, t))
    return QColor(
        int(a.red()   + (b.red()   - a.red())   * t),
        int(a.green() + (b.green() - a.green()) * t),
        int(a.blue()  + (b.blue()  - a.blue())  * t),
        int(a.alpha() + (b.alpha() - a.alpha()) * t),
    )
