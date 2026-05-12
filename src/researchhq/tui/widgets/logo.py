"""ResearchHQ wordmark widgets.

- `AnimatedWordmark` — full ASCII, used by the splash screen.
- `Wordmark`         — full ASCII, static (kept for potential reuse).
- `CompactWordmark`  — single-line brand + tagline, used by the dashboard so
                       the brand moment doesn't dominate the screen.

Original ASCII typeface — does not use any third-party logo or wordmark.
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Group
from rich.text import Text
from textual.widgets import Static

from researchhq.tui.theme import Palette, get_palette


# RESEARCH (8 letters, ANSI Shadow font) and HQ (2 letters) are stored as two
# *separate* string arrays so they can be styled independently — no fragile
# column-index splitting.
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
_GAP = "  "  # gap between RESEARCH and HQ blocks
# Total ASCII width = 64 + 2 + 17 = 83 chars. Add a small left margin for
# breathing room when centered.

# Backwards-compat: a few smoke tests still import WORDMARK_LINES.
WORDMARK_LINES = [
    f"  {RESEARCH_LINES[i]}{_GAP}{HQ_LINES[i]}  " for i in range(6)
]
SUB_LINE = "HQ  ·  premium research workstation"


def _line_to_text(idx: int, palette: Palette) -> Text:
    """Render one wordmark row as RESEARCH (teal) + HQ (purple) — two spans,
    no character-index slicing."""
    t = Text("  ", style="")  # 2-char left margin
    t.append(RESEARCH_LINES[idx], style=f"bold {palette.accent}")
    t.append(_GAP)
    t.append(HQ_LINES[idx], style=f"bold {palette.accent_2}")
    return t


def _full_lines(palette: Palette) -> list[Text]:
    """Build the dual-color wordmark — one Text per row, two color spans each."""
    return [_line_to_text(i, palette) for i in range(len(RESEARCH_LINES))]


def _render(palette: Palette, reveal: int = 1_000) -> Group:
    """`reveal` is a character cap for the marquee animation (0–N chars).
    The cap is applied per-row to the total visible width (RESEARCH + gap + HQ)
    so the reveal sweep keeps the dual-color split intact."""
    lines: list[Text] = []
    per_row_total = len(RESEARCH_LINES[0]) + len(_GAP) + len(HQ_LINES[0])
    written = 0
    for i in range(len(RESEARCH_LINES)):
        if written >= reveal:
            lines.append(Text(""))
            continue
        room = reveal - written
        if room >= per_row_total:
            lines.append(_line_to_text(i, palette))
            written += per_row_total
        else:
            # Partial reveal — slice the combined row carefully so we don't
            # bleed accent_2 into the RESEARCH block.
            t = Text()
            r_len = len(RESEARCH_LINES[i])
            if room <= r_len:
                t.append(RESEARCH_LINES[i][:room], style=f"bold {palette.accent}")
            else:
                t.append(RESEARCH_LINES[i], style=f"bold {palette.accent}")
                remaining = room - r_len
                gap_take = min(len(_GAP), remaining)
                t.append(_GAP[:gap_take])
                remaining -= gap_take
                if remaining > 0:
                    t.append(HQ_LINES[i][:remaining], style=f"bold {palette.accent_2}")
            lines.append(t)
            written = reveal  # stop revealing further rows this frame
    lines.append(Text(""))
    lines.append(Text(SUB_LINE, style=f"italic {palette.text_dim}"))
    return Group(*[Align.center(t) for t in lines])


class Wordmark(Static):
    """Static (non-animated) wordmark used in dashboard header."""

    def __init__(self, theme_name: str = "default", **kwargs) -> None:
        super().__init__(_render(get_palette(theme_name)), **kwargs)
        self._theme = theme_name

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self.update(_render(get_palette(theme_name)))


class CompactWordmark(Static):
    """Two-line brand mark for in-app screens. Renders as:

        ResearchHQ  ·  premium research workstation
        ─────────────────────────────────────────────
    """

    def __init__(self, theme_name: str = "default", **kwargs) -> None:
        kwargs.setdefault("classes", "dash_compact_brand")
        super().__init__(self._build(get_palette(theme_name)), **kwargs)
        self._theme = theme_name

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self.update(self._build(get_palette(theme_name)))

    @staticmethod
    def _build(p: Palette) -> Text:
        line = Text()
        line.append("Research", style=f"bold {p.accent}")
        line.append("HQ", style=f"bold {p.accent_2}")
        line.append("  ·  ", style=p.text_mute)
        line.append("premium research workstation", style=f"italic {p.text_dim}")
        return line


# Width threshold: full ASCII needs ~85 cols (64 RESEARCH + 2 gap + 17 HQ +
# small margins). Below that we fall back to the compact single-line variant
# so the dashboard never wraps.
_FULL_LOGO_MIN_WIDTH = 88


class ResponsiveWordmark(Static):
    """Dashboard brand mark that swaps between full ASCII and compact text
    based on the available width. Tagline 'HQ · premium research workstation'
    is always shown beneath the brand.
    """

    def __init__(self, theme_name: str = "default", **kwargs) -> None:
        kwargs.setdefault("classes", "dash_brand")
        # Initial render assumes a wide terminal; on_resize corrects it.
        super().__init__(self._build(get_palette(theme_name), full=True), **kwargs)
        self._theme = theme_name
        self._is_full = True

    def on_resize(self, event) -> None:
        full = event.size.width >= _FULL_LOGO_MIN_WIDTH
        if full == self._is_full:
            return
        self._is_full = full
        self.update(self._build(get_palette(self._theme), full=full))
        # Inform the layout that our preferred height changed.
        self.refresh(layout=True)

    def set_theme(self, theme_name: str) -> None:
        self._theme = theme_name
        self.update(self._build(get_palette(theme_name), full=self._is_full))

    @staticmethod
    def _build(palette: Palette, *, full: bool) -> Group:
        if full:
            lines = _full_lines(palette)
            lines.append(Text(""))
            lines.append(Text(SUB_LINE, style=f"italic {palette.text_dim}"))
            return Group(*[Align.center(t) for t in lines])
        # Compact fallback — single line with brand colors split inline
        line = Text()
        line.append("Research", style=f"bold {palette.accent}")
        line.append("HQ", style=f"bold {palette.accent_2}")
        line.append("  ·  ", style=palette.text_mute)
        line.append("premium research workstation", style=f"italic {palette.text_dim}")
        return Group(Align.center(line))


class AnimatedWordmark(Static):
    """Splash-screen variant that reveals the wordmark left-to-right."""

    def __init__(self, theme_name: str = "default", duration: float = 0.6, **kwargs) -> None:
        super().__init__(_render(get_palette(theme_name), reveal=0), **kwargs)
        self._theme = theme_name
        self._duration = duration
        self._total_chars = sum(len(line) for line in WORDMARK_LINES)
        self._step = max(1, self._total_chars // 24)
        self._revealed = 0

    def on_mount(self) -> None:
        self._tick()
        self.set_interval(self._duration / 24, self._tick)

    def _tick(self) -> None:
        if self._revealed >= self._total_chars:
            return
        self._revealed = min(self._total_chars, self._revealed + self._step)
        self.update(_render(get_palette(self._theme), reveal=self._revealed))
