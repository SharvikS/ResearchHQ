"""Premium startup splash screen.

Full-screen animated wordmark reveal + tagline. Auto-dismisses after
the animation completes. User can skip early with Escape / Enter / Space.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Static
from textual.containers import Center, Middle

from researchhq.tui.theme import DEFAULT_THEME, get_palette
from researchhq.tui.widgets.logo import AnimatedWordmark


class SplashScreen(Screen):
    """Full-screen animated boot splash."""

    BINDINGS = [
        Binding("escape,enter,space", "action_dismiss_splash", "skip", show=False),
    ]

    def __init__(
        self,
        theme_name: str = DEFAULT_THEME,
        duration: float = 0.65,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._theme_name = theme_name
        self._duration   = duration

    def compose(self) -> ComposeResult:
        p = get_palette(self._theme_name)
        yield Middle(
            Center(
                AnimatedWordmark(
                    theme_name=self._theme_name,
                    duration=self._duration,
                    id="splash_logo",
                ),
            ),
            Center(
                Static(" ", id="splash_spacer"),
            ),
            Center(
                Static(
                    f"[dim]initializing workspace …[/dim]",
                    id="splash_hint",
                ),
            ),
            Center(
                Static(
                    f"[dim]press [bold]Enter[/bold] to skip[/dim]",
                    id="splash_skip",
                ),
            ),
        )

    def on_mount(self) -> None:
        # Auto-dismiss after animation + brief pause
        self.set_timer(self._duration + 0.5, self.action_dismiss_splash)

    def action_dismiss_splash(self) -> None:
        self.dismiss()
