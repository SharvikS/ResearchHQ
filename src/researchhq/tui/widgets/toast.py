"""Lightweight toast notifications.

Textual ≥0.86 has a built-in `notify`, but our toasts are themed via the
custom CSS palette so they're consistent with the rest of the UI.
"""

from __future__ import annotations

from textual.containers import Container
from textual.widgets import Static


class Toast(Container):
    """Auto-dismissing notification."""

    def __init__(self, message: str, kind: str = "info", duration: float = 3.0, **kwargs) -> None:
        super().__init__(classes=f"toast -{kind}", **kwargs)
        self._message = message
        self._duration = duration

    def compose(self):
        yield Static(self._message)

    def on_mount(self) -> None:
        self.set_timer(self._duration, self._dismiss)

    def _dismiss(self) -> None:
        try:
            self.remove()
        except Exception:
            pass
