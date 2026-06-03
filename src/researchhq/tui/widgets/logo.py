"""ResearchHQ wordmark widgets.

- AnimatedWordmark  — full ASCII, revealed left-to-right (splash)
- Wordmark          — full ASCII, static
- CompactWordmark   — single-line brand line (narrow layouts)
- ResponsiveWordmark — swaps full ↔ compact based on terminal width
"""

from __future__ import annotations

import math

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

from researchhq.tui.theme import DEFAULT_THEME, get_palette

# ── ASCII artwork ─────────────────────────────────────────────────────
# Carefully proportioned — "RHQ" mark in block letters.
# Splits into RESEARCH (accent) and HQ (accent_2) for dual-color rendering.

RESEARCH_LINES = [
    "██████╗ ███████╗███████╗███████╗ █████╗ ██████╗  ██████╗██╗  ██╗",
    "██╔══██╗██╔════╝██╔════╝██╔════╝██╔══██╗██╔══██╗██╔════╝██║  ██║",
    "██████╔╝█████╗  ███████╗█████╗  ███████║██████╔╝██║     ███████║",
    "██╔══██╗██╔══╝  ╚════██║██╔══╝  ██╔══██║██╔══██╗██║     ██╔══██║",
    "██║  ██║███████╗███████║███████╗██║  ██║██║  ██║╚██████╗██║  ██║",
    "╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝",
]

HQ_LINES = [
    "██╗  ██╗ ██████╗ ",
    "██║  ██║██╔═══██╗",
    "███████║██║   ██║",
    "██╔══██║██║▄▄ ██║",
    "██║  ██║╚██████╔╝",
    "╚═╝  ╚═╝ ╚══▀▀═╝ ",
]

SUB_LINE = "multi-agent AI research platform"
LOGO_WIDTH = len(RESEARCH_LINES[0]) + 2 + len(HQ_LINES[0])  # approx
MIN_FULL_COLS = 88  # below this threshold use compact wordmark


def _render_full(palette_name: str = DEFAULT_THEME, reveal: int | None = None) -> str:
    """Build full ASCII logo markup, optionally capped to `reveal` columns per row."""
    p = get_palette(palette_name)
    lines: list[str] = []

    total_cols = max(len(r) for r in RESEARCH_LINES) + 2 + max(len(h) for h in HQ_LINES)
    cap = reveal if reveal is not None else total_cols

    for r_line, h_line in zip(RESEARCH_LINES, HQ_LINES, strict=False):
        combined = r_line + "  " + h_line
        visible = combined[:cap]
        r_part = visible[: len(r_line)]
        gap_part = visible[len(r_line) : len(r_line) + 2]
        h_part = visible[len(r_line) + 2 :]
        row = ""
        if r_part:
            row += f"[bold {p.accent}]{r_part}[/]"
        if gap_part:
            row += gap_part
        if h_part:
            row += f"[bold {p.accent_2}]{h_part}[/]"
        lines.append(row)

    lines.append("")
    lines.append(f"  [dim italic]{SUB_LINE}[/dim italic]")
    return "\n".join(lines)


def _render_compact(palette_name: str = DEFAULT_THEME) -> str:
    """Single-line brand for narrow terminals."""
    p = get_palette(palette_name)
    return (
        f"[bold {p.accent}]Research[/bold {p.accent}]"
        f"[bold {p.accent_2}]HQ[/bold {p.accent_2}]"
        f"  [dim]·  {SUB_LINE}[/dim]"
    )


# ── Static wordmark ───────────────────────────────────────────────────


class Wordmark(Static):
    """Full ASCII wordmark, static. Pass `theme_name` to colorize."""

    def __init__(self, theme_name: str = DEFAULT_THEME, **kwargs) -> None:
        super().__init__(_render_full(theme_name), **kwargs)
        self._theme_name = theme_name

    def set_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        self.update(_render_full(theme_name))


# ── Compact wordmark ──────────────────────────────────────────────────


class CompactWordmark(Static):
    """Single-line brand line for sidebars / narrow headers."""

    DEFAULT_CSS = "CompactWordmark { height: 2; }"

    def __init__(self, theme_name: str = DEFAULT_THEME, **kwargs) -> None:
        kwargs.setdefault("classes", "dash_compact_brand")
        super().__init__(_render_compact(theme_name), **kwargs)
        self._theme_name = theme_name

    def set_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        self.update(_render_compact(theme_name))


# ── Responsive wordmark ───────────────────────────────────────────────


class ResponsiveWordmark(Widget):
    """Shows full ASCII logo when wide enough, compact text when narrow."""

    DEFAULT_CSS = "ResponsiveWordmark { height: auto; max-height: 9; }"

    def __init__(self, theme_name: str = DEFAULT_THEME, **kwargs) -> None:
        kwargs.setdefault("classes", "dash_brand")
        super().__init__(**kwargs)
        self._theme_name = theme_name
        self._compact = False

    def compose(self) -> ComposeResult:
        yield Static(id="rw_inner")

    def on_mount(self) -> None:
        self._redraw()

    def on_resize(self, event) -> None:  # type: ignore[override]
        want_compact = event.size.width < MIN_FULL_COLS
        if want_compact != self._compact:
            self._compact = want_compact
            self._redraw()

    def set_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        self._redraw()

    def _redraw(self) -> None:
        inner = self.query_one("#rw_inner", Static)
        if self._compact:
            inner.update(_render_compact(self._theme_name))
        else:
            inner.update(_render_full(self._theme_name))


# ── Animated wordmark (splash) ────────────────────────────────────────


class AnimatedWordmark(Widget):
    """Full ASCII logo revealed left-to-right over `duration` seconds."""

    DEFAULT_CSS = "AnimatedWordmark { height: auto; }"

    def __init__(
        self,
        theme_name: str = DEFAULT_THEME,
        duration: float = 0.7,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._theme_name = theme_name
        self._duration = duration
        self._total_cols = max(len(r) for r in RESEARCH_LINES) + 2 + max(len(h) for h in HQ_LINES)
        self._reveal = 0

    def compose(self) -> ComposeResult:
        yield Static(id="aw_inner")

    def on_mount(self) -> None:
        self._inner = self.query_one("#aw_inner", Static)
        frames = max(12, int(self._duration * 24))
        self.set_interval(self._duration / frames, self._tick)

    def _tick(self) -> None:
        step = max(1, math.ceil(self._total_cols / max(12, int(self._duration * 24))))
        self._reveal = min(self._reveal + step, self._total_cols)
        self._inner.update(_render_full(self._theme_name, reveal=self._reveal))

    def set_theme(self, theme_name: str) -> None:
        self._theme_name = theme_name
        self._inner.update(_render_full(theme_name, reveal=self._reveal))
