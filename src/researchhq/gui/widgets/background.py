"""Painted background for the main window — animated.

Two radial halos float in slow orbits behind the workspace. The motion
is extremely subtle (one full revolution per 90 s for the primary halo,
120 s for the secondary one) so it never distracts but the desktop
feels alive when you stop to look.

Implementation notes
--------------------
* A single ``QTimer`` ticks at ~20 Hz and advances two phase floats;
  ``paintEvent`` reads them to compute halo centres. No widget
  layouts are touched per-tick — cheap.
* Each halo is a ``QRadialGradient`` painted into a transparent buffer.
* When ``reduce_motion.is_reduced()`` is on the timer doesn't run and
  the halos sit at their starting positions.
"""

from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QTimer, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from researchhq.gui.reduce_motion import ReduceMotion, is_reduced
from researchhq.gui.theme import ThemeManager, theme


# Period (seconds) for each halo's slow orbit. Big numbers — this is
# ambient drift, not motion the user actively perceives.
_PRIMARY_PERIOD_S   = 90.0
_SECONDARY_PERIOD_S = 120.0
_TICK_INTERVAL_MS   = 50    # 20 fps is plenty for ambient drift

# Count of drifting dust motes painted on top of the radial halos.
# Kept low so the workspace reads quiet — these are barely visible.
_DUST_COUNT = 14


class BackgroundWidget(QWidget):
    """Central widget that paints a deep field + two orbiting halos."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAutoFillBackground(False)
        # Phase accumulators (radians). Driven by a single QTimer so
        # the orbits stay in lockstep regardless of widget resizes.
        self._phase_primary = 0.0
        self._phase_secondary = math.pi  # start opposite for visual variety
        self._tick_seconds = _TICK_INTERVAL_MS / 1000.0

        # Dust motes — laid out on a deterministic seeded grid so the
        # workspace looks "lived in" without dependency on luck. Each
        # mote carries its own velocity and an alpha phase so the
        # field doesn't pulse in unison.
        rng = random.Random(0xDADA)
        self._motes: list[dict] = []
        for _ in range(_DUST_COUNT):
            self._motes.append({
                "x_ratio": rng.random(),
                "y_ratio": rng.random(),
                "vx": rng.uniform(-0.04, 0.04),  # ratio per second
                "vy": rng.uniform(-0.03, 0.03),
                "radius": rng.uniform(0.8, 1.8),
                "phase": rng.uniform(0.0, math.tau),
                "freq":  rng.uniform(0.7, 1.4),
            })
        self._mote_clock = 0.0

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_INTERVAL_MS)
        self._timer.timeout.connect(self._tick)
        if not is_reduced():
            self._timer.start()

        # Toggle the timer if the user flips reduce-motion at runtime.
        ReduceMotion().changed.connect(self._on_reduce_motion_changed)
        ThemeManager.instance().theme_changed.connect(self.update)

    def _on_reduce_motion_changed(self, reduced: bool) -> None:
        if reduced:
            self._timer.stop()
            self.update()
        elif not self._timer.isActive():
            self._timer.start()

    def _tick(self) -> None:
        # Advance phases by (2pi / period) * tick_seconds — a tiny
        # nudge per frame, totalling one full revolution every period.
        self._phase_primary   = (self._phase_primary   + (2 * math.pi / _PRIMARY_PERIOD_S)   * self._tick_seconds) % (2 * math.pi)
        self._phase_secondary = (self._phase_secondary + (2 * math.pi / _SECONDARY_PERIOD_S) * self._tick_seconds) % (2 * math.pi)

        # Drift the dust motes. Velocities are ratios per second — at
        # 20 fps, displacement per tick = vx * 0.05. Wrap around screen
        # edges so motes never run out.
        self._mote_clock = (self._mote_clock + self._tick_seconds) % 1000.0
        for m in self._motes:
            m["x_ratio"] = (m["x_ratio"] + m["vx"] * self._tick_seconds) % 1.0
            m["y_ratio"] = (m["y_ratio"] + m["vy"] * self._tick_seconds) % 1.0

        self.update()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        if w <= 0 or h <= 0:
            return

        # Base fill — solid deep colour so child widgets read crisply.
        p.fillRect(self.rect(), QColor(t.bg_base))

        # ── Primary halo: orbits a small ellipse near the top-left ─────
        # Base centre at (18%, 12%); orbit radius ~6% of the smaller
        # window dimension so the halo doesn't drift far enough to look
        # animated, only enough to feel alive.
        orbit_r = min(w, h) * 0.06
        cx1 = w * 0.18 + orbit_r * math.cos(self._phase_primary)
        cy1 = h * 0.12 + orbit_r * 0.6 * math.sin(self._phase_primary)
        halo_radius = max(w, h) * 0.55
        radial = QRadialGradient(QPointF(cx1, cy1), halo_radius)
        accent_glow = QColor(t.accent)
        accent_glow.setAlpha(60)
        accent_clear = QColor(t.accent)
        accent_clear.setAlpha(0)
        radial.setColorAt(0.0, accent_glow)
        radial.setColorAt(1.0, accent_clear)
        p.fillRect(self.rect(), radial)

        # ── Secondary halo: bottom-right, opposite orbit phase ─────────
        cx2 = w * 0.92 - orbit_r * math.cos(self._phase_secondary)
        cy2 = h * 0.95 - orbit_r * 0.6 * math.sin(self._phase_secondary)
        radial2 = QRadialGradient(QPointF(cx2, cy2), max(w, h) * 0.4)
        a2_glow = QColor(t.accent2)
        a2_glow.setAlpha(40)
        a2_clear = QColor(t.accent2)
        a2_clear.setAlpha(0)
        radial2.setColorAt(0.0, a2_glow)
        radial2.setColorAt(1.0, a2_clear)
        p.fillRect(self.rect(), radial2)

        # Top-edge highlight — almost invisible but adds dimensionality.
        edge = QLinearGradient(0, 0, 0, 2)
        edge_top = QColor(t.text); edge_top.setAlpha(16)
        edge_clear = QColor(t.text); edge_clear.setAlpha(0)
        edge.setColorAt(0.0, edge_top)
        edge.setColorAt(1.0, edge_clear)
        p.fillRect(0, 0, w, 2, edge)

        # ── Dust motes: slow-drifting low-alpha specks. Each mote's
        # alpha breathes with its own sine phase so the field doesn't
        # twinkle in unison. Painted on top of the halos so they read
        # as floating particles in the volume of the workspace.
        p.setPen(Qt.PenStyle.NoPen)
        for m in self._motes:
            mod = (math.sin(self._mote_clock * m["freq"] + m["phase"]) + 1.0) * 0.5
            alpha = int(20 + 60 * mod)
            c = QColor(t.text)
            c.setAlpha(alpha)
            p.setBrush(c)
            x = m["x_ratio"] * w
            y = m["y_ratio"] * h
            r = m["radius"] * (0.6 + 0.4 * mod)
            p.drawEllipse(QPointF(x, y), r, r)
