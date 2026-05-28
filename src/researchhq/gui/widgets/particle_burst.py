"""One-shot particle burst.

Used by the splash when boot completes — a quick cyan/magenta burst
radiates outward from a target point. The burst self-destructs after
its animation finishes. Cheap (16 particles, single QTimer at 60 fps,
no per-particle widgets).

Usage::

    burst = ParticleBurst.fire_at(parent, origin=QPoint(280, 200))

The burst is parented to ``parent`` and positioned to fill it (so it
can paint anywhere within the parent without layout interference). It
captures click-through so it can never block the interface beneath.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget

from researchhq.gui.reduce_motion import is_reduced
from researchhq.gui.theme import theme


# Total lifetime of the burst in milliseconds. After this the widget
# self-destructs. 900 ms is enough for the particles to drift to their
# final radius and fade out without lingering.
_LIFETIME_MS = 900
_TICK_MS = 16    # ~60 fps for the brief burst — particles are simple


class _Particle:
    """Single particle state. Cheap dataclass-ish; mutable for hot loop."""

    __slots__ = ("vx", "vy", "x", "y", "life", "color", "radius")

    def __init__(self, x: float, y: float, vx: float, vy: float,
                 color: QColor, radius: float) -> None:
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.color = color
        self.radius = radius
        self.life = 1.0   # 1.0 → 0.0 as the particle ages out


class ParticleBurst(QWidget):
    """One-shot ring burst that paints itself for ~900 ms then deletes."""

    PARTICLE_COUNT = 18
    SPEED_PX_PER_FRAME = 3.4

    def __init__(self, parent: QWidget, origin: QPointF) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        # Fill the parent so we can paint particles wherever they drift.
        self.setGeometry(0, 0, parent.width(), parent.height())

        self._origin = origin
        self._particles: list[_Particle] = []
        self._build_particles()

        self._elapsed_ms = 0
        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    # ── factory ────────────────────────────────────────────────────────────

    @classmethod
    def fire_at(cls, parent: QWidget, origin: QPointF) -> "ParticleBurst | None":
        """Spawn a burst at *origin* (in *parent*-local coords).

        Returns the widget so callers can keep a ref if they need to
        cancel early; the burst manages its own deletion otherwise.
        Returns ``None`` when reduce-motion is on — bursts are pure
        spectacle so we skip them cleanly."""
        if is_reduced():
            return None
        burst = cls(parent, origin)
        burst.show()
        burst.raise_()
        return burst

    # ── lifecycle ──────────────────────────────────────────────────────────

    def _build_particles(self) -> None:
        t = theme()
        for i in range(self.PARTICLE_COUNT):
            # Even angular distribution + a small jitter so the burst
            # reads as a hand-tossed ring rather than a perfect wheel.
            angle = (math.tau * i / self.PARTICLE_COUNT) + random.uniform(-0.18, 0.18)
            speed = self.SPEED_PX_PER_FRAME * random.uniform(0.7, 1.3)
            vx = math.cos(angle) * speed
            vy = math.sin(angle) * speed
            # Alternate between primary and secondary brand colours.
            color = QColor(t.accent if i % 2 == 0 else t.accent2)
            radius = random.uniform(2.0, 3.6)
            self._particles.append(
                _Particle(self._origin.x(), self._origin.y(), vx, vy, color, radius)
            )

    def _tick(self) -> None:
        self._elapsed_ms += _TICK_MS
        if self._elapsed_ms >= _LIFETIME_MS:
            self._timer.stop()
            self.close()
            return

        # Particle update — advance position, decay life. We model life
        # as a normalised quantity that decays linearly across the
        # widget lifetime so alpha + radius taper smoothly to zero.
        progress = self._elapsed_ms / _LIFETIME_MS
        for pt in self._particles:
            pt.x += pt.vx
            pt.y += pt.vy
            # Gentle deceleration so the ring slows as it expands.
            pt.vx *= 0.96
            pt.vy *= 0.96
            pt.life = 1.0 - progress
        self.update()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        for pt in self._particles:
            if pt.life <= 0.0:
                continue
            c = QColor(pt.color)
            c.setAlpha(int(255 * pt.life))
            p.setBrush(c)
            r = pt.radius * pt.life
            p.drawEllipse(QPointF(pt.x, pt.y), r, r)
