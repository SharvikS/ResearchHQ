"""Live pipeline status widget — animated chips for each agent stage.

Each ``StageChip`` is a small pill-shaped label that carries one of
four states (idle / running / done / failed). The base appearance
comes from the global QSS template (#StageChip with state="…"); the
``running`` state adds a continuously animated accent halo painted on
top of the QSS so the active chip reads as alive.

Animations route through ``QPropertyAnimation`` on ``pulsePhase`` so
reduce-motion can collapse them and stop the timers.
"""

from __future__ import annotations

import math

from PySide6.QtCore import (
    QEasingCurve, QPropertyAnimation, QRectF, Qt, Property,
)
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from researchhq.gui.reduce_motion import is_reduced
from researchhq.gui.theme import ThemeManager, theme

STAGES = [
    ("planner",       "Planner"),
    ("searcher",      "Searcher"),
    ("source_ranker", "Ranker"),
    ("fetcher",       "Fetcher"),
    ("extractor",     "Extractor"),
    ("synthesizer",   "Synthesizer"),
    ("verifier",      "Verifier"),
    ("formatter",     "Formatter"),
]


class StageChip(QLabel):
    """Pill chip with a pulsing accent halo when state == 'running'."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("StageChip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pulse_phase = 0.0
        self._pulse_anim: QPropertyAnimation | None = None
        ThemeManager.instance().theme_changed.connect(self.update)
        self._set_state("idle")

    # ── Qt property ────────────────────────────────────────────────────────

    def _get_pulse(self) -> float: return self._pulse_phase
    def _set_pulse(self, v: float) -> None:
        self._pulse_phase = float(v); self.update()
    pulsePhase = Property(float, _get_pulse, _set_pulse)

    # ── state ──────────────────────────────────────────────────────────────

    def _set_state(self, s: str) -> None:
        self.setProperty("state", s)
        self.style().unpolish(self)
        self.style().polish(self)
        # Start / stop the running-state pulse animation.
        if s == "running" and not is_reduced():
            self._start_pulse()
        else:
            self._stop_pulse()

    def _start_pulse(self) -> None:
        if self._pulse_anim is not None:
            return
        anim = QPropertyAnimation(self, b"pulsePhase", self)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setDuration(1200)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)

        # Manual ping-pong loop so the halo breathes.
        def _reverse() -> None:
            s, e = anim.startValue(), anim.endValue()
            anim.setStartValue(e); anim.setEndValue(s)
            anim.start()

        anim.finished.connect(_reverse)
        anim.start()
        self._pulse_anim = anim

    def _stop_pulse(self) -> None:
        if self._pulse_anim is not None:
            self._pulse_anim.stop()
            self._pulse_anim = None
        self._pulse_phase = 0.0
        self.update()

    # ── painting ───────────────────────────────────────────────────────────

    def paintEvent(self, ev) -> None:  # noqa: N802 - Qt method
        super().paintEvent(ev)
        if self.property("state") != "running":
            return
        # Composite a pulsing accent halo on top of the QSS-rendered chip.
        t = theme()
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        # Pulse from 60→200 alpha and back.
        alpha = int(60 + 140 * (math.sin(self._pulse_phase * math.pi) * 0.5 + 0.5))
        glow = QColor(t.accent); glow.setAlpha(alpha)
        pen = QPen(glow)
        pen.setWidthF(1.5)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        # Stay just inside the chip's outer rect so the painted stroke
        # doesn't get cropped by the pill's rounded corners.
        rect = QRectF(0.75, 0.75, w - 1.5, h - 1.5)
        # QSS uses border-radius: 999px for #StageChip — treat the chip
        # as a fully-rounded pill.
        p.drawRoundedRect(rect, h / 2, h / 2)


class PipelineStatus(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)
        self._chips: dict[str, StageChip] = {}
        for key, label in STAGES:
            chip = StageChip(label)
            row.addWidget(chip)
            self._chips[key] = chip
        row.addStretch(1)
        outer.addLayout(row)

        self._detail = QLabel("Ready.")
        self._detail.setObjectName("Muted")
        outer.addWidget(self._detail)

    def reset(self) -> None:
        for c in self._chips.values():
            c._set_state("idle")
        self._detail.setText("Ready.")

    def on_stage(self, stage: str, detail: str) -> None:
        if stage not in self._chips:
            return
        # Mark prior stages done.
        order = [k for k, _ in STAGES]
        idx = order.index(stage)
        for i, k in enumerate(order):
            chip = self._chips[k]
            if i < idx:
                chip._set_state("done")
            elif i == idx:
                chip._set_state("running")
            else:
                chip._set_state("idle")
        self._detail.setText(f"{stage}: {detail}")

    def mark_done(self) -> None:
        for c in self._chips.values():
            c._set_state("done")
        self._detail.setText("Pipeline complete.")

    def mark_failed(self, msg: str) -> None:
        # Whichever chip was running becomes failed; idle chips stay idle.
        for c in self._chips.values():
            if c.property("state") == "running":
                c._set_state("failed")
        self._detail.setText(f"Failed: {msg}")

    def mark_canceled(self) -> None:
        for c in self._chips.values():
            if c.property("state") == "running":
                c._set_state("idle")
        self._detail.setText("Canceled.")
