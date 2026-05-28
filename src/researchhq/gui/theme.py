"""ResearchHQ Studio theme system.

Single source of truth for every colour used in the desktop GUI. A
`ThemeManager` singleton holds the active `Theme` and emits a Qt signal
whenever the user switches; widgets that hold inline colours subscribe and
re-style themselves on the fly.

Built-in themes
---------------
- ``Deep Space`` — deep navy + electric cyan + magenta (default)
- ``Neon``       — magenta / cyan synthwave on near-black
- ``Aurora``     — cosmic purple + mint
- ``Mono``       — neutral graphite / white minimal

The QSS template is rendered from the active palette via ``render_qss()``.
Callers that just need the bundled QSS string can keep using ``DARK_QSS``
which now resolves to the active theme's rendered stylesheet.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import QObject, Signal


# ── Theme dataclass ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Theme:
    """Colour tokens for one theme.

    Field names are intentionally semantic (``bg_raised``, ``accent2``, …) so
    QSS templates and motion helpers can pull colours by purpose rather than
    hard-coding hex values. All values are ``#rrggbb`` strings — Qt parses
    them everywhere they're consumed.
    """

    name: str
    is_dark: bool

    # Layered surfaces — deeper to lighter.
    bg_deep: str       # outermost frame / behind everything
    bg_base: str       # page background
    bg_raised: str     # cards, panels
    bg_hover: str      # hovered surface (sidebar item, list row)
    bg_select: str     # selected surface (active table row)
    bg_input: str      # text input fill

    # Borders.
    border: str        # primary divider colour
    border_lt: str     # lighter divider for inner cells

    # Brand identity.
    accent: str        # primary brand colour — cyan/violet/etc.
    accent_dim: str    # de-emphasised version (disabled primary)
    accent_bg: str     # accent-tinted surface (selected pill / chip bg)
    accent2: str       # secondary brand colour for typographic pop
    accent2_dim: str

    # Status palette.
    ok: str
    warn: str
    err: str
    err_dim: str

    # Typography.
    text: str          # primary text
    text_dim: str      # secondary / labels
    text_mute: str     # tertiary / placeholders
    text_mono: str     # monospace text (logs, code)

    # Reserved for future syntax-highlighted terminal widget.
    term_bg: str
    term_fg: str
    term_glow: str
    term_border: str

    # Backwards-compat: legacy code referenced these names. The dataclass keeps
    # both old and new spellings synonymous to avoid breaking pages mid-port.
    @property
    def panel(self) -> str:        return self.bg_raised
    @property
    def panel_2(self) -> str:      return self.bg_hover
    @property
    def text_muted(self) -> str:   return self.text_dim
    @property
    def bg_alt(self) -> str:       return self.bg_raised
    @property
    def bg(self) -> str:           return self.bg_base


# ── Built-in palettes ────────────────────────────────────────────────────────


DEEP_SPACE = Theme(
    name="Deep Space",
    is_dark=True,
    bg_deep    = "#070b14",
    bg_base    = "#0c1322",
    bg_raised  = "#131c30",
    bg_hover   = "#1a2641",
    bg_select  = "#11305a",
    bg_input   = "#0a1428",
    border     = "#1f2d44",
    border_lt  = "#2c3e5c",
    accent     = "#00d4ff",
    accent_dim = "#0099bb",
    accent_bg  = "#082236",
    accent2    = "#ff5cd0",
    accent2_dim= "#a8338a",
    ok         = "#00e57a",
    warn       = "#ffaa00",
    err        = "#ff4d63",
    err_dim    = "#992330",
    text       = "#dde7f4",
    text_dim   = "#7689a4",
    text_mute  = "#4a5b78",
    text_mono  = "#7ec8e3",
    term_bg    = "#04080f",
    term_fg    = "#7ee0ff",
    term_glow  = "#00d4ff",
    term_border= "#0a3a55",
)

NEON = Theme(
    name="Neon",
    is_dark=True,
    bg_deep    = "#08020f",
    bg_base    = "#11061d",
    bg_raised  = "#1a0a2c",
    bg_hover   = "#260f3c",
    bg_select  = "#3a1657",
    bg_input   = "#10051a",
    border     = "#2a1340",
    border_lt  = "#48206c",
    accent     = "#ff2bd6",
    accent_dim = "#b3168f",
    accent_bg  = "#2b0728",
    accent2    = "#7ef9ff",
    accent2_dim= "#3ec5d4",
    ok         = "#39ff88",
    warn       = "#ffd400",
    err        = "#ff3a6e",
    err_dim    = "#8a1738",
    text       = "#ffe6fb",
    text_dim   = "#9b6cb6",
    text_mute  = "#5f3c7a",
    text_mono  = "#7ef9ff",
    term_bg    = "#070110",
    term_fg    = "#ff7df1",
    term_glow  = "#ff2bd6",
    term_border= "#5b1670",
)

AURORA = Theme(
    name="Aurora",
    is_dark=True,
    bg_deep    = "#040616",
    bg_base    = "#0a0e23",
    bg_raised  = "#101632",
    bg_hover   = "#1a2247",
    bg_select  = "#23306a",
    bg_input   = "#080c1f",
    border     = "#1c2548",
    border_lt  = "#2d3a66",
    accent     = "#9d7bff",
    accent_dim = "#6c4cd6",
    accent_bg  = "#160f33",
    accent2    = "#5effc8",
    accent2_dim= "#2a8c6f",
    ok         = "#5effc8",
    warn       = "#ffc857",
    err        = "#ff5d8a",
    err_dim    = "#8c2848",
    text       = "#e6e9ff",
    text_dim   = "#7a82b8",
    text_mute  = "#4d557f",
    text_mono  = "#a9b9ff",
    term_bg    = "#04061a",
    term_fg    = "#c9b9ff",
    term_glow  = "#9d7bff",
    term_border= "#3a2d6c",
)

MONO = Theme(
    name="Mono",
    is_dark=True,
    bg_deep    = "#06070a",
    bg_base    = "#0d0f14",
    bg_raised  = "#15181f",
    bg_hover   = "#1c2029",
    bg_select  = "#2a2f3a",
    bg_input   = "#0a0c11",
    border     = "#23272f",
    border_lt  = "#363b46",
    accent     = "#e6ecf3",
    accent_dim = "#9aa1ad",
    accent_bg  = "#1f242d",
    accent2    = "#9aa1ad",
    accent2_dim= "#6a7080",
    ok         = "#5fcf80",
    warn       = "#e8b04b",
    err        = "#e85d5d",
    err_dim    = "#7a2b2b",
    text       = "#e6ecf3",
    text_dim   = "#8a92a0",
    text_mute  = "#525a68",
    text_mono  = "#cdd4dd",
    term_bg    = "#06070a",
    term_fg    = "#cdd4dd",
    term_glow  = "#9aa1ad",
    term_border= "#363b46",
)


THEMES: dict[str, Theme] = {
    "deep_space": DEEP_SPACE,
    "neon":       NEON,
    "aurora":     AURORA,
    "mono":       MONO,
}

DEFAULT_THEME = "deep_space"


# ── ThemeManager (signal-emitting singleton) ─────────────────────────────────


class ThemeManager(QObject):
    """Singleton that owns the active theme and notifies subscribers.

    Widgets connect to ``theme_changed`` and re-render whichever inline
    colours they hold. The QSS itself is reapplied at app level — pages
    only need to subscribe if they paint custom widgets (logos, dividers)
    that read raw colour values.
    """

    theme_changed = Signal(object)  # emits the new Theme

    _instance: Optional["ThemeManager"] = None

    @classmethod
    def instance(cls) -> "ThemeManager":
        if cls._instance is None:
            cls._instance = ThemeManager()
        return cls._instance

    def __init__(self) -> None:
        super().__init__()
        self._theme: Theme = THEMES[DEFAULT_THEME]
        self._key: str = DEFAULT_THEME

    def current(self) -> Theme:
        return self._theme

    def key(self) -> str:
        return self._key

    def set_theme(self, key: str) -> bool:
        """Switch active theme. Returns True if the key was known."""
        if key not in THEMES:
            return False
        if key == self._key:
            return True
        self._theme = THEMES[key]
        self._key = key
        self.theme_changed.emit(self._theme)
        return True


def theme() -> Theme:
    """Module-level shorthand for ``ThemeManager.instance().current()``."""
    return ThemeManager.instance().current()


# ── QSS template ─────────────────────────────────────────────────────────────


_QSS_TEMPLATE = """
/* ─── Global ─────────────────────────────────────────────────────────── */
QWidget {{
    background-color: {bg_base};
    color: {text};
    font-family: "SF Pro Text", "Inter", "Segoe UI", system-ui, sans-serif;
    font-size: 13px;
}}

QMainWindow {{ background-color: {bg_base}; }}

/* ─── Sidebar ───────────────────────────────────────────────────────── */
#Sidebar {{
    background-color: {bg_deep};
    border-right: 1px solid {border};
}}
#Sidebar QPushButton {{
    text-align: left;
    padding: 10px 16px;
    background-color: transparent;
    border: none;
    border-radius: 8px;
    color: {text_dim};
    font-size: 13px;
}}
#Sidebar QPushButton:hover {{
    background-color: {bg_hover};
    color: {text};
}}
#Sidebar QPushButton[active="true"] {{
    background-color: {accent_bg};
    color: {accent};
    font-weight: 600;
    border-left: 2px solid {accent};
    padding-left: 14px;
}}
#SidebarBrand {{
    color: {text};
    font-size: 18px;
    font-weight: 700;
    padding: 22px 16px 4px 16px;
    background-color: transparent;
    letter-spacing: 1px;
}}
#SidebarBrandSub {{
    color: {accent2};
    font-size: 10px;
    padding: 0 16px 18px 16px;
    background-color: transparent;
    letter-spacing: 2px;
    text-transform: uppercase;
}}

/* Hairline gradient between sidebar and content. Painted manually by
   WorkspaceDivider — this rule covers the standard QFrame fallback. */
#WorkspaceDivider {{
    background-color: transparent;
}}

/* ─── Cards ─────────────────────────────────────────────────────────── */
#Card {{
    background-color: {bg_raised};
    border: 1px solid {border};
    border-radius: 12px;
}}
#Card:hover {{
    border-color: {border_lt};
}}
#CardTitle {{
    color: {text};
    font-size: 13px;
    font-weight: 600;
    background-color: transparent;
    letter-spacing: 0.4px;
}}
#CardSubtitle {{
    color: {text_dim};
    font-size: 11px;
    background-color: transparent;
}}
#StatValue {{
    color: {accent};
    font-size: 24px;
    font-weight: 700;
    background-color: transparent;
}}
#StatLabel {{
    color: {text_dim};
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    background-color: transparent;
}}

/* ─── Page chrome ───────────────────────────────────────────────────── */
QLabel#PageTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {text};
    background-color: transparent;
    letter-spacing: 0.3px;
}}
QLabel#PageKicker {{
    font-size: 10px;
    font-weight: 600;
    color: {accent2};
    background-color: transparent;
    letter-spacing: 2px;
    text-transform: uppercase;
}}
QLabel#Muted {{
    color: {text_dim};
    background-color: transparent;
}}
QLabel#MutedItalic {{
    color: {text_dim};
    background-color: transparent;
    font-style: italic;
}}
QLabel#ProviderName {{
    color: {text};
    background-color: transparent;
}}
QLabel#StatusOk {{
    color: {ok};
    background-color: transparent;
}}
QLabel#StatusOff {{
    color: {text_dim};
    background-color: transparent;
}}
QLabel#StatValueInline {{
    color: {accent};
    font-size: 16px;
    font-weight: 600;
    background-color: transparent;
}}
QLabel#KeyStatus {{ background-color: transparent; }}

/* ─── Inputs ───────────────────────────────────────────────────────── */
QLineEdit, QPlainTextEdit, QTextEdit {{
    background-color: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 10px;
    color: {text};
    selection-background-color: {accent_bg};
    selection-color: {accent};
}}
QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {accent};
}}
QLineEdit#QueryInput {{
    font-size: 14px;
    padding: 12px 14px;
    background-color: {bg_input};
    border: 1px solid {border_lt};
}}
QLineEdit#QueryInput:focus {{
    border: 1px solid {accent};
}}

QComboBox, QSpinBox {{
    background-color: {bg_input};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 6px 10px;
    color: {text};
    min-width: 90px;
}}
QComboBox:focus, QSpinBox:focus {{ border: 1px solid {accent}; }}
QComboBox::drop-down {{
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {bg_raised};
    border: 1px solid {border_lt};
    selection-background-color: {accent_bg};
    selection-color: {accent};
    color: {text};
    padding: 4px;
}}

QCheckBox {{
    color: {text};
    background-color: transparent;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 14px; height: 14px;
    border-radius: 4px;
    border: 1px solid {border_lt};
    background-color: {bg_input};
}}
QCheckBox::indicator:checked {{
    background-color: {accent};
    border-color: {accent};
}}

/* ─── Buttons ──────────────────────────────────────────────────────── */
QPushButton {{
    background-color: {bg_raised};
    color: {text};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {bg_hover};
    border-color: {accent};
    color: {accent};
}}
QPushButton:pressed {{
    background-color: {accent_bg};
    color: {accent};
}}
QPushButton:disabled {{
    color: {text_mute};
    background-color: {bg_raised};
    border-color: {border};
}}

QPushButton#Primary {{
    background-color: {accent};
    border: 1px solid {accent};
    color: {bg_deep};
    font-weight: 600;
}}
QPushButton#Primary:hover {{
    background-color: {accent2};
    border-color: {accent2};
    color: {bg_deep};
}}
QPushButton#Primary:pressed {{
    background-color: {accent_dim};
    border-color: {accent_dim};
}}
QPushButton#Primary:disabled {{
    background-color: {accent_dim};
    border-color: {accent_dim};
    color: {text_dim};
}}

QPushButton#Danger {{
    background-color: transparent;
    border: 1px solid {err};
    color: {err};
}}
QPushButton#Danger:hover {{
    background-color: {err};
    color: {bg_deep};
}}

/* ─── Pipeline status chips ────────────────────────────────────────── */
#StageChip {{
    background-color: {bg_raised};
    border: 1px solid {border};
    border-radius: 999px;
    padding: 6px 12px;
    color: {text_dim};
    font-size: 12px;
}}
#StageChip[state="running"] {{
    border-color: {accent};
    color: {accent};
    background-color: {accent_bg};
}}
#StageChip[state="done"] {{
    border-color: {ok};
    color: {ok};
}}
#StageChip[state="failed"] {{
    border-color: {err};
    color: {err};
}}

/* ─── Tables & lists ───────────────────────────────────────────────── */
QTableView, QTableWidget {{
    background-color: {bg_raised};
    alternate-background-color: {bg_hover};
    gridline-color: {border};
    border: 1px solid {border};
    border-radius: 8px;
    selection-background-color: {accent_bg};
    selection-color: {accent};
}}
QHeaderView::section {{
    background-color: {bg_deep};
    color: {text_dim};
    border: none;
    border-bottom: 1px solid {border};
    padding: 8px 10px;
    font-weight: 600;
    letter-spacing: 0.4px;
    text-transform: uppercase;
    font-size: 11px;
}}
QListWidget {{
    background-color: {bg_raised};
    border: 1px solid {border};
    border-radius: 8px;
}}
QListWidget::item {{
    padding: 9px 12px;
    border-bottom: 1px solid {border};
}}
QListWidget::item:hover {{ background-color: {bg_hover}; }}
QListWidget::item:selected {{
    background-color: {accent_bg};
    color: {accent};
}}

/* ─── Tabs ─────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {border};
    border-radius: 8px;
    top: -1px;
    background-color: {bg_raised};
}}
QTabBar::tab {{
    background-color: transparent;
    color: {text_dim};
    padding: 8px 16px;
    border: 1px solid transparent;
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
}}
QTabBar::tab:selected {{
    background-color: {bg_raised};
    color: {accent};
    border: 1px solid {border};
    border-bottom: none;
}}
QTabBar::tab:hover:!selected {{ color: {text}; }}

/* ─── Scrollbars ───────────────────────────────────────────────────── */
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{
    background: {border_lt};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {accent_dim}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{
    background: {border_lt};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::handle:horizontal:hover {{ background: {accent_dim}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ─── Tooltips ─────────────────────────────────────────────────────── */
QToolTip {{
    background-color: {bg_raised};
    border: 1px solid {accent};
    color: {text};
    padding: 6px 10px;
    border-radius: 6px;
}}

/* ─── Toast / progress / misc ──────────────────────────────────────── */
#Toast {{
    background-color: {err};
    color: {bg_deep};
    border-radius: 8px;
    padding: 10px 14px;
    font-weight: 600;
}}

QProgressBar#BusyBar {{
    background-color: {bg_hover};
    border: none;
    border-radius: 3px;
}}
QProgressBar#BusyBar::chunk {{
    background-color: {accent};
    border-radius: 3px;
}}

/* Splash-screen styling — used by the startup loading window. */
#SplashRoot {{
    background-color: {bg_deep};
    border: 1px solid {border_lt};
    border-radius: 14px;
}}
#SplashBrand {{
    color: {text};
    font-size: 38px;
    font-weight: 700;
    letter-spacing: 4px;
    background-color: transparent;
}}
#SplashAccent {{
    color: {accent};
    font-size: 38px;
    font-weight: 700;
    letter-spacing: 4px;
    background-color: transparent;
}}
#SplashKicker {{
    color: {accent2};
    font-size: 10px;
    letter-spacing: 6px;
    font-weight: 600;
    background-color: transparent;
}}
#SplashStatus {{
    color: {text_dim};
    font-size: 11px;
    letter-spacing: 1px;
    background-color: transparent;
}}
#SplashTagline {{
    color: {text_dim};
    font-size: 11px;
    background-color: transparent;
}}
QProgressBar#SplashProgress {{
    background-color: {bg_raised};
    border: none;
    border-radius: 2px;
    max-height: 4px;
}}
QProgressBar#SplashProgress::chunk {{
    background-color: {accent};
    border-radius: 2px;
}}
"""


def render_qss(t: Optional[Theme] = None) -> str:
    """Render the QSS stylesheet for *t* (or the active theme)."""
    p = t or theme()
    return _QSS_TEMPLATE.format(
        bg_deep=p.bg_deep,
        bg_base=p.bg_base,
        bg_raised=p.bg_raised,
        bg_hover=p.bg_hover,
        bg_select=p.bg_select,
        bg_input=p.bg_input,
        border=p.border,
        border_lt=p.border_lt,
        accent=p.accent,
        accent_dim=p.accent_dim,
        accent_bg=p.accent_bg,
        accent2=p.accent2,
        accent2_dim=p.accent2_dim,
        ok=p.ok,
        warn=p.warn,
        err=p.err,
        err_dim=p.err_dim,
        text=p.text,
        text_dim=p.text_dim,
        text_mute=p.text_mute,
        text_mono=p.text_mono,
    )


# ── Backwards-compat shims ──────────────────────────────────────────────────
# The previous module exposed ``PALETTE`` (a plain dict) and ``DARK_QSS``
# (the rendered string). Pages still reference both — keep them resolving
# to the active theme so existing imports keep working.

class _PaletteProxy(dict):
    """Dict-like view of the active theme, refreshed on each lookup so that
    a theme switch is automatically picked up by ``PALETTE["accent"]`` reads
    in legacy call sites."""

    def __getitem__(self, key):
        t = theme()
        legacy_map = {
            "bg": t.bg_base,
            "bg_alt": t.bg_raised,
            "panel": t.bg_raised,
            "panel_2": t.bg_hover,
            "text_muted": t.text_dim,
        }
        if key in legacy_map:
            return legacy_map[key]
        return getattr(t, key)

    def __contains__(self, key) -> bool:
        try:
            self.__getitem__(key)
            return True
        except (AttributeError, KeyError):
            return False

    def get(self, key, default=None):
        try:
            return self.__getitem__(key)
        except (AttributeError, KeyError):
            return default


PALETTE = _PaletteProxy()


def _dark_qss() -> str:
    """Resolve the rendered QSS lazily so a theme switch is reflected in
    callers that re-import ``DARK_QSS`` at runtime."""
    return render_qss()


# Concrete string for callers that grab DARK_QSS at import time (e.g. app.py).
DARK_QSS = render_qss()
