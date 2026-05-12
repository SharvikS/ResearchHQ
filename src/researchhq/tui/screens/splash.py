"""Animated startup splash. Auto-dismisses to dashboard after the wordmark
has finished revealing."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Center, Middle
from textual.screen import Screen
from textual.widgets import Static

from researchhq.tui.widgets.logo import AnimatedWordmark


class SplashScreen(Screen):
    """Boot screen — wordmark + tagline. ~0.7s."""

    BINDINGS = [("escape,enter,space", "dismiss_splash", "skip")]

    def __init__(self, theme_name: str = "default", duration: float = 0.7, **kwargs) -> None:
        super().__init__(**kwargs)
        self._theme_name = theme_name
        self._duration = duration

    def compose(self) -> ComposeResult:
        with Middle():
            with Center():
                yield AnimatedWordmark(self._theme_name, duration=self._duration)
            with Center():
                yield Static(" ")  # spacer
            with Center():
                yield Static("[dim]initializing workspace…[/dim]")

    def on_mount(self) -> None:
        # Dismiss slightly after the wordmark animation finishes; this reveals
        # the persistent shell + dashboard underneath.
        self.set_timer(self._duration + 0.4, self._dismiss)

    def action_dismiss_splash(self) -> None:
        self._dismiss()

    def _dismiss(self) -> None:
        try:
            self.app.pop_screen()
        except Exception:
            pass
