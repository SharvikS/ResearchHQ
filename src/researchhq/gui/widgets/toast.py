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
# Per-toast vertical gap when multiple toasts are visible at the same time.
_STACK_GAP = 8


def _stack_for(parent: QWidget) -> list["Toast"]:
    """Return the list of live toasts parented to *parent*.

    We attach the list as an attribute on the parent so cascading
    state stays in scope for the parent's lifetime. The list is
    filtered to drop any toasts that have been destroyed."""
    stack = getattr(parent, "_rhq_toast_stack", None)
    if stack is None:
        stack = []
        parent._rhq_toast_stack = stack  # type: ignore[attr-defined]
    # Cull dead refs.
    parent._rhq_toast_stack = [t for t in stack if _alive(t)]
    return parent._rhq_toast_stack


def _alive(t) -> bool:
    try:
        t.objectName()
        return True
    except RuntimeError:
        return False


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
        caller can cancel early via ``toast.dismiss()`` if needed.

        Multiple toasts cascade — the newest is at the bottom and older
        ones slide up to make room. The stack is kept on the parent."""
        toast = cls(parent, text, kind=kind, duration_ms=duration_ms)
        stack = _stack_for(parent)
        stack.append(toast)
        # Re-layout the whole stack so older toasts shift up.
        for t in stack:
            t._update_target_for_stack(stack)
        toast._animate_in()
        QTimer.singleShot(int(duration_ms), toast.dismiss)
        return toast

    # ── public ─────────────────────────────────────────────────────────────

    def dismiss(self) -> None:
        """Slide + fade out, then self-destruct."""
        # Avoid double-dismissing — the auto-timer + user clicks could
        # both call this for the same toast.
        if getattr(self, "_dismissing", False):
            return
        self._dismissing = True

        # Remove ourselves from the parent's stack and re-layout the
        # remaining toasts so they slide DOWN into the freed slot.
        parent = self.parentWidget()
        if parent is not None:
            stack = _stack_for(parent)
            if self in stack:
                stack.remove(self)
            for t in stack:
                t._update_target_for_stack(stack)

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

    def _update_target_for_stack(self, stack: list) -> None:
        """Recompute this toast's docked position based on its index in
        the parent's stack and animate it there.

        The newest toast (last in the list) sits at the bottom; older
        ones stack up above it. When one is dismissed, the rest slide
        down to close the gap."""
        parent = self.parentWidget()
        if parent is None or self not in stack:
            return
        # Index 0 = oldest; the last toast (index -1) sits at the bottom.
        # We invert so the oldest is highest.
        index_from_bottom = len(stack) - 1 - stack.index(self)
        pw, ph = parent.width(), parent.height()
        w, h = self.width(), self.height()
        x = pw - w - _MARGIN_X
        # Each step shifts up by its own height + a gap.
        y = ph - h - _MARGIN_Y - index_from_bottom * (h + _STACK_GAP)
        self._target_pos = QPoint(x, y)
        # Off-screen entry position stays to the right of the final spot.
        self._start_pos = QPoint(pw + 8, y)

        # If we're already visible, slide to the new target.
        if self.isVisible() and not getattr(self, "_dismissing", False):
            anim = QPropertyAnimation(self, b"pos", self)
            anim.setStartValue(self.pos())
            anim.setEndValue(self._target_pos)
            anim.setDuration(scaled(180))
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            anim.start()
            self._restack_anim = anim  # type: ignore[attr-defined]

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
