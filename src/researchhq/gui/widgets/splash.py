"""Animated startup splash window.

Shown for ~1.5s while the main window finishes wiring up its pages. The
splash carries the ResearchHQ wordmark on a frameless rounded surface,
a slow breathing accent glow on the brand, a progress bar that fills in
sync with boot stages, and a status line that reports the current stage.

The splash is *purely cosmetic* — it never blocks the bootstrap. The
caller advances the progress via ``set_progress(percent, status)`` from
the main thread as initialisation milestones complete. When the boot is
done the caller invokes ``finish()`` to fade the window out and emit
``finished``; main.py listens for that and shows the real window.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import (
    QEasingCurve, QPoint, QPointF, QPropertyAnimation, QRect, QTimer, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QGuiApplication, QLinearGradient, QPainter,
)
from PySide6.QtWidgets import (
    QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QProgressBar,
    QVBoxLayout, QWidget,
)

from researchhq.gui.reduce_motion import is_reduced
from researchhq.gui.theme import theme


class _Starfield(QWidget):
    """Twinkling dot field. Sits behind the splash card and gives the
    splash a depth-of-space feel.

    Each star has a fixed position and a slow alpha pulse with a random
    phase so the field looks alive but never distracts. The 28 dots are
    cheap to paint at 20 fps."""

    STAR_COUNT = 28

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        # Lay stars out on a deterministic grid + a small per-cell jitter
        # so they read as random without bunching. We seed a local Random
        # so the layout stays identical across launches.
        rng = random.Random(0xCAFE)
        self._stars: list[tuple[float, float, float, float, float]] = []
        for _ in range(self.STAR_COUNT):
            # (x_ratio, y_ratio, base_radius, phase, frequency)
            self._stars.append((
                rng.random(),
                rng.random(),
                rng.uniform(0.6, 1.6),
                rng.uniform(0.0, math.tau),
                rng.uniform(0.7, 1.4),
            ))
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20 fps — plenty for ambient twinkle
        self._timer.timeout.connect(self._tick)
        if not is_reduced():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        # Single global phase — each star multiplies it by its own frequency.
        self._phase = (self._phase + 0.05) % math.tau
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return
        p.setPen(Qt.PenStyle.NoPen)
        for rx, ry, base_r, phase, freq in self._stars:
            x = rx * w
            y = ry * h
            # Alpha modulates between 30 and 170 on a slow sine.
            mod = (math.sin(self._phase * freq + phase) + 1.0) * 0.5
            alpha = int(30 + 140 * mod)
            color = QColor(t.text)
            color.setAlpha(alpha)
            p.setBrush(color)
            p.drawEllipse(QPointF(x, y), base_r, base_r)


class _AnimatedWordmark(QWidget):
    """Custom-painted wordmark with a left-to-right gradient reveal.

    Letters fade in from left to right by sweeping a translucent mask
    across the painted text. Used during the first ~600 ms of the splash;
    after the reveal completes a slow PulseGlow takes over."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._progress = 0.0   # 0.0 → 1.0 reveal sweep
        self._brand = "RESEARCH"
        self._accent_part = "HQ"
        self.setMinimumHeight(72)
        self.setMinimumWidth(420)

    def set_progress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, value))
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        font = p.font()
        font.setFamilies(["SF Pro Display", "Inter", "Segoe UI"])
        font.setPointSize(40)
        font.setBold(True)
        font.setLetterSpacing(font.SpacingType.AbsoluteSpacing, 4.0)
        p.setFont(font)

        fm = p.fontMetrics()
        brand_w = fm.horizontalAdvance(self._brand)
        accent_w = fm.horizontalAdvance(self._accent_part)
        total_w = brand_w + accent_w + 8
        x = (self.width() - total_w) // 2
        y = self.height() // 2 + fm.ascent() // 2 - 4

        # Brand half — primary text.
        p.setPen(QColor(t.text))
        p.drawText(x, y, self._brand)

        # Accent half — cyan.
        p.setPen(QColor(t.accent))
        p.drawText(x + brand_w + 8, y, self._accent_part)

        # Reveal mask: a vertical band from left to a "progress" cutoff
        # is drawn opaque over the deep background, hiding the letters
        # to the right of the cutoff during the reveal.
        if self._progress < 1.0:
            cutoff = int(self.width() * self._progress)
            mask_rect = QRect(cutoff, 0, self.width() - cutoff, self.height())
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(t.bg_deep))
            p.drawRect(mask_rect)
            # Bright leading edge — gives the reveal a glowing seam.
            grad = QLinearGradient(cutoff - 24, 0, cutoff + 8, 0)
            c0 = QColor(t.accent); c0.setAlpha(0)
            c1 = QColor(t.accent2); c1.setAlpha(140)
            grad.setColorAt(0.0, c0)
            grad.setColorAt(1.0, c1)
            p.setBrush(grad)
            p.drawRect(cutoff - 24, 0, 32, self.height())


class _DotsAnimator(QWidget):
    """Three pulsing dots beside the status line — purely decorative."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(38, 12)
        self._phase = 0
        self._timer = QTimer(self)
        self._timer.setInterval(90)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _tick(self) -> None:
        self._phase = (self._phase + 1) % 24
        self.update()

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for i in range(3):
            # Each dot offsets the phase so they ripple, not blink in unison.
            phase = (self._phase + i * 8) % 24
            # 24-step sine — bright at 12, dim at 0/24.
            scale = 0.5 + 0.5 * (1 - abs(phase - 12) / 12)
            c = QColor(t.accent)
            c.setAlpha(int(80 + 175 * scale))
            radius = 2.0 + 2.0 * scale
            p.setBrush(c)
            cx = 6 + i * 12
            p.drawEllipse(QPoint(cx, 6), radius, radius)


class SplashScreen(QWidget):
    """Borderless rounded-rect splash, ~520×320 px.

    Public API
    ----------
    - ``set_progress(percent, status)``  — advance the bar + message
    - ``finish()``                       — fade out then close + emit
                                             ``finished``
    """

    finished = Signal()

    WIDTH = 560
    HEIGHT = 400

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Frameless, no taskbar entry, on top of the desktop.
        self.setWindowFlags(
            Qt.WindowType.SplashScreen
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(self.WIDTH, self.HEIGHT)
        self._center_on_primary_screen()

        # Root card with rounded corners + drop shadow.
        self._root = QWidget(self)
        self._root.setObjectName("SplashRoot")
        self._root.setGeometry(8, 8, self.WIDTH - 16, self.HEIGHT - 16)
        shadow = QGraphicsDropShadowEffect(self._root)
        shadow.setBlurRadius(36)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(0, 0, 0, 180))
        self._root.setGraphicsEffect(shadow)

        # Starfield: drifting low-alpha dots behind every other widget
        # inside the card. Sits at the same geometry as _root so it
        # exactly fills the visible surface, then we lower it so the
        # other children (kicker / logo / wordmark / progress) sit on top.
        self._stars = _Starfield(self._root)
        self._stars.setGeometry(0, 0, self.WIDTH - 16, self.HEIGHT - 16)
        self._stars.lower()

        # Layout inside the root card.
        outer = QVBoxLayout(self._root)
        outer.setContentsMargins(36, 36, 36, 28)
        outer.setSpacing(10)

        # Kicker line.
        kicker = QLabel("RESEARCHHQ · STUDIO")
        kicker.setObjectName("SplashKicker")
        kicker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(kicker)

        outer.addStretch(1)

        # Animated brand mark — six agent nodes converge to a bright
        # central core. On the splash the mark runs its full assembly
        # animation: nodes fade in staggered → filaments draw inward →
        # core pulses up → settles into idle breathing.
        from researchhq.gui.widgets.logo import LogoMark
        self._logo = LogoMark(size=96, mode="assemble")
        outer.addWidget(self._logo, alignment=Qt.AlignmentFlag.AlignCenter)

        outer.addSpacing(6)

        # Animated wordmark — gradient sweep reveal.
        self._wordmark = _AnimatedWordmark()
        outer.addWidget(self._wordmark, alignment=Qt.AlignmentFlag.AlignCenter)

        # Tagline below the wordmark.
        tagline = QLabel("premium multi-agent research workstation")
        tagline.setObjectName("SplashTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(tagline)

        outer.addStretch(2)

        # Status line — dots animator + label.
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        status_row.addStretch(1)
        self._dots = _DotsAnimator()
        status_row.addWidget(self._dots)
        self._status = QLabel("initializing workspace")
        self._status.setObjectName("SplashStatus")
        status_row.addWidget(self._status)
        status_row.addStretch(1)
        outer.addLayout(status_row)

        # Progress bar.
        self._bar = QProgressBar()
        self._bar.setObjectName("SplashProgress")
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        outer.addWidget(self._bar)

        # Reveal animation: drive the wordmark sweep across the first 600 ms.
        self._reveal = QPropertyAnimation(self, b"_reveal_progress", self)
        self._reveal.setStartValue(0.0)
        self._reveal.setEndValue(1.0)
        self._reveal.setDuration(700)
        self._reveal.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._reveal.valueChanged.connect(
            lambda v: self._wordmark.set_progress(float(v))
        )
        self._reveal.finished.connect(self._on_reveal_done)

        # Fade the whole window via setWindowOpacity (window-manager level).
        # We avoid QGraphicsOpacityEffect here because the inner widgets
        # already use their own QGraphicsEffects (drop shadow on _root,
        # PulseGlow on _wordmark) — nesting effects is not supported by
        # Qt and produces a flood of "painter not active" warnings.
        self.setWindowOpacity(0.0)

        self._fade_in = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in.setStartValue(0.0)
        self._fade_in.setEndValue(1.0)
        self._fade_in.setDuration(240)
        self._fade_in.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._fade_out = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out.setStartValue(1.0)
        self._fade_out.setEndValue(0.0)
        self._fade_out.setDuration(260)
        self._fade_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self._fade_out.finished.connect(self._on_faded_out)

    # ─── public API ─────────────────────────────────────────────────────────

    def show_animated(self) -> None:
        """Show the splash and kick off the reveal animation."""
        self.show()
        self.raise_()
        self._fade_in.start()
        self._reveal.start()

    def set_progress(self, percent: int, status: str | None = None) -> None:
        prev = self._bar.value()
        new = max(0, min(100, int(percent)))
        self._bar.setValue(new)
        if status is not None:
            self._status.setText(status)
        # Fire a celebratory particle burst on the transition into the
        # final "ready" state — happens exactly once even if callers
        # set 100 repeatedly.
        if new >= 100 and prev < 100 and not getattr(self, "_burst_fired", False):
            self._burst_fired = True
            self._fire_ready_burst()

    def _fire_ready_burst(self) -> None:
        """Spawn a particle burst centred on the logo."""
        try:
            from PySide6.QtCore import QPointF
            from researchhq.gui.widgets.particle_burst import ParticleBurst
            # Compute the logo centre in _root-local coordinates.
            logo_geo = self._logo.geometry()
            origin = QPointF(
                logo_geo.x() + logo_geo.width() / 2,
                logo_geo.y() + logo_geo.height() / 2,
            )
            ParticleBurst.fire_at(self._root, origin)
        except (ImportError, RuntimeError):
            # Burst is pure spectacle — never let a paint failure
            # interfere with the boot handoff.
            pass

    def finish(self) -> None:
        """Fade the splash out, then close + emit ``finished``."""
        self._dots.stop()
        # Stop the logo and starfield timers so they don't tick into
        # destroyed widgets after the fade-out completes.
        try:
            self._logo.stop()
        except (AttributeError, RuntimeError):
            pass
        try:
            self._stars.stop()
        except (AttributeError, RuntimeError):
            pass
        self._fade_out.start()

    # ─── internals ──────────────────────────────────────────────────────────

    def _center_on_primary_screen(self) -> None:
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = screen.availableGeometry()
        x = geo.x() + (geo.width() - self.WIDTH) // 2
        y = geo.y() + (geo.height() - self.HEIGHT) // 2
        self.move(x, y)

    def _on_reveal_done(self) -> None:
        # Reveal animation finished — just pin the wordmark to fully visible.
        # We don't attach a QGraphicsEffect to the wordmark because the
        # widget already has a custom paintEvent; combining the two causes
        # Qt to re-enter its painter during effect rendering and segfault.
        self._wordmark.set_progress(1.0)

    def _on_faded_out(self) -> None:
        self.finished.emit()
        self.close()

    # Reveal progress property — driven by the QPropertyAnimation.
    def _get_reveal_progress(self) -> float:
        return self._wordmark._progress

    def _set_reveal_progress(self, v: float) -> None:
        self._wordmark.set_progress(v)

    from PySide6.QtCore import Property
    _reveal_progress = Property(float, _get_reveal_progress, _set_reveal_progress)
