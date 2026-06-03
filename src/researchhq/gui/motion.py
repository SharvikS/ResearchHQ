"""ResearchHQ Studio — global motion / interaction system.

Single source of truth for the desktop app's animation language. Every
interactive element routes hover, focus, press and page transitions
through here so the whole UI shares one timing + easing personality.

Design principles
-----------------
* **Subtle, intentional** — short durations, smooth decelerations, no
  bouncing. The app should feel like a high-end developer tool.
* **GPU friendly** — animations route through ``QPropertyAnimation``,
  ``QVariantAnimation`` and ``QGraphicsDropShadowEffect``. No per-frame
  Python loops.
* **Lazy by default** — effects attach on first hover/focus. Idle
  widgets cost nothing.
* **Theme aware** — colours pulled from the live ``ThemeManager`` and
  refreshed on theme change.

Public surface
--------------
- ``MOTION``                              tuning constants (durations, easing)
- ``install_global_motion(app)``          one-line app-wide setup
- ``attach_button_motion(btn)``           hover glow + press pulse + ripple
- ``attach_focus_glow(widget)``           focus drop-shadow on inputs/combos
- ``cross_fade(stack, new_index)``        animated swap of QStackedWidget pages
- ``fade_in(widget, duration)``           reveal helper for first-mount
- ``pulse_color(label, color, duration)`` one-shot text-colour flash
- ``Ripple``                              standalone click-ripple overlay
- ``PulseGlow``                           breathing drop-shadow used by the logo
"""

from __future__ import annotations

import logging

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QObject,
    QPoint,
    QPropertyAnimation,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QGraphicsDropShadowEffect,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QTextEdit,
    QToolButton,
    QWidget,
)

from researchhq.gui.reduce_motion import is_reduced, scaled
from researchhq.gui.theme import ThemeManager, theme

logger = logging.getLogger(__name__)


# ── Tuning constants ─────────────────────────────────────────────────────────


class MOTION:
    """Central tuning. Tweak here to retune the entire app at once."""

    # Durations (ms). Anything > 220ms feels sluggish for hover;
    # anything < 80ms reads as a glitch.
    HOVER_IN = 140
    HOVER_OUT = 180
    PRESS = 90
    RELEASE = 160
    FOCUS_IN = 160
    FOCUS_OUT = 200
    PAGE_FADE = 220
    RIPPLE = 480
    INTRO = 360
    PULSE = 1800  # full breathing cycle for the brand glow

    # Easing — sharp decel for "in", soft for "out".
    EASE_IN = QEasingCurve.Type.OutCubic
    EASE_OUT = QEasingCurve.Type.InOutQuad
    EASE_PRESS = QEasingCurve.Type.OutQuad
    EASE_PAGE = QEasingCurve.Type.InOutCubic
    EASE_RIPPLE = QEasingCurve.Type.OutCubic

    # Visual amplitudes — conservative so the UI never feels noisy.
    HOVER_BLUR = 18.0
    HOVER_BLUR_PRIM = 28.0  # primary / accent buttons get a touch more
    HOVER_ALPHA = 110
    HOVER_ALPHA_PRIM = 165
    PRESS_ALPHA = 220
    FOCUS_BLUR = 22.0
    FOCUS_ALPHA = 160


# Marker property so the global event filter never instruments a widget twice.
_INSTRUMENTED = "_rhq_motion_installed"


# ── Helpers ─────────────────────────────────────────────────────────────────


def _is_primary(btn: QWidget) -> bool:
    return (btn.objectName() or "") == "Primary"


def _is_danger(btn: QWidget) -> bool:
    return (btn.objectName() or "") == "Danger"


def _hover_color_for(widget: QWidget) -> QColor:
    t = theme()
    if _is_danger(widget):
        return QColor(t.err)
    if _is_primary(widget):
        return QColor(t.accent2)  # primary buttons glow magenta on hover
    return QColor(t.accent)


# ── Animated drop-shadow wrapper ────────────────────────────────────────────


class _GlowEffect(QGraphicsDropShadowEffect):
    """Drop-shadow with helpers for animating alpha + blur.

    Qt has no animatable QColor property on the effect itself, so we keep
    a base RGB internally and drive a separate ``QVariantAnimation`` that
    updates ``setColor()`` each tick. Blur radius animates via the
    standard ``blurRadius`` property.
    """

    def __init__(self, parent: QWidget, base_color: QColor) -> None:
        super().__init__(parent)
        self.setOffset(0, 0)
        self.setBlurRadius(0.0)
        self._base = QColor(base_color)
        c = QColor(base_color)
        c.setAlpha(0)
        self.setColor(c)

    def set_base_color(self, color: QColor) -> None:
        self._base = QColor(color)
        # Keep the current alpha so a theme switch mid-hover doesn't pop.
        cur = self.color()
        new = QColor(self._base)
        new.setAlpha(cur.alpha())
        self.setColor(new)

    def set_alpha(self, alpha: int) -> None:
        c = QColor(self._base)
        c.setAlpha(max(0, min(255, int(alpha))))
        self.setColor(c)


# ── Button motion (hover glow + press pulse + ripple) ──────────────────────


def attach_button_motion(btn: QWidget) -> None:
    """Equip *btn* with hover glow, press pulse, and click ripple.

    Idempotent — safe to call multiple times. The glow lives on
    ``btn._rhq_glow`` and the active animations on ``btn._rhq_anims``."""
    if btn.property(_INSTRUMENTED):
        return
    btn.setProperty(_INSTRUMENTED, True)

    glow = _GlowEffect(btn, _hover_color_for(btn))
    btn.setGraphicsEffect(glow)
    btn._rhq_glow = glow  # type: ignore[attr-defined]

    blur_anim = QPropertyAnimation(glow, b"blurRadius", btn)
    blur_anim.setDuration(MOTION.HOVER_IN)
    blur_anim.setEasingCurve(MOTION.EASE_IN)

    alpha_anim = QVariantAnimation(btn)
    alpha_anim.setDuration(MOTION.HOVER_IN)
    alpha_anim.setEasingCurve(MOTION.EASE_IN)
    alpha_anim.valueChanged.connect(lambda v: glow.set_alpha(int(v)))

    btn._rhq_anims = (blur_anim, alpha_anim)  # type: ignore[attr-defined]

    # Re-theme on theme switch so the glow follows the active palette.
    ThemeManager.instance().theme_changed.connect(
        lambda _t: glow.set_base_color(_hover_color_for(btn))
    )

    btn.installEventFilter(_button_filter())


def _press_alpha(widget: QWidget) -> int:
    return MOTION.PRESS_ALPHA if _is_primary(widget) or _is_danger(widget) else 200


def _hover_alpha(widget: QWidget) -> int:
    return MOTION.HOVER_ALPHA_PRIM if _is_primary(widget) else MOTION.HOVER_ALPHA


def _hover_blur(widget: QWidget) -> float:
    return MOTION.HOVER_BLUR_PRIM if _is_primary(widget) else MOTION.HOVER_BLUR


def _hover_in(btn: QWidget) -> None:
    anims = getattr(btn, "_rhq_anims", None)
    if anims is None:
        return
    blur, alpha = anims
    blur.stop()
    alpha.stop()
    blur.setDuration(scaled(MOTION.HOVER_IN))
    blur.setEasingCurve(MOTION.EASE_IN)
    blur.setEndValue(_hover_blur(btn))
    alpha.setDuration(scaled(MOTION.HOVER_IN))
    alpha.setEasingCurve(MOTION.EASE_IN)
    alpha.setStartValue(int(btn._rhq_glow.color().alpha()))  # type: ignore[attr-defined]
    alpha.setEndValue(_hover_alpha(btn))
    blur.start()
    alpha.start()


def _hover_out(btn: QWidget) -> None:
    anims = getattr(btn, "_rhq_anims", None)
    if anims is None:
        return
    blur, alpha = anims
    blur.stop()
    alpha.stop()
    blur.setDuration(scaled(MOTION.HOVER_OUT))
    blur.setEasingCurve(MOTION.EASE_OUT)
    blur.setEndValue(0.0)
    alpha.setDuration(scaled(MOTION.HOVER_OUT))
    alpha.setEasingCurve(MOTION.EASE_OUT)
    alpha.setStartValue(int(btn._rhq_glow.color().alpha()))  # type: ignore[attr-defined]
    alpha.setEndValue(0)
    blur.start()
    alpha.start()


def _press_pulse(btn: QWidget) -> None:
    anims = getattr(btn, "_rhq_anims", None)
    if anims is None:
        return
    _, alpha = anims
    alpha.stop()
    alpha.setDuration(scaled(MOTION.PRESS))
    alpha.setEasingCurve(MOTION.EASE_PRESS)
    alpha.setStartValue(int(btn._rhq_glow.color().alpha()))  # type: ignore[attr-defined]
    alpha.setEndValue(_press_alpha(btn))
    alpha.start()


class _ButtonMotionFilter(QObject):
    """Shared event filter that routes Enter/Leave/Press/Release events
    on instrumented buttons through ``_hover_in/_hover_out/_press_pulse``."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not isinstance(obj, QWidget):
            return False
        try:
            et = event.type()
        except RuntimeError:
            return False

        try:
            if et == QEvent.Type.Enter:
                _hover_in(obj)
            elif et == QEvent.Type.Leave:
                _hover_out(obj)
            elif et == QEvent.Type.MouseButtonPress:
                _press_pulse(obj)
                # Spawn a ripple at the cursor position.
                try:
                    pos = event.position().toPoint()  # type: ignore[attr-defined]
                except (AttributeError, TypeError):
                    pos = obj.rect().center()
                Ripple.spawn(obj, pos)
            elif et == QEvent.Type.MouseButtonRelease:
                # Settle back to hover-level glow if still hovered.
                if obj.underMouse():
                    _hover_in(obj)
                else:
                    _hover_out(obj)
        except RuntimeError:
            # Late event on a dying widget — ignore quietly.
            logger.debug("button event ignored on torn-down widget", exc_info=True)
        return False


_FILTER_SINGLETON: _ButtonMotionFilter | None = None


def _button_filter() -> _ButtonMotionFilter:
    global _FILTER_SINGLETON
    if _FILTER_SINGLETON is None:
        app = QApplication.instance()
        _FILTER_SINGLETON = _ButtonMotionFilter(app)
    return _FILTER_SINGLETON


# ── Ripple overlay ──────────────────────────────────────────────────────────


class Ripple(QWidget):
    """Material-style click ripple. Spawned as a transient child overlay
    and self-deletes when the animation finishes."""

    def __init__(self, parent: QWidget, origin: QPoint) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setGeometry(parent.rect())
        self._origin = origin
        self._radius = 0.0
        self._alpha = 110
        self._max_radius = float(max(parent.width(), parent.height()))
        self._color = QColor(_hover_color_for(parent))
        self._anim_r = QVariantAnimation(self)
        self._anim_r.setStartValue(0.0)
        self._anim_r.setEndValue(self._max_radius)
        self._anim_r.setDuration(MOTION.RIPPLE)
        self._anim_r.setEasingCurve(MOTION.EASE_RIPPLE)
        self._anim_r.valueChanged.connect(self._on_radius)
        self._anim_r.finished.connect(self.close)

        self._anim_a = QVariantAnimation(self)
        self._anim_a.setStartValue(140)
        self._anim_a.setEndValue(0)
        self._anim_a.setDuration(MOTION.RIPPLE)
        self._anim_a.setEasingCurve(QEasingCurve.Type.OutQuad)
        self._anim_a.valueChanged.connect(self._on_alpha)

    @staticmethod
    def spawn(parent: QWidget, origin: QPoint) -> Ripple:
        r = Ripple(parent, origin)
        r.show()
        r._anim_r.start()
        r._anim_a.start()
        return r

    def _on_radius(self, v: float) -> None:
        self._radius = float(v)
        self.update()

    def _on_alpha(self, v: int) -> None:
        self._alpha = int(v)
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._color)
        c.setAlpha(self._alpha)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(c)
        p.drawEllipse(self._origin, self._radius, self._radius)


# ── Focus glow (inputs / combos / spinboxes) ───────────────────────────────


def attach_focus_glow(widget: QWidget) -> None:
    """Add an animated drop-shadow that pulses in on focus and out on
    blur. Idempotent."""
    if widget.property(_INSTRUMENTED):
        return
    widget.setProperty(_INSTRUMENTED, True)

    t = theme()
    glow = _GlowEffect(widget, QColor(t.accent))
    widget.setGraphicsEffect(glow)
    widget._rhq_focus_glow = glow  # type: ignore[attr-defined]

    blur_anim = QPropertyAnimation(glow, b"blurRadius", widget)
    alpha_anim = QVariantAnimation(widget)
    alpha_anim.valueChanged.connect(lambda v: glow.set_alpha(int(v)))

    def on_focus_in(_e) -> None:
        blur_anim.stop()
        alpha_anim.stop()
        blur_anim.setDuration(MOTION.FOCUS_IN)
        blur_anim.setEasingCurve(MOTION.EASE_IN)
        blur_anim.setEndValue(MOTION.FOCUS_BLUR)
        alpha_anim.setDuration(MOTION.FOCUS_IN)
        alpha_anim.setEasingCurve(MOTION.EASE_IN)
        alpha_anim.setStartValue(int(glow.color().alpha()))
        alpha_anim.setEndValue(MOTION.FOCUS_ALPHA)
        blur_anim.start()
        alpha_anim.start()

    def on_focus_out(_e) -> None:
        blur_anim.stop()
        alpha_anim.stop()
        blur_anim.setDuration(MOTION.FOCUS_OUT)
        blur_anim.setEasingCurve(MOTION.EASE_OUT)
        blur_anim.setEndValue(0.0)
        alpha_anim.setDuration(MOTION.FOCUS_OUT)
        alpha_anim.setEasingCurve(MOTION.EASE_OUT)
        alpha_anim.setStartValue(int(glow.color().alpha()))
        alpha_anim.setEndValue(0)
        blur_anim.start()
        alpha_anim.start()

    # Chain into existing focus handlers without breaking them.
    _prev_in = widget.focusInEvent
    _prev_out = widget.focusOutEvent

    def _focus_in(e) -> None:
        _prev_in(e)
        on_focus_in(e)

    def _focus_out(e) -> None:
        _prev_out(e)
        on_focus_out(e)

    widget.focusInEvent = _focus_in  # type: ignore[method-assign]
    widget.focusOutEvent = _focus_out  # type: ignore[method-assign]

    ThemeManager.instance().theme_changed.connect(
        lambda _t: glow.set_base_color(QColor(theme().accent))
    )


# ── Cross-fade for QStackedWidget ──────────────────────────────────────────


def cross_fade(stack: QStackedWidget, new_index: int, duration: int = MOTION.PAGE_FADE) -> None:
    """Animated swap from the current page to *new_index*.

    Pages in this app contain instrumented buttons / inputs that already
    wear their own ``QGraphicsEffect``. Stacking a
    ``QGraphicsOpacityEffect`` on the parent page makes Qt re-enter
    painting on descendants — that crashes the splash. So we use a
    "pixmap shroud" overlay: render the old page to a snapshot label,
    swap the stack instantly, then animate the snapshot out.

    The shroud also slides horizontally a small distance in the
    direction implied by the index delta (forward = right→left, back =
    left→right). The new page's "entrance slide" rides through the
    same translation in the opposite direction so the navigation feels
    spatial without becoming a hard cut.
    """
    if new_index == stack.currentIndex():
        return

    direction = 1 if new_index > stack.currentIndex() else -1
    slide_px = 14
    old = stack.currentWidget()
    snapshot = None

    if old is not None and old.size().width() > 0 and old.size().height() > 0:
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

        pm = QPixmap(old.size())
        pm.fill(Qt.GlobalColor.transparent)
        old.render(pm)

        snapshot = QLabel(stack)
        snapshot.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        snapshot.setPixmap(pm)
        snapshot.setGeometry(0, 0, old.size().width(), old.size().height())
        snapshot.raise_()
        snapshot.show()

        # Fade out the snapshot.
        eff = QGraphicsOpacityEffect(snapshot)
        eff.setOpacity(1.0)
        snapshot.setGraphicsEffect(eff)
        fade = QPropertyAnimation(eff, b"opacity", snapshot)
        fade.setDuration(scaled(duration))
        fade.setStartValue(1.0)
        fade.setEndValue(0.0)
        fade.setEasingCurve(MOTION.EASE_PAGE)
        fade.finished.connect(snapshot.deleteLater)
        fade.start()

        # Slide the snapshot away in the navigation direction.
        slide = QPropertyAnimation(snapshot, b"pos", snapshot)
        slide.setDuration(scaled(duration))
        slide.setStartValue(snapshot.pos())
        slide.setEndValue(QPoint(snapshot.pos().x() - direction * slide_px, snapshot.pos().y()))
        slide.setEasingCurve(MOTION.EASE_PAGE)
        slide.start()

        snapshot._rhq_anims = (fade, slide)  # type: ignore[attr-defined]

    # Swap to the new page + give it the opposite-direction entrance slide.
    stack.setCurrentIndex(new_index)
    new = stack.currentWidget()
    if new is not None and not is_reduced():
        from PySide6.QtCore import QPoint

        # Cache the final position once we know the layout has placed
        # the page; then offset by +/- slide_px in the page's local
        # coords. The container is a QStackedWidget so each child
        # widget's pos is (0, 0) — we shift it temporarily and animate
        # back to (0, 0).
        new_anim = QPropertyAnimation(new, b"pos", new)
        new_anim.setStartValue(QPoint(direction * slide_px, 0))
        new_anim.setEndValue(QPoint(0, 0))
        new_anim.setDuration(scaled(duration))
        new_anim.setEasingCurve(MOTION.EASE_PAGE)
        new.move(direction * slide_px, 0)
        new_anim.start()
        new._rhq_entrance_slide = new_anim  # type: ignore[attr-defined]


def fade_in(widget: QWidget, duration: int = MOTION.INTRO) -> None:
    """Briefly fade *widget* from transparent to fully opaque.

    Top-level windows fade via ``setWindowOpacity`` (window-manager level)
    so we don't stack a QGraphicsOpacityEffect on top of inner widgets
    that have their own effects (drop-shadows on buttons / inputs).
    Stacking effects is unsupported by Qt and segfaults under the splash.

    For child widgets we still use ``QGraphicsOpacityEffect`` — but only
    when the widget has no existing effect. If it already has one we
    skip the fade rather than risk crashing.
    """
    if widget.isWindow():
        widget.setWindowOpacity(0.0)
        anim = QPropertyAnimation(widget, b"windowOpacity", widget)
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(MOTION.EASE_PAGE)
        anim.start()
        widget._rhq_fade_in = anim  # type: ignore[attr-defined]
        return

    if widget.graphicsEffect() is not None:
        # Widget already wears an effect — skipping the fade is safer than
        # nesting effects and crashing the painter.
        logger.debug("fade_in skipped on %r: graphicsEffect already set", widget)
        return

    from PySide6.QtWidgets import QGraphicsOpacityEffect

    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity", widget)
    anim.setDuration(duration)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(MOTION.EASE_PAGE)

    def _cleanup() -> None:
        try:
            widget.setGraphicsEffect(None)
        except RuntimeError:
            logger.debug("fade_in cleanup: widget already destroyed", exc_info=True)

    anim.finished.connect(_cleanup)
    anim.start()
    widget._rhq_fade_in = anim  # type: ignore[attr-defined]


# ── One-shot text-colour pulse ─────────────────────────────────────────────


def pulse_color(label, color: QColor, duration: int = 600) -> None:
    """Flash *label* to *color* and ease back to the theme text colour."""
    base_text = theme().text

    def _set_css(c: QColor) -> None:
        try:
            label.setStyleSheet(
                f"color: rgba({c.red()},{c.green()},{c.blue()},{c.alpha()});"
                "background: transparent;"
            )
        except RuntimeError:
            logger.debug("pulse_color: label destroyed mid-animation", exc_info=True)

    anim = QVariantAnimation(label)
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
    start = QColor(color)
    end = QColor(base_text)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)

    def _step(t: float) -> None:
        r = int(start.red() + (end.red() - start.red()) * t)
        g = int(start.green() + (end.green() - start.green()) * t)
        b = int(start.blue() + (end.blue() - start.blue()) * t)
        _set_css(QColor(r, g, b, 255))

    anim.valueChanged.connect(lambda v: _step(float(v)))
    anim.start()
    label._rhq_pulse = anim  # type: ignore[attr-defined]


# ── Breathing logo glow ────────────────────────────────────────────────────


class PulseGlow(QObject):
    """Drive a slow, looping brightness oscillation on a target widget's
    drop-shadow. Used to give the brand wordmark a calm, breathing presence
    without any per-frame Python work in widgets.

    Usage::

        glow = PulseGlow(label, color=QColor(theme().accent))
        glow.start()
    """

    def __init__(
        self,
        target: QWidget,
        color: QColor,
        min_alpha: int = 30,
        max_alpha: int = 180,
        blur: float = 32.0,
        duration: int = MOTION.PULSE,
    ) -> None:
        super().__init__(target)
        self._glow = _GlowEffect(target, color)
        self._glow.setBlurRadius(blur)
        target.setGraphicsEffect(self._glow)

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(min_alpha)
        self._anim.setEndValue(max_alpha)
        self._anim.setDuration(duration // 2)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.valueChanged.connect(lambda v: self._glow.set_alpha(int(v)))
        self._anim.finished.connect(self._reverse)
        self._forward = True

        ThemeManager.instance().theme_changed.connect(self._retheme)

    def _retheme(self, _t) -> None:
        self._glow.set_base_color(QColor(theme().accent))

    def _reverse(self) -> None:
        self._forward = not self._forward
        s, e = self._anim.startValue(), self._anim.endValue()
        self._anim.setStartValue(e)
        self._anim.setEndValue(s)
        self._anim.start()

    def start(self) -> None:
        self._anim.start()

    def stop(self) -> None:
        self._anim.stop()


# ── Card hover-lift glow ───────────────────────────────────────────────────


def attach_card_hover(card: QWidget) -> None:
    """Add an animated drop-shadow that lifts the card on hover.

    Different from button motion: the shadow always carries a small ambient
    offset to give cards a settled "resting" elevation, then deepens + widens
    on hover. Idempotent — safe to call repeatedly.
    """
    if card.property(_INSTRUMENTED + "_card"):
        return
    card.setProperty(_INSTRUMENTED + "_card", True)

    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    shadow = QGraphicsDropShadowEffect(card)
    shadow.setBlurRadius(14.0)
    shadow.setOffset(0, 4)
    base = QColor(0, 0, 0, 120)
    shadow.setColor(base)
    card.setGraphicsEffect(shadow)

    blur_anim = QPropertyAnimation(shadow, b"blurRadius", card)
    blur_anim.setDuration(MOTION.HOVER_IN)
    blur_anim.setEasingCurve(MOTION.EASE_IN)

    card._rhq_card_shadow = shadow  # type: ignore[attr-defined]
    card._rhq_card_blur_anim = blur_anim  # type: ignore[attr-defined]
    card.installEventFilter(_card_filter())


class _CardHoverFilter(QObject):
    """Routes Enter/Leave events on instrumented cards into blur ramps."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not isinstance(obj, QWidget):
            return False
        anim = getattr(obj, "_rhq_card_blur_anim", None)
        if anim is None:
            return False
        try:
            et = event.type()
            if et == QEvent.Type.Enter:
                anim.stop()
                anim.setDuration(MOTION.HOVER_IN)
                anim.setEasingCurve(MOTION.EASE_IN)
                anim.setEndValue(34.0)
                anim.start()
            elif et == QEvent.Type.Leave:
                anim.stop()
                anim.setDuration(MOTION.HOVER_OUT)
                anim.setEasingCurve(MOTION.EASE_OUT)
                anim.setEndValue(14.0)
                anim.start()
        except RuntimeError:
            logger.debug("card event on dying widget", exc_info=True)
        return False


_CARD_FILTER_SINGLETON: _CardHoverFilter | None = None


def _card_filter() -> _CardHoverFilter:
    global _CARD_FILTER_SINGLETON
    if _CARD_FILTER_SINGLETON is None:
        app = QApplication.instance()
        _CARD_FILTER_SINGLETON = _CardHoverFilter(app)
    return _CARD_FILTER_SINGLETON


# ── Staggered slide-in entrance ────────────────────────────────────────────


def stagger_in(
    widgets: list[QWidget], *, step_ms: int = 60, distance_px: int = 18, duration: int = 320
) -> None:
    """Animate *widgets* into place one after another.

    Each widget starts shifted down by ``distance_px`` and at zero
    opacity, then slides up to its final position. The stagger lets the
    dashboard read like it's settling into place rather than appearing
    all at once.

    Implementation note — we animate ``pos`` (window-relative) instead of
    geometry to avoid fighting the layout. Opacity goes through a fresh
    ``QGraphicsOpacityEffect`` and we only attach it if the widget has
    no existing graphics effect (otherwise we skip to preserve hover
    glow already attached by ``attach_card_hover``).
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    for i, w in enumerate(widgets):
        if w is None:
            continue
        final_pos = w.pos()
        start_pos = QPoint(final_pos.x(), final_pos.y() + distance_px)
        w.move(start_pos)

        # Position animation — always safe.
        pos_anim = QPropertyAnimation(w, b"pos", w)
        pos_anim.setDuration(duration)
        pos_anim.setEasingCurve(MOTION.EASE_PAGE)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(final_pos)

        # Opacity — only if no other effect is in play (cards have the
        # hover-shadow effect; we'd be stacking otherwise).
        if w.graphicsEffect() is None:
            eff = QGraphicsOpacityEffect(w)
            eff.setOpacity(0.0)
            w.setGraphicsEffect(eff)
            op_anim = QPropertyAnimation(eff, b"opacity", w)
            op_anim.setDuration(duration)
            op_anim.setEasingCurve(MOTION.EASE_PAGE)
            op_anim.setStartValue(0.0)
            op_anim.setEndValue(1.0)
            op_anim.finished.connect(lambda _w=w: _w.setGraphicsEffect(None))

            def _start_both(_p=pos_anim, _o=op_anim) -> None:
                _p.start()
                _o.start()

            QTimer.singleShot(i * step_ms, _start_both)
            w._rhq_stagger = (pos_anim, op_anim)  # type: ignore[attr-defined]
        else:
            QTimer.singleShot(i * step_ms, pos_anim.start)
            w._rhq_stagger = (pos_anim,)  # type: ignore[attr-defined]


# ── Animated integer count-up ──────────────────────────────────────────────


def count_up(
    label, end_value: int, *, duration: int = 700, prefix: str = "", suffix: str = ""
) -> None:
    """Tween the ``setText`` of *label* from 0 → ``end_value``.

    Used for the dashboard stat cards so big numbers animate in instead
    of snapping. Easing decelerates so the final digits "settle"."""
    anim = QVariantAnimation(label)
    anim.setStartValue(0)
    anim.setEndValue(int(end_value))
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _step(v) -> None:
        try:
            label.setText(f"{prefix}{int(v)}{suffix}")
        except RuntimeError:
            logger.debug("count_up: label destroyed mid-animation", exc_info=True)

    anim.valueChanged.connect(_step)
    anim.start()
    label._rhq_countup = anim  # type: ignore[attr-defined]


def count_up_float(
    label, end_value: float, *, duration: int = 700, fmt: str = "{:.4f}", prefix: str = "$"
) -> None:
    """Float variant of count_up — used for currency / confidence values."""
    anim = QVariantAnimation(label)
    anim.setStartValue(0.0)
    anim.setEndValue(float(end_value))
    anim.setDuration(duration)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _step(v) -> None:
        try:
            label.setText(f"{prefix}{fmt.format(float(v))}")
        except RuntimeError:
            logger.debug("count_up_float: label destroyed mid-animation", exc_info=True)

    anim.valueChanged.connect(_step)
    anim.start()
    label._rhq_countup = anim  # type: ignore[attr-defined]


# ── Page entrance choreography ─────────────────────────────────────────────


def page_entrance(
    page: QWidget,
    *,
    title_widget: QWidget | None = None,
    cards: list[QWidget] | None = None,
    step_ms: int = 60,
) -> None:
    """Wire a "title fades + cards stagger in" reveal for a page.

    Call this from the page's ``showEvent`` (gated behind a once-only
    latch so re-shows don't replay the animation). The title is fade-in
    via the standard ``fade_in`` helper; the cards are passed through
    ``stagger_in`` so each one slides up 18 px while easing to full
    opacity.
    """
    if title_widget is not None:
        # Title is a leaf QLabel — safe to apply an opacity effect
        # without nesting since labels don't have their own effects.
        fade_in(title_widget, duration=DURATION_INTRO)
    if cards:
        stagger_in(cards, step_ms=step_ms)


# Aliased here so callers don't have to import DURATION constants
# explicitly; keeps the entrance helper a single import for pages.
DURATION_INTRO = MOTION.INTRO


# ── Stat-number flash on update ────────────────────────────────────────────


def flash_value_change(label: QWidget, *, duration: int = 480) -> None:
    """Briefly tint *label* with the accent2 colour, then ease back to the
    theme text colour. Used by StatCard.set_value when the value mutates
    so the user sees the change actually happened."""
    if scaled(duration) == 0:
        return
    t = theme()
    start_color = QColor(t.accent2)
    end_color = QColor(t.text)

    anim = QVariantAnimation(label)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setDuration(scaled(duration))
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _step(v) -> None:
        try:
            v = float(v)
            r = int(start_color.red() + (end_color.red() - start_color.red()) * v)
            g = int(start_color.green() + (end_color.green() - start_color.green()) * v)
            b = int(start_color.blue() + (end_color.blue() - start_color.blue()) * v)
            label.setStyleSheet(f"color: rgb({r},{g},{b}); background-color: transparent;")
        except RuntimeError:
            logger.debug("flash_value_change: label destroyed mid-animation", exc_info=True)

    anim.valueChanged.connect(_step)
    anim.finished.connect(lambda: label.setStyleSheet(""))
    anim.start()
    label._rhq_flash = anim  # type: ignore[attr-defined]


# ── Global install ─────────────────────────────────────────────────────────


_INPUT_TYPES = (QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QSpinBox)


def install_global_motion(app: QApplication) -> None:
    """Walk every existing widget once and instrument the standard
    controls; install an event filter on the application so future
    widgets get instrumented as they appear.

    Idempotent and safe to call multiple times (per-widget marker
    property short-circuits double-installs)."""

    # Sweep existing widgets.
    for w in app.allWidgets():
        _maybe_attach(w)

    # Catch later-created widgets via a polish-time event filter.
    app.installEventFilter(_PolishFilter(app))


class _PolishFilter(QObject):
    """Application-wide filter that instruments widgets as they're polished
    by the style. ``Polish`` fires once per widget right before the first
    paint — ideal place to attach effects without affecting initial layout."""

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        try:
            if event.type() == QEvent.Type.Polish and isinstance(obj, QWidget):
                _maybe_attach(obj)
        except RuntimeError:
            logger.debug("PolishFilter: widget destroyed during polish", exc_info=True)
        return False


def _maybe_attach(w: QWidget) -> None:
    if w.property(_INSTRUMENTED):
        return
    if isinstance(w, (QPushButton, QToolButton)):
        attach_button_motion(w)
    elif isinstance(w, _INPUT_TYPES):
        attach_focus_glow(w)
