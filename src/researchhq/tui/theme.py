"""ResearchHQ visual identity — theme palettes and Textual CSS.

Four premium themes ship by default:
  deep_space  Matte black + electric purple    (default)
  arctic      Clean light mode, indigo+violet
  cyber_noir  Dark graphite + cyan + magenta
  mono        Pure black / white minimalism

Usage:
  from researchhq.tui.theme import get_palette, render_css, PALETTES, DEFAULT_THEME
"""

from __future__ import annotations

from dataclasses import dataclass


# ── Palette ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Palette:
    name: str
    description: str
    # Backgrounds
    bg: str        # base surface
    bg_alt: str    # raised surface (sidebar, header)
    panel: str     # card / panel glass
    border: str    # subtle divider
    # Typography
    text: str       # primary
    text_dim: str   # secondary
    text_mute: str  # tertiary / placeholder
    # Brand accents
    accent: str    # primary (purple / blue / cyan …)
    accent_2: str  # secondary contrasting pop
    # Status
    success: str
    warning: str
    error: str


# ── Premium theme definitions ─────────────────────────────────────────

_DEEP_SPACE = Palette(
    name="deep_space",
    description="Matte black · electric purple · glass panels",
    bg="#07080f",
    bg_alt="#0d0f1a",
    panel="#111320",
    border="#1c2035",
    text="#dde4f0",
    text_dim="#8896aa",
    text_mute="#414d62",
    accent="#7c5cff",    # electric violet — the ResearchHQ signature color
    accent_2="#4a9eff",  # electric blue — secondary pop
    success="#3dd68c",
    warning="#f59e0b",
    error="#f06882",
)

_ARCTIC = Palette(
    name="arctic",
    description="Soft whites · indigo accents · minimal light mode",
    bg="#f6f8fc",
    bg_alt="#edf0f7",
    panel="#ffffff",
    border="#d4dae8",
    text="#0f1629",
    text_dim="#4b5675",
    text_mute="#9ba3bd",
    accent="#4f46e5",    # indigo
    accent_2="#7c3aed",  # violet
    success="#059669",
    warning="#d97706",
    error="#dc2626",
)

_CYBER_NOIR = Palette(
    name="cyber_noir",
    description="Cool graphite · electric cyan · neon magenta",
    bg="#09090e",
    bg_alt="#0e0e18",
    panel="#131322",
    border="#1a1a30",
    text="#e4e4ff",
    text_dim="#7272aa",
    text_mute="#363660",
    accent="#00d4ff",    # electric cyan
    accent_2="#cc44ff",  # neon magenta
    success="#00e599",
    warning="#ffb700",
    error="#ff3366",
)

_MONO = Palette(
    name="mono",
    description="Pure black · pure white · zero color",
    bg="#0a0a0a",
    bg_alt="#111111",
    panel="#171717",
    border="#282828",
    text="#f5f5f5",
    text_dim="#737373",
    text_mute="#404040",
    accent="#e5e5e5",    # bright near-white
    accent_2="#a3a3a3",  # mid-gray
    success="#d4d4d4",
    warning="#a3a3a3",
    error="#737373",
)

# Legacy palettes (kept for backward-compat; old theme names still resolve)
_AMBER = Palette(
    name="amber",
    description="Warm amber CRT vintage",
    bg="#0e0a05", bg_alt="#15100a", panel="#1d160c", border="#2c2114",
    text="#f5d893", text_dim="#c69b54", text_mute="#7a5a32",
    accent="#ffb43c", accent_2="#ff7a45",
    success="#9bd864", warning="#ffd166", error="#ef6c5b",
)
_MATRIX = Palette(
    name="matrix",
    description="Phosphor green hacker terminal",
    bg="#02060a", bg_alt="#040c0a", panel="#06120e", border="#0d2820",
    text="#9bf2b8", text_dim="#46b577", text_mute="#1f5e3e",
    accent="#39ff7a", accent_2="#00d4a3",
    success="#5eff9c", warning="#ffd84a", error="#ff5454",
)

PALETTES: dict[str, Palette] = {
    # Premium quartet
    "deep_space": _DEEP_SPACE,
    "arctic":     _ARCTIC,
    "cyber_noir": _CYBER_NOIR,
    "mono":       _MONO,
    # Legacy aliases
    "default":    _DEEP_SPACE,
    "amber":      _AMBER,
    "nord":       _ARCTIC,    # nord → arctic
    "midnight":   _DEEP_SPACE,
    "matrix":     _MATRIX,
}

DEFAULT_THEME = "deep_space"

# Ordered list for Ctrl+T cycling (premium first, then legacy)
THEME_CYCLE = ["deep_space", "arctic", "cyber_noir", "mono", "amber", "matrix"]


def get_palette(name: str) -> Palette:
    return PALETTES.get(name) or PALETTES[DEFAULT_THEME]


# ── Textual CSS template ──────────────────────────────────────────────
# $variables are substituted by render_css(). Ordering matters:
# $bg_alt before $bg, $text_dim/$text_mute before $text, $accent_2 before $accent.

CSS_TEMPLATE = r"""
/* ═══════════════════════════════════════════════════════════════════
   ResearchHQ TUI  —  visual identity v3
   ═══════════════════════════════════════════════════════════════════ */

/* ── Global ──────────────────────────────────────────────────────── */

Screen {
    background: $bg;
    color: $text;
}

/* ── Shell layout ────────────────────────────────────────────────── */

#header_bar {
    height: 1;
    background: $bg_alt;
    color: $text_dim;
    padding: 0 1;
}

#root_row {
    height: 1fr;
    min-height: 5;
}

#content_switcher {
    height: 1fr;
    background: $bg;
    padding: 1 2;
}

#view_dashboard,
#view_research,
#view_reports,
#view_settings {
    height: 100%;
    width: 100%;
}

/* ── Global query bar ────────────────────────────────────────────── */

#global_query {
    height: 3;
    background: $panel;
    color: $text;
    border: round $border;
    padding: 0 2;
    margin: 0 1;
}

#global_query:focus {
    border: round $accent;
}

/* ── Sidebar ─────────────────────────────────────────────────────── */

#sidebar {
    width: 22;
    min-width: 16;
    background: $bg_alt;
    border-right: solid $border;
    padding: 1 0 0 0;
}

.sidebar_section {
    height: 1;
    color: $text_mute;
    text-style: italic;
    padding: 0;
    margin: 1 0 0 0;
}

.sidebar_hint {
    height: 1;
    color: $text_mute;
    padding: 0 1 0 0;
}

#sidebar Button {
    background: $bg_alt;
    color: $text_dim;
    border: none;
    height: 1;
    width: 100%;
    text-align: left;
    padding: 0 1;
}

#sidebar Button:hover {
    background: $panel;
    color: $text;
}

#sidebar Button.-active {
    background: $panel;
    color: $accent;
    text-style: bold;
}

/* ── Cards ───────────────────────────────────────────────────────── */

.card {
    height: auto;
    background: $panel;
    border: round $border;
    padding: 0 2 1 2;
    margin: 0 0 1 0;
}

.card_title {
    height: 1;
    color: $accent;
    text-style: bold;
    padding: 0;
    margin: 1 0 1 0;
}

/* ── Dashboard layout ────────────────────────────────────────────── */

.dash_col {
    height: auto;
    width: 1fr;
}

.dash_compact_brand {
    height: 2;
    color: $accent;
    text-style: bold;
}

.dash_brand {
    height: auto;
    max-height: 9;
}

/* ── Research view ───────────────────────────────────────────────── */

#research_top {
    height: auto;
}

#research_bottom {
    height: 1fr;
    min-height: 6;
}

.toolbar {
    height: 3;
}

.scroll_card {
    height: 1fr;
    background: $panel;
    border: round $border;
    padding: 0 1;
}

#log_card    { width: 2fr; }
#report_card { width: 3fr; }

/* ── Agent pipeline ──────────────────────────────────────────────── */

#agent_pipeline {
    height: auto;
    max-height: 12;
    background: $panel;
    border: round $border;
    padding: 0 1;
}

.agent_row {
    height: 1;
    color: $text_dim;
    padding: 0 1;
}

.agent_row.-pending { color: $text_mute; }
.agent_row.-active  { color: $accent; text-style: bold; }
.agent_row.-done    { color: $success; }
.agent_row.-fail    { color: $error; }

/* ── Effort chips ────────────────────────────────────────────────── */

.effort_chip {
    height: 3;
    width: 12;
    border: round $border;
    color: $text_dim;
    background: $panel;
    content-align: center middle;
}

.effort_chip.-active {
    background: $accent 15%;
    border: round $accent;
    color: $accent;
    text-style: bold;
}

/* ── Log console ─────────────────────────────────────────────────── */

RichLog {
    background: $bg_alt;
    color: $text_dim;
    scrollbar-size: 1 1;
    scrollbar-color: $accent 20% $bg_alt;
    scrollbar-color-hover: $accent $bg_alt;
    scrollbar-color-active: $accent_2 $bg_alt;
}

.log_info { color: $text_dim; }
.log_warn { color: $warning; }
.log_err  { color: $error; }
.log_ok   { color: $success; }

/* ── Report pane ─────────────────────────────────────────────────── */

_ReportPane {
    background: $panel;
    color: $text;
    padding: 0 1;
    overflow-y: auto;
}

#report_pane {
    background: $panel;
    color: $text;
    padding: 0 1;
    overflow-y: auto;
}

/* ── KV pairs ────────────────────────────────────────────────────── */

.kv_label { color: $text_mute; }
.kv_value { color: $text; }

/* ── Settings ────────────────────────────────────────────────────── */

.input_bar {
    height: 5;
    background: $bg_alt;
    border-top: solid $border;
    padding: 1 2;
}

.input_bar Input:focus {
    border: round $accent;
}

.settings_row {
    height: 3;
    margin: 0;
    padding: 0;
}

.settings_label {
    width: 22;
    color: $text_dim;
    padding: 1 0 0 0;
}

#settings_buttons {
    height: 3;
    padding: 0 1 0 1;
}

#set_status {
    height: auto;
    padding: 0 1;
}

/* ── History / reports view ──────────────────────────────────────── */

#reports_filter_card {
    height: auto;
    background: $panel;
    border: round $border;
    padding: 0 2 1 2;
    margin: 0 0 1 0;
}

/* ── Scrollbars (global) ─────────────────────────────────────────── */

#dashboard_scroll,
#reports_scroll,
#settings_scroll {
    height: 1fr;
    scrollbar-size: 1 1;
    scrollbar-color: $accent 20% $bg_alt;
    scrollbar-color-hover: $accent $bg_alt;
    scrollbar-color-active: $accent_2 $bg_alt;
}

/* ── Toasts ──────────────────────────────────────────────────────── */

.toast {
    height: auto;
    background: $panel;
    border: round $accent;
    padding: 1 2;
    margin: 0 2 1 0;
}

.toast.-error { border: round $error; }
.toast.-warn  { border: round $warning; }
.toast.-ok    { border: round $success; }

/* ── Inputs / selects / buttons (global defaults) ────────────────── */

Input {
    background: $panel;
    color: $text;
    border: round $border;
}

Input:focus {
    border: round $accent;
}

Select {
    background: $panel;
    color: $text;
    border: round $border;
}

Select:focus {
    border: round $accent;
}

Select > SelectOverlay {
    background: $panel;
    border: round $border;
}

RadioSet {
    background: $panel;
    border: none;
}

Button {
    background: $panel;
    color: $text;
    border: round $border;
}

Button.-primary {
    background: $accent 20%;
    color: $accent;
    border: round $accent;
    text-style: bold;
}

Button:hover {
    background: $bg_alt;
    color: $text;
}

Button.-primary:hover {
    background: $accent 30%;
    color: $accent;
}

/* ── Global scrollbar fallback ───────────────────────────────────── */

* {
    scrollbar-size: 1 1;
    scrollbar-color: $accent 20% $bg_alt;
    scrollbar-color-hover: $accent $bg_alt;
    scrollbar-color-active: $accent_2 $bg_alt;
}
"""


def render_css(theme: str = DEFAULT_THEME) -> str:
    """Substitute palette hex values into CSS_TEMPLATE and return the result."""
    p = get_palette(theme)
    css = CSS_TEMPLATE
    # Order matters: longer tokens must be replaced before shorter prefixes
    css = css.replace("$bg_alt",    p.bg_alt)
    css = css.replace("$bg",        p.bg)
    css = css.replace("$panel",     p.panel)
    css = css.replace("$border",    p.border)
    css = css.replace("$text_dim",  p.text_dim)
    css = css.replace("$text_mute", p.text_mute)
    css = css.replace("$text",      p.text)
    css = css.replace("$accent_2",  p.accent_2)
    css = css.replace("$accent",    p.accent)
    css = css.replace("$success",   p.success)
    css = css.replace("$warning",   p.warning)
    css = css.replace("$error",     p.error)
    return css
