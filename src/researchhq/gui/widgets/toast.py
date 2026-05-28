"""Transient toast notification.

Frameless rounded chip parented to the main window. Slides in from the
bottom-right, sits for ~3 s, then fades out. Used for non-modal feedback
(run completed, report exported, theme changed, etc.).

Public surface
--------------
``Toast.show_message(parent, text, kind="info", duration=3000)``
    classmethod that places, animates, and self-destructs.
"""

from __future__ import annotations

from typing import Literal

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt,
)
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QWidget,
)

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import theme

ToastKind = Literal["info", "ok", "warn", "error"]

# Where to dock the toast relative to its parent (px from the parent's
# bottom-right corner).
_MARGIN_X = 24
_MARGIN_Y = 24


class Toast(QWidget):
    """One toast chip. Don't instantiate directly — use
    ``Toast.show_message()`` which manages lifecycle for you."""

    def __init__(
        self,
        parent: QWidget,
        text: str,
        kind: ToastKind = "info",
        duration_ms: int = 3000,
    ) -> None:
        super().__init__(parent)
        self._duration_ms = int(duration_ms)
        self._kind: ToastKind = kind

        # Translucent child overlay — we paint our own rounded rect via QSS
        # and add a drop shadow for elevation.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setObjectName("Toast")

        # Layout — small accent glyph on the left, message on the right.
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(10)

        glyph = QLabel(_glyph_for(kind))
        glyph.setObjectName("ToastGlyph")
        layout.addWidget(glyph)

        message = QLabel(text)
        message.setObjectName("ToastMessage")
        message.setWordWrap(False)
        layout.addWidget(message, 1)

        # Style the chip by kind — different border colour per severity.
        accent = _accent_for(kind)
        self.setStyleSheet(
            "#Toast {{"
            "  background-color: {bg};"
            "  border: 1px solid {accent};"
            "  border-radius: 10px;"
            "}}"
            "#ToastMessage {{ color: {text}; font-weight: 500; background: transparent; }}"
            "#ToastGlyph   {{ color: {accent}; font-weight: 700; background: transparent; }}"
            .format(
                bg=theme().bg_raised,
                text=theme().text,
                accent=accent,
            )
        )

        # Drop shadow — gives the chip elevation off the page below.
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 150))
        self.setGraphicsEffect(shadow)

        # Size to content. adjustSize() polls the layout for the
        # minimal hint then we use that to compute the slide-in target.
        self.adjustSize()

        # Position off-screen-right initially; the show() call will
        # animate us to the final docked position.
        self._target_pos: QPoint = QPoint(0, 0)
        self._start_pos: QPoint = QPoint(0, 0)
        self._compute_positions()

    # ── classmethod entry point ────────────────────────────────────────────

    @classmethod
    def show_message(
        cls,
        parent: QWidget,
        text: str,
        *,
        kind: ToastKind = "info",
        duration_ms: int = 3000,
    ) -> "Toast":
        """Create and show a toast on *parent*. Returns the toast so the
        caller can cancel early via ``toast.dismiss()`` if needed."""
        toast = cls(parent, text, kind=kind, duration_ms=duration_ms)
        toast._animate_in()
        QTimer.singleShot(int(duration_ms), toast.dismiss)
        return toast

    # ── public ─────────────────────────────────────────────────────────────

    def dismiss(self) -> None:
        """Slide + fade out, then self-destruct."""
        # Opacity effect for the fade — we replaced the drop-shadow with
        # opacity here because the existing graphics effect on `self` is
        # the drop shadow. Nesting effects isn't allowed, so we swap.
        self.setGraphicsEffect(None)
        op = QGraphicsOpacityEffect(self)
        op.setOpacity(1.0)
        self.setGraphicsEffect(op)

        op_anim = QPropertyAnimation(op, b"opacity", self)
        op_anim.setStartValue(1.0)
        op_anim.setEndValue(0.0)
        op_anim.setDuration(scaled(200))
        op_anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

        pos_anim = QPropertyAnimation(self, b"pos", self)
        pos_anim.setStartValue(self.pos())
        pos_anim.setEndValue(self._start_pos)
        pos_anim.setDuration(scaled(200))
        pos_anim.setEasingCurve(QEasingCurve.Type.InQuad)

        op_anim.finished.connect(self.deleteLater)
        op_anim.start(); pos_anim.start()
        # Pin refs so GC doesn't reap mid-anim.
        self._dismiss_anims = (op_anim, pos_anim)  # type: ignore[attr-defined]

    # ── internals ──────────────────────────────────────────────────────────

    def _compute_positions(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        pw, ph = parent.width(), parent.height()
        w, h = self.width(), self.height()
        # Final docked position — bottom-right with margin.
        self._target_pos = QPoint(pw - w - _MARGIN_X, ph - h - _MARGIN_Y)
        # Off-screen start — same Y, just past the right edge.
        self._start_pos = QPoint(pw + 8, ph - h - _MARGIN_Y)

    def _animate_in(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        # Recompute in case parent resized between __init__ and show.
        self._compute_positions()
        self.move(self._start_pos)
        self.show()
        self.raise_()

        anim = QPropertyAnimation(self, b"pos", self)
        anim.setStartValue(self._start_pos)
        anim.setEndValue(self._target_pos)
        anim.setDuration(scaled(240))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._slide_in = anim  # type: ignore[attr-defined]


# ── per-kind glyph + accent ────────────────────────────────────────────────


def _glyph_for(kind: ToastKind) -> str:
    return {
        "info":  "ℹ",
        "ok":    "✓",
        "warn":  "!",
        "error": "✕",
    }[kind]


def _accent_for(kind: ToastKind) -> str:
    t = theme()
    return {
        "info":  t.accent,
        "ok":    t.ok,
        "warn":  t.warn,
        "error": t.err,
    }[kind]
