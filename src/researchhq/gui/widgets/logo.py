"""ResearchHQ brand mark — convergence / aperture motif.

Concept
-------
Six outer "agent" nodes arranged on a regular hexagon. Each node sends a
thin filament inward toward a bright central node. The filaments stop
just short of the centre, leaving a small negative-space gap so the
core reads as a separate, brighter focal point. A thin outer ring
frames the whole composition. The result is an aperture / converging
constellation — multiple agents collapsing to a single synthesized
insight.

Three modes
-----------
- ``mode="assemble"`` — for the splash. Outer nodes fade in staggered,
  filaments draw inward sequentially, then the core pulses once. After
  the assembly the mark settles into the idle loop.
- ``mode="idle"`` — for the sidebar. Outer nodes static, filaments
  static, core pulses gently forever. No rotation (less distraction in
  the chrome).
- ``mode="static"`` — single frame at full assembly. Used by
  ``logo_icon()`` to mint a flat QIcon for the dock / window.

All animations run through ``QPropertyAnimation`` on float properties
so reduce-motion can collapse them via ``scaled()``.
"""

from __future__ import annotations

import math
from typing import Literal

from PySide6.QtCore import (
    QEasingCurve, QPointF, QPropertyAnimation, QRectF, QSequentialAnimationGroup,
    QTimer, Qt, Property,
)
from PySide6.QtGui import (
    QBrush, QColor, QIcon, QPainter, QPen, QPixmap, QRadialGradient,
)
from PySide6.QtWidgets import QWidget

from researchhq.gui.reduce_motion import scaled
from researchhq.gui.theme import ThemeManager, theme

LogoMode = Literal["assemble", "idle", "static"]

# Number of agent nodes — 6 reads as "many" without becoming visual noise.
_AGENT_COUNT = 6

# Stroke widths scale with widget size; min/max keep the mark legible at
# both favicon (16 px) and splash (128 px) resolutions.
_RING_W_RATIO   = 0.022
_FILAMENT_RATIO = 0.030


class LogoMark(QWidget):
    """The ResearchHQ brand mark."""

    def __init__(
        self,
        size: int = 64,
        mode: LogoMode = "idle",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._size = int(size)
        self.setFixedSize(self._size, self._size)
        self._mode: LogoMode = mode

        # Animated properties (0.0–1.0). Each drives a portion of the
        # rendered geometry and is wired through a real QPropertyAnimation
        # so reduce-motion + global timing tweaks work uniformly.
        self._nodes_progress = 1.0 if mode != "assemble" else 0.0
        self._filaments_progress = 1.0 if mode != "assemble" else 0.0
        self._core_scale = 1.0 if mode != "assemble" else 0.0
        self._core_pulse = 0.6  # idle alpha modulation for the centre dot
        # Extra rotation applied to all outer agent nodes — used by the
        # hover-trail animation. Defaults to 0; nudges to +60° (one
        # full hex step) on enterEvent and eases back on leaveEvent.
        self._rotation_offset = 0.0

        # Idle pulse — runs forever in "idle" + after assembly in "assemble"
        # mode. Cheap (alpha-only on one element).
        self._pulse_anim: QPropertyAnimation | None = None
        self._assemble_group: QSequentialAnimationGroup | None = None
        self._rotation_anim: QPropertyAnimation | None = None

        ThemeManager.instance().theme_changed.connect(self._on_theme)

        if mode == "assemble":
            # Defer a tick so the widget has its first geometry pass.
            QTimer.singleShot(0, self._start_assembly)
        elif mode == "idle":
            QTimer.singleShot(0, self._start_idle_pulse)

    # ── theme ──────────────────────────────────────────────────────────────

    def _on_theme(self, _t) -> None:
        self.update()

    # ── property accessors (Qt animations require Property + signal) ───────

    def _get_nodes_progress(self) -> float: return self._nodes_progress
    def _set_nodes_progress(self, v: float) -> None:
        self._nodes_progress = float(v); self.update()
    nodesProgress = Property(float, _get_nodes_progress, _set_nodes_progress)

    def _get_filaments_progress(self) -> float: return self._filaments_progress
    def _set_filaments_progress(self, v: float) -> None:
        self._filaments_progress = float(v); self.update()
    filamentsProgress = Property(float, _get_filaments_progress, _set_filaments_progress)

    def _get_core_scale(self) -> float: return self._core_scale
    def _set_core_scale(self, v: float) -> None:
        self._core_scale = float(v); self.update()
    coreScale = Property(float, _get_core_scale, _set_core_scale)

    def _get_core_pulse(self) -> float: return self._core_pulse
    def _set_core_pulse(self, v: float) -> None:
        self._core_pulse = float(v); self.update()
    corePulse = Property(float, _get_core_pulse, _set_core_pulse)

    def _get_rotation_offset(self) -> float: return self._rotation_offset
    def _set_rotation_offset(self, v: float) -> None:
        self._rotation_offset = float(v); self.update()
    rotationOffset = Property(float, _get_rotation_offset, _set_rotation_offset)

    # ── hover trail (outer nodes rotate one hex step on hover) ─────────────

    def enterEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().enterEvent(event)
        self._start_rotation(target_degrees=60.0, duration_ms=320)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt method
        super().leaveEvent(event)
        self._start_rotation(target_degrees=0.0, duration_ms=380)

    def _start_rotation(self, *, target_degrees: float, duration_ms: int) -> None:
        if self._rotation_anim is not None:
            self._rotation_anim.stop()
        anim = QPropertyAnimation(self, b"rotationOffset", self)
        anim.setStartValue(self._rotation_offset)
        anim.setEndValue(target_degrees)
        anim.setDuration(scaled(duration_ms))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()
        self._rotation_anim = anim

    # ── assembly animation ────────────────────────────────────────────────

    def _start_assembly(self) -> None:
        """Three-phase reveal: nodes → filaments → core pulse → idle."""
        group = QSequentialAnimationGroup(self)

        # Phase 1: outer nodes fade-in (driven by a single progress var
        # that paintEvent uses to gate per-node alpha + scale via the
        # node index).
        nodes_anim = QPropertyAnimation(self, b"nodesProgress", self)
        nodes_anim.setStartValue(0.0)
        nodes_anim.setEndValue(1.0)
        nodes_anim.setDuration(scaled(420))
        nodes_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(nodes_anim)

        # Phase 2: filaments draw inward toward the core.
        filaments_anim = QPropertyAnimation(self, b"filamentsProgress", self)
        filaments_anim.setStartValue(0.0)
        filaments_anim.setEndValue(1.0)
        filaments_anim.setDuration(scaled(360))
        filaments_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        group.addAnimation(filaments_anim)

        # Phase 3: core pulses up with a small OutBack overshoot.
        core_in = QPropertyAnimation(self, b"coreScale", self)
        core_in.setStartValue(0.0)
        core_in.setEndValue(1.0)
        core_in.setDuration(scaled(280))
        core_in.setEasingCurve(QEasingCurve.Type.OutBack)
        group.addAnimation(core_in)

        group.finished.connect(self._start_idle_pulse)
        group.start()
        self._assemble_group = group

    def _start_idle_pulse(self) -> None:
        """Settle into the perpetual idle state — gentle core breathing."""
        anim = QPropertyAnimation(self, b"corePulse", self)
        anim.setStartValue(0.55)
        anim.setEndValue(1.0)
        anim.setDuration(scaled(1200))
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        # Manual loop — reverse on finish so the pulse breathes.
        def _reverse() -> None:
            s, e = anim.startValue(), anim.endValue()
            anim.setStartValue(e); anim.setEndValue(s)
            if scaled(1) > 0:  # only loop when motion is enabled
                anim.start()

        anim.finished.connect(_reverse)
        if scaled(1) > 0:
            anim.start()
        self._pulse_anim = anim

    # ── public API ─────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Halt any running animation. Call before destruction so child
        QPropertyAnimation timers don't tick into a freed widget."""
        if self._assemble_group is not None:
            self._assemble_group.stop()
        if self._pulse_anim is not None:
            self._pulse_anim.stop()

    def to_pixmap(self) -> QPixmap:
        """Rasterise the current frame to a transparent pixmap."""
        pm = QPixmap(self._size, self._size)
        pm.fill(Qt.GlobalColor.transparent)
        self.render(pm)
        return pm

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, _ev) -> None:  # noqa: N802 - Qt method
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        s = float(self._size)
        cx, cy = s / 2, s / 2
        outer_r = s * 0.42         # agent-node orbital radius
        ring_r  = s * 0.48         # framing ring radius
        node_r  = max(1.5, s * 0.05)
        core_r  = max(2.5, s * 0.085)
        # Where the filaments terminate — short of the core so the
        # negative-space aperture reads as deliberate.
        filament_inner = core_r + s * 0.04
        filament_outer = outer_r - node_r * 0.6

        ring_w     = max(1.0, s * _RING_W_RATIO)
        filament_w = max(1.0, s * _FILAMENT_RATIO * 0.55)

        accent  = QColor(t.accent)
        accent2 = QColor(t.accent2)
        text_c  = QColor(t.text)

        # ── outer framing ring (a thin 320° arc — leaves a small gap so
        # the form reads as an aperture, not a closed circle) ─────────────
        ring_pen = QPen(QColor(t.border_lt))
        ring_pen.setWidthF(ring_w)
        ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(ring_pen)
        ring_rect = QRectF(cx - ring_r, cy - ring_r, 2 * ring_r, 2 * ring_r)
        # Start at 110° CCW from 3 o'clock, sweep 320°.
        p.drawArc(ring_rect, int(110 * 16), int(320 * 16))

        # ── outer agent nodes + their inward filaments ────────────────────
        # Each node has an individual reveal threshold based on its index.
        # nodesProgress 0.0–1.0 maps across the 6 nodes — node i becomes
        # visible once progress crosses i/(N+1). Adding 1 to the denom
        # gives the *last* node a brief visible flourish before phase 1
        # completes (it never reaches 100% mid-phase).
        n = _AGENT_COUNT
        # Hover-trail rotation offset is in degrees — convert to radians
        # and add to every node's angle so the whole ring drifts.
        rot_rad = math.radians(self._rotation_offset)
        for i in range(n):
            angle = -math.pi / 2 + (2 * math.pi * i / n) + rot_rad  # start at top, CW
            nx = cx + outer_r * math.cos(angle)
            ny = cy + outer_r * math.sin(angle)

            # Per-node reveal threshold.
            threshold = i / (n + 1)
            local_progress = max(0.0, min(1.0,
                (self._nodes_progress - threshold) / max(0.001, 1.0 - threshold)
            ))
            if local_progress <= 0.0:
                continue

            # Filament: from outer point → toward centre. Length grows
            # with filamentsProgress; per-node start threshold staggers
            # the draw so they don't all reach the centre simultaneously.
            fil_threshold = i / (n + 1)
            fil_local = max(0.0, min(1.0,
                (self._filaments_progress - fil_threshold)
                / max(0.001, 1.0 - fil_threshold)
            ))
            if fil_local > 0.0:
                # Endpoint along the same radial line.
                start_x = cx + filament_outer * math.cos(angle)
                start_y = cy + filament_outer * math.sin(angle)
                end_x_full = cx + filament_inner * math.cos(angle)
                end_y_full = cy + filament_inner * math.sin(angle)
                end_x = start_x + (end_x_full - start_x) * fil_local
                end_y = start_y + (end_y_full - start_y) * fil_local

                fil_color = QColor(accent)
                fil_color.setAlpha(int(180 * fil_local))
                fil_pen = QPen(fil_color)
                fil_pen.setWidthF(filament_w)
                fil_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(fil_pen)
                p.drawLine(QPointF(start_x, start_y), QPointF(end_x, end_y))

            # Node dot — alpha + scale from local_progress.
            alpha = int(255 * local_progress)
            scale = 0.6 + 0.4 * local_progress  # 0.6 → 1.0
            node_color = QColor(accent if i % 2 == 0 else accent2)
            node_color.setAlpha(alpha)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(node_color))
            p.drawEllipse(QPointF(nx, ny),
                          node_r * scale, node_r * scale)

        # ── core: bright central node with radial-gradient halo ───────────
        scale = max(0.0, min(1.2, self._core_scale))
        if scale > 0.001:
            # Soft halo behind the dot — radial gradient so the centre
            # reads as the brightest point of the composition.
            halo_r = core_r * 2.6 * scale
            halo_grad = QRadialGradient(QPointF(cx, cy), halo_r)
            halo_inner = QColor(accent)
            halo_inner.setAlpha(int(140 * self._core_pulse))
            halo_outer = QColor(accent)
            halo_outer.setAlpha(0)
            halo_grad.setColorAt(0.0, halo_inner)
            halo_grad.setColorAt(1.0, halo_outer)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(halo_grad))
            p.drawEllipse(QPointF(cx, cy), halo_r, halo_r)

            # Core dot — a small filled circle, gradient-tinted.
            core_grad = QRadialGradient(QPointF(cx, cy), core_r * scale)
            core_grad.setColorAt(0.0, text_c)
            core_grad.setColorAt(0.6, accent)
            core_grad.setColorAt(1.0, accent2)
            p.setBrush(QBrush(core_grad))
            p.drawEllipse(QPointF(cx, cy),
                          core_r * scale, core_r * scale)


def logo_icon(size: int = 128) -> QIcon:
    """Static ``QIcon`` rasterised from the brand mark at full assembly.

    Used for the application / dock / window icon. The widget is
    created in ``static`` mode so no timers fire and no animation
    state needs to be ticked forward."""
    mark = LogoMark(size=size, mode="static")
    pm = mark.to_pixmap()
    return QIcon(pm)
