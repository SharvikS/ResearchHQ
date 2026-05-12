"""ResearchHQ TUI theme palette + Textual CSS.

A theme is just a name → palette dict. The CSS template substitutes color
variables; Textual reapplies styling whenever the active theme changes.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    description: str
    bg: str
    bg_alt: str
    panel: str
    border: str
    text: str
    text_dim: str
    text_mute: str
    accent: str
    accent_2: str
    success: str
    warning: str
    error: str


PALETTES: dict[str, Palette] = {
    "default": Palette(
        name="default",
        description="ResearchHQ deep — high-contrast dark with teal accent.",
        bg="#0c0f14",
        bg_alt="#10141c",
        panel="#141923",
        border="#1f2735",
        text="#e6edf3",
        text_dim="#9ba6b4",
        text_mute="#5a6573",
        accent="#34d4bb",
        accent_2="#7c5cff",
        success="#4ade80",
        warning="#fbbf24",
        error="#f87171",
    ),
    "amber": Palette(
        name="amber",
        description="Warm amber CRT.",
        bg="#0e0a05",
        bg_alt="#15100a",
        panel="#1d160c",
        border="#2c2114",
        text="#f5d893",
        text_dim="#c69b54",
        text_mute="#7a5a32",
        accent="#ffb43c",
        accent_2="#ff7a45",
        success="#9bd864",
        warning="#ffd166",
        error="#ef6c5b",
    ),
    "nord": Palette(
        name="nord",
        description="Cool arctic blues.",
        bg="#0f1620",
        bg_alt="#161e2c",
        panel="#1c2532",
        border="#2a3445",
        text="#d8dee9",
        text_dim="#a8b2c2",
        text_mute="#6b7888",
        accent="#88c0d0",
        accent_2="#81a1c1",
        success="#a3be8c",
        warning="#ebcb8b",
        error="#bf616a",
    ),
    "midnight": Palette(
        name="midnight",
        description="Deep midnight blue with violet accents.",
        bg="#070a18",
        bg_alt="#0d1224",
        panel="#121833",
        border="#1f2950",
        text="#e2e7ff",
        text_dim="#9aa3d4",
        text_mute="#5b658c",
        accent="#6e8bff",
        accent_2="#b061ff",
        success="#5ce7c8",
        warning="#ffd166",
        error="#ff6b8a",
    ),
    "matrix": Palette(
        name="matrix",
        description="Phosphor-green hacker terminal.",
        bg="#02060a",
        bg_alt="#040c0a",
        panel="#06120e",
        border="#0d2820",
        text="#9bf2b8",
        text_dim="#46b577",
        text_mute="#1f5e3e",
        accent="#39ff7a",
        accent_2="#00d4a3",
        success="#5eff9c",
        warning="#ffd84a",
        error="#ff5454",
    ),
}


DEFAULT_THEME = "default"


def get_palette(name: str) -> Palette:
    return PALETTES.get(name, PALETTES[DEFAULT_THEME])


CSS_TEMPLATE = """
Screen {
    background: $bg;
    color: $text;
}

/* Layout: pure vertical flow.
 * - header_bar  : fixed 1 line at the top
 * - root_row    : flexes (1fr) — sidebar + active view live here
 * - global_query: fixed 3 lines (border-top + content + border-bottom)
 * - Footer      : docks bottom (Textual default), 1 line
 *
 * No competing docks. The Footer is the ONLY docked widget; everything
 * else flows top-to-bottom and the input always sits directly above
 * the footer regardless of terminal size.
 */
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
    overflow-y: auto;
    overflow-x: hidden;
}

/* Research view: dedicated containers so the toolbar/pipeline never push the
 * log/report split off-screen, and the split itself can scroll internally. */
#research_top {
    height: auto;
}

#research_bottom {
    height: 1fr;
    min-height: 6;
}

#global_query {
    height: 3;
    margin: 0 2;
    background: $panel;
    color: $text;
    border: round $border;
}

#global_query:focus {
    border: round $accent;
}

#header_bar .header_brand {
    color: $accent;
    text-style: bold;
}

#header_bar .header_segment {
    color: $text_dim;
}

#header_bar .header_segment_value {
    color: $text;
}

#sidebar {
    width: 24;
    min-width: 18;
    background: $bg_alt;
    border-right: solid $border;
    padding: 1 0 0 0;
}

/* Research-screen toolbar: holds the mode Select + 3-chip effort selector,
 * both of which are 3 lines tall. The toolbar must be exactly 3 lines high
 * with NO inner vertical padding, otherwise the Select/chip bottom borders
 * get clipped. Spacing below is provided by margin instead. */
.toolbar {
    height: 3;
    padding: 0;
    margin: 0 0 1 0;
}

.toolbar Select {
    width: 1fr;
    margin: 0 1 0 0;
}

.toolbar EffortSelector {
    width: auto;
    height: 3;
}

/* Each row's leading whitespace lives in its TEXT (see sidebar.compose)
 * so the visible "  X" column lines up identically across Static and
 * Button regardless of per-widget defaults. CSS adds zero horizontal
 * padding here — only the right margin on hints to keep the trailing
 * label safely inside the rail. */
#sidebar .sidebar_section {
    color: $text_mute;
    text-style: italic;
    padding: 0;
    margin: 1 0 0 0;
    height: 1;
}

#sidebar .sidebar_hint {
    height: 1;
    padding: 0 1 0 0;
    color: $text_mute;
}

#sidebar Button {
    width: 100%;
    height: 1;
    margin: 0;
    background: $bg_alt;
    color: $text_dim;
    border: none;
    text-align: left;
    padding: 0;
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

#main_workspace {
    background: $bg;
    padding: 1 2;
}

/* Cards size to their content; only stretch when explicitly told to. */
.card {
    background: $panel;
    border: round $border;
    padding: 0 2 1 2;
    margin: 0 0 1 0;
    height: auto;
}

.card_title {
    color: $accent;
    text-style: bold;
    padding: 0;
    height: 1;
    margin: 1 0 1 0;
}

/* Dashboard column wrappers: equal width, content-driven height. */
.dash_col {
    width: 1fr;
    padding: 0 1;
    height: auto;
}

.dash_compact_brand {
    height: 2;
    padding: 0 1 1 1;
    color: $accent;
    text-style: bold;
}

.dash_compact_brand .dash_tagline {
    color: $text_mute;
    text-style: italic;
}

/* Responsive logo: full ASCII = 8 lines (6 art + blank + tagline);
 * compact fallback = 1 line. Container sizes to its rendered content. */
.dash_brand {
    height: auto;
    max-height: 9;
    padding: 0 0 1 0;
}

#dashboard_grid {
    height: auto;
}

#dashboard_scroll,
#reports_scroll,
#settings_scroll {
    height: 1fr;
    overflow-y: auto;
    overflow-x: hidden;
    scrollbar-size: 1 1;
    scrollbar-color: $accent $bg_alt;
    scrollbar-color-hover: $accent_2 $bg_alt;
    scrollbar-color-active: $accent_2 $bg_alt;
}

/* Settings form rows */
.settings_row {
    height: 3;
    margin: 0 0 0 0;
    padding: 0;
}

.settings_label {
    width: 22;
    color: $text_dim;
    padding: 1 0 0 0;
}

.settings_row Select,
.settings_row Input {
    width: 1fr;
}

#settings_buttons {
    height: 3;
    padding: 0 1 0 1;
    margin: 1 0 0 0;
}

#settings_buttons Button {
    margin: 0 1 0 0;
}

#set_status {
    height: auto;
    margin: 1 0 0 0;
    padding: 0 1;
}

/* Global scrollbar styling — applies to anything with overflow. */
* {
    scrollbar-size: 1 1;
    scrollbar-color: $accent 30% $bg_alt;
    scrollbar-color-hover: $accent $bg_alt;
    scrollbar-color-active: $accent_2 $bg_alt;
    scrollbar-background: $bg_alt;
    scrollbar-background-hover: $bg_alt;
    scrollbar-background-active: $bg_alt;
}

.kv_label {
    color: $text_mute;
}

.kv_value {
    color: $text;
}

.input_bar {
    height: 5;
    background: $bg_alt;
    border-top: solid $border;
    padding: 1 2;
}

.input_bar Input {
    background: $panel;
    color: $text;
    border: round $border;
}

.input_bar Input:focus {
    border: round $accent;
}

#agent_pipeline {
    height: auto;
    max-height: 12;
    background: $panel;
    border: round $border;
    padding: 0 1;
    margin: 0 0 1 0;
    overflow-y: auto;
}

.agent_row {
    height: 1;
    padding: 0 1;
    color: $text_dim;
}

.agent_row .agent_name {
    color: $text;
    width: 14;
}

.agent_row.-pending .agent_name { color: $text_mute; }
.agent_row.-active  .agent_name { color: $accent; text-style: bold; }
.agent_row.-done    .agent_name { color: $success; }
.agent_row.-fail    .agent_name { color: $error; }

.agent_status {
    color: $text_dim;
    width: 1fr;
}

.agent_timing {
    color: $text_mute;
    width: 14;
    text-align: right;
}

/* Research-screen split: 40% logs / 60% report. Both scroll. */
.research_split {
    height: 1fr;
}

#log_card {
    width: 2fr;
    margin: 0 1 0 0;
    height: 1fr;
}

#report_card {
    width: 3fr;
    height: 1fr;
}

.scroll_card {
    background: $panel;
    border: round $border;
    padding: 0 1;
    height: 1fr;
}

#log_console {
    height: 1fr;
    background: $bg_alt;
    color: $text_dim;
    padding: 0 1;
    overflow: auto;
    scrollbar-size: 1 1;
}

#log_console .log_info { color: $text_dim; }
#log_console .log_warn { color: $warning; }
#log_console .log_err  { color: $error; }
#log_console .log_ok   { color: $success; }

#report_pane {
    height: 1fr;
    overflow: hidden;
}

#report_view {
    height: 1fr;
    background: $panel;
    color: $text;
    padding: 0 1;
    overflow-y: auto;
    scrollbar-size: 1 1;
}

.toast {
    dock: bottom;
    height: auto;
    background: $panel;
    border: round $accent;
    padding: 1 2;
    margin: 0 2 1 0;
}

.toast.-error  { border: round $error; }
.toast.-warn   { border: round $warning; }
.toast.-ok     { border: round $success; }

.effort_chip {
    width: 12;
    height: 3;
    border: round $border;
    color: $text_dim;
    background: $panel;
    content-align: center middle;
}

.effort_chip.-active {
    background: $accent 30%;
    border: round $accent;
    color: $accent;
    text-style: bold;
}
"""


def render_css(theme: str = DEFAULT_THEME) -> str:
    """Substitute palette variables into the CSS template.

    Replacements are applied longest-key-first so that shorter prefixes (e.g.
    `$bg`) don't cannibalize longer keys (e.g. `$bg_alt`).
    """
    p = get_palette(theme)
    mapping = {
        "$bg_alt": p.bg_alt, "$bg": p.bg,
        "$panel": p.panel, "$border": p.border,
        "$text_mute": p.text_mute, "$text_dim": p.text_dim, "$text": p.text,
        "$accent_2": p.accent_2, "$accent": p.accent,
        "$success": p.success, "$warning": p.warning, "$error": p.error,
    }
    css = CSS_TEMPLATE
    for key in sorted(mapping, key=len, reverse=True):
        css = css.replace(key, mapping[key])
    return css
