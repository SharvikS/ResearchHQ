"""Animated tooltip helper.

Qt's stock ``QToolTip`` pops instantly and feels jarring next to the
rest of the animated UI. This module provides an opt-in replacement
that's attached per-widget via ``attach_animated_tooltip(widget, text)``.

How it works
------------
* A single global ``_TooltipManager`` owns one ``_TooltipBubble``
  widget. We share one bubble across the app so we never have multiple
  tooltips fading at once.
* For each instrumented source widget, an event filter listens for
  hover events. A 500 ms timer arms on ``Enter``; if the cursor
  hasn't left by the time the timer fires, the bubble appears,
  positioned just below the source widget, and fades in.
* ``Leave`` (or movement that takes the cursor off the source) cancels
  the timer / fades the bubble out.

The helper never mutates the host widget's behaviour beyond clearing
its stock ``setToolTip`` so they don't double-trigger.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation,
    QTimer, Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QLabel, QWidget,
)

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme


# Delay before the tooltip is allowed to appear (ms). Matches Qt's
# default tooltip dwell, so behaviour feels familiar.
_HOVER_DELAY_MS = 500
# Vertical offset below the source widget for the bubble.
_OFFSET_Y = 6


class _TooltipBubble(QWidget):
    """Single shared bubble — repositioned + retitled as it's reused."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.ToolTip | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self._label = QLabel("", self)
        self._label.setObjectName("AnimatedTooltipBody")

        # Drop shadow gives the bubble elevation off whatever it sits on.
        shadow = QGraphicsDropShadowEffect(self._label)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 160))
        self._label.setGraphicsEffect(shadow)

        # Opacity effect lives on the WINDOW (this widget) not on the
        # label, so it doesn't nest with the label's drop shadow.
        self._opacity = QGraphicsOpacityEffect(self)
        self._opacity.setOpacity(0.0)
        self.setGraphicsEffect(self._opacity)

        self._fade = QPropertyAnimation(self._opacity, b"opacity", self)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._apply_qss()
        ThemeManager.instance().theme_changed.connect(self._apply_qss)

    def _apply_qss(self) -> None:
        t = theme()
        self._label.setStyleSheet(f"""
            #AnimatedTooltipBody {{
                color: {t.text};
                background-color: {t.bg_raised};
                border: 1px solid {t.border_lt};
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }}
        """)

    def show_at(self, text: str, anchor: QPoint) -> None:
        """Display this bubble showing *text* at *anchor* (screen coords)."""
        self._label.setText(text)
        self._label.adjustSize()
        # Resize the parent window to match the label exactly so the
        # drop-shadow has clean bounds.
        self.resize(self._label.size())
        self.move(anchor)
        self.show()
        self.raise_()

        self._fade.stop()
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(1.0)
        self._fade.setDuration(scaled(180))
        try:
            self._fade.finished.disconnect()
        except RuntimeError:
            pass
        self._fade.start()

    def fade_out(self) -> None:
        self._fade.stop()
        self._fade.setStartValue(self._opacity.opacity())
        self._fade.setEndValue(0.0)
        self._fade.setDuration(scaled(160))
        try:
            self._fade.finished.disconnect()
        except RuntimeError:
            pass
        self._fade.finished.connect(self.hide)
        self._fade.start()


class _TooltipManager(QObject):
    """Singleton — keeps the shared bubble + per-source state."""

    _instance: Optional["_TooltipManager"] = None

    @classmethod
    def instance(cls) -> "_TooltipManager":
        if cls._instance is None:
            cls._instance = _TooltipManager()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._bubble = _TooltipBubble()
        # Map source widget → (text, QTimer)
        self._sources: dict[QWidget, tuple[str, QTimer]] = {}

    def attach(self, widget: QWidget, text: str) -> None:
        # Clear any existing native tooltip — we own this widget's hover.
        widget.setToolTip("")

        if widget in self._sources:
            existing_text, timer = self._sources[widget]
            self._sources[widget] = (text, timer)
            return

        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(_HOVER_DELAY_MS)
        timer.timeout.connect(lambda w=widget: self._show_for(w))
        self._sources[widget] = (text, timer)
        widget.installEventFilter(self)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 - Qt method
        if obj not in self._sources:
            return False
        try:
            et = event.type()
            if et == QEvent.Type.Enter:
                _, timer = self._sources[obj]
                timer.start()
            elif et == QEvent.Type.Leave:
                _, timer = self._sources[obj]
                timer.stop()
                self._bubble.fade_out()
            elif et == QEvent.Type.Hide:
                _, timer = self._sources[obj]
                timer.stop()
                self._bubble.fade_out()
        except RuntimeError:
            # Widget was torn down underneath us.
            self._sources.pop(obj, None)
        return False

    def _show_for(self, widget: QWidget) -> None:
        if widget not in self._sources:
            return
        text, _ = self._sources[widget]
        try:
            # Anchor the bubble at the widget's bottom-left in screen coords.
            anchor = widget.mapToGlobal(QPoint(0, widget.height() + _OFFSET_Y))
        except RuntimeError:
            return
        self._bubble.show_at(text, anchor)


def attach_animated_tooltip(widget: QWidget, text: str) -> None:
    """Replace *widget*'s native tooltip with an animated bubble.

    Safe to call multiple times — re-attaching just updates the text."""
    _TooltipManager.instance().attach(widget, text)
