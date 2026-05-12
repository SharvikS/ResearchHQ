"""Live pipeline status widget — chips for each agent stage."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

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
    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(label, parent)
        self.setObjectName("StageChip")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._set_state("idle")

    def _set_state(self, s: str) -> None:
        self.setProperty("state", s)
        self.style().unpolish(self)
        self.style().polish(self)


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
        self._detail.setStyleSheet(
            "color: #8a96a8; padding: 4px 0; background: transparent;"
        )
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
