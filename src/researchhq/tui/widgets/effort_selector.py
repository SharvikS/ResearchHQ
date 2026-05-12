"""Three-chip effort selector — low | medium | high.

Mirrors the --effort CLI flag. Posts EffortChanged on click; keyboard-driven
via left/right arrows when focused.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Static

from researchhq.effort import PROFILES


@dataclass
class EffortChanged(Message):
    value: str


class EffortChip(Static):
    """One pill in the segmented control."""

    def __init__(self, value: str, **kwargs) -> None:
        super().__init__(value.upper(), classes="effort_chip", **kwargs)
        self._value = value
        self.can_focus = True

    def on_click(self) -> None:
        self.post_message(EffortChanged(value=self._value))


class EffortSelector(Horizontal):
    """Segmented control: low / medium / high."""

    def __init__(self, current: str = "medium", **kwargs) -> None:
        super().__init__(**kwargs)
        self._current = current

    def compose(self):
        for level in ("low", "medium", "high"):
            chip = EffortChip(level, id=f"chip_{level}")
            if level == self._current:
                chip.add_class("-active")
            yield chip

    def set_value(self, value: str) -> None:
        if value not in PROFILES:
            return
        self._current = value
        for level in ("low", "medium", "high"):
            try:
                chip = self.query_one(f"#chip_{level}", EffortChip)
            except Exception:
                continue
            if level == value:
                chip.add_class("-active")
            else:
                chip.remove_class("-active")

    def on_effort_changed(self, message: EffortChanged) -> None:
        # Bubble up to the screen, but also update local active styling.
        self.set_value(message.value)
