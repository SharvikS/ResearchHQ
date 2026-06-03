"""Item views with a sliding hover-indicator bar.

``QListWidget`` and ``QTableWidget`` don't expose per-item hover effects
that QSS can animate — Qt re-paints items via its delegate without any
notion of transitions. So we drop a transparent overlay onto the
view's viewport that paints a thin accent bar on the row the cursor
is currently over, and animate the bar's vertical position via a
``QPropertyAnimation`` whenever the hovered row changes.

The helper ``attach_row_hover_indicator(view)`` works on any
``QAbstractItemView`` — pass a ``QListWidget``, ``QTableWidget``, or
``QTreeView`` and you get the same effect. The two subclasses here
are thin conveniences that auto-attach the indicator on construction.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import (
    Property,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QRect,
    Qt,
)
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QAbstractItemView,
    QListWidget,
    QTableWidget,
    QWidget,
)

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme

# Width of the accent bar painted at the left edge of the hovered row.
_BAR_WIDTH = 3
# Inset from row top/bottom so the bar reads as a deliberate stripe
# instead of slamming against neighbouring rows.
_BAR_INSET = 4


class _RowHoverIndicator(QWidget):
    """Transparent overlay child of an item view's viewport.

    Paints a single thin accent stripe on the left edge of the currently
    hovered row. Its vertical position + height tween via
    ``QPropertyAnimation`` on the ``rowY`` Qt property so the bar slides
    smoothly between rows.
    """

    def __init__(self, view: QAbstractItemView) -> None:
        super().__init__(view.viewport())
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        # Sized to fill the viewport — paints its own row indicator.
        vp = view.viewport()
        self.setGeometry(0, 0, vp.width(), vp.height())
        self._view = view
        self._row_rect: QRect | None = None
        self.hide()
        ThemeManager.instance().theme_changed.connect(self.update)

        self._row_y = 0
        self._row_h = 0

        # Slide animation targets the registered ``rowY`` Qt Property
        # (defined below as a class-level descriptor). Using the
        # descriptor's name means QPropertyAnimation can locate it via
        # Qt's meta-object system.
        self._slide_anim = QPropertyAnimation(self, b"rowY")
        self._slide_anim.setDuration(scaled(180))
        self._slide_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    # ── animated Qt property ──────────────────────────────────────────
    def _get_row_y(self) -> int:
        return self._row_y

    def _set_row_y(self, v) -> None:
        self._row_y = int(v)
        self.update()

    rowY = Property(int, _get_row_y, _set_row_y)

    # ── public API ─────────────────────────────────────────────────────────

    def set_active_row(self, rect: QRect | None) -> None:
        """Move the indicator to *rect* (in viewport coords). None hides it."""
        if rect is None or rect.height() <= 0:
            self.hide()
            self._row_rect = None
            return

        new_y = rect.y() + _BAR_INSET
        new_h = max(0, rect.height() - 2 * _BAR_INSET)
        if not self.isVisible():
            # Appear instantly on first hover — no slide-from-zero glitch.
            self._row_y = new_y
            self._row_h = new_h
            self._row_rect = rect
            self.show()
            self.raise_()
            self.update()
            return

        # Same row — nothing to animate.
        if self._row_rect == rect:
            return

        self._row_h = new_h
        self._row_rect = rect
        self._slide_anim.stop()
        self._slide_anim.setStartValue(self._row_y)
        self._slide_anim.setEndValue(new_y)
        self._slide_anim.start()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        if self._row_h <= 0:
            return
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # A 3-px bar painted at the left edge with a top→middle→bottom
        # alpha gradient that fades softly at both ends.
        bar_rect = QRect(0, self._row_y, _BAR_WIDTH, self._row_h)
        path = QPainterPath()
        path.addRoundedRect(bar_rect, _BAR_WIDTH / 2, _BAR_WIDTH / 2)

        grad = QLinearGradient(0, bar_rect.top(), 0, bar_rect.bottom())
        c_dim = QColor(t.accent)
        c_dim.setAlpha(40)
        c_peak = QColor(t.accent)
        c_peak.setAlpha(255)
        grad.setColorAt(0.0, c_dim)
        grad.setColorAt(0.5, c_peak)
        grad.setColorAt(1.0, c_dim)
        p.fillPath(path, grad)


class _RowHoverFilter(QObject):
    """Event filter that watches a view's viewport for hover events and
    nudges the row indicator to the row under the cursor."""

    def __init__(self, view: QAbstractItemView, indicator: _RowHoverIndicator) -> None:
        super().__init__(view)
        self._view = view
        self._indicator = indicator
        view.viewport().setMouseTracking(True)
        view.viewport().installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt method
        if obj is not self._view.viewport():
            return False
        try:
            et = event.type()
            if et == QEvent.Type.MouseMove:
                self._update_hover(event)
            elif et == QEvent.Type.Leave:
                self._indicator.set_active_row(None)
            elif et == QEvent.Type.Resize:
                # Keep the overlay matched to the viewport size.
                vp = self._view.viewport()
                self._indicator.setGeometry(0, 0, vp.width(), vp.height())
        except RuntimeError:
            logger.debug("Row hover filter event on dying widget", exc_info=True)
        return False

    def _update_hover(self, event) -> None:
        try:
            pos = event.position().toPoint()
        except (AttributeError, TypeError):
            pos = event.pos()
        # Resolve the model index under the cursor → row geometry.
        index = self._view.indexAt(pos)
        if not index.isValid():
            self._indicator.set_active_row(None)
            return
        rect = self._view.visualRect(index)
        self._indicator.set_active_row(rect)


def attach_row_hover_indicator(view: QAbstractItemView) -> None:
    """Equip *view* with a sliding hover-row accent bar.

    Idempotent — calling twice on the same view is a no-op. The
    indicator widget is parented to the view's viewport so its
    lifecycle is automatically tied to the view's."""
    if getattr(view, "_rhq_row_hover", None) is not None:
        return
    indicator = _RowHoverIndicator(view)
    filt = _RowHoverFilter(view, indicator)
    view._rhq_row_hover = (indicator, filt)  # type: ignore[attr-defined]


# ── Drop-in subclasses ─────────────────────────────────────────────────────


class AnimatedListWidget(QListWidget):
    """QListWidget pre-wired with the row hover indicator."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        attach_row_hover_indicator(self)


class AnimatedTableWidget(QTableWidget):
    """QTableWidget pre-wired with the row hover indicator."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        attach_row_hover_indicator(self)
