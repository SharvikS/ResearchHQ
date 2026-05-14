"""Left-rail navigation. Keyboard-driven; emits NavRequest on selection."""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Button, Static

# ── Nav sections ──────────────────────────────────────────────────────
# (target, label, number_key, icon)
SECTIONS = [
    ("dashboard", "Dashboard", "1", "◈"),
    ("research",  "Research",  "2", "⌖"),
    ("reports",   "Reports",   "3", "⊞"),
    ("settings",  "Settings",  "4", "◎"),
]

SHORTCUTS = [
    ("ctrl+/",  "Query"),
    ("ctrl+r",  "Research"),
    ("ctrl+h",  "History"),
    ("ctrl+,",  "Settings"),
    ("ctrl+t",  "Theme"),
    ("ctrl+q",  "Quit"),
]


# ── Messages ──────────────────────────────────────────────────────────

@dataclass
class NavRequest(Message):
    target: str


# ── Sidebar widget ────────────────────────────────────────────────────

class Sidebar(Widget):
    DEFAULT_ID = "sidebar"

    def compose(self) -> ComposeResult:
        yield Static("  WORKSPACE", classes="sidebar_section")
        for target, label, key, icon in SECTIONS:
            yield Button(
                f"  {icon}  {label}",
                id=f"nav_{target}",
            )

        yield Static("  SHORTCUTS", classes="sidebar_section")
        for keys, action in SHORTCUTS:
            yield Static(
                f"  [dim]{keys:<10}[/dim]  [dim]{action}[/dim]",
                classes="kv_label sidebar_hint",
            )

    def set_active(self, target: str) -> None:
        for t, _, _, _ in SECTIONS:
            btn = self.query_one(f"#nav_{t}", Button)
            if t == target:
                btn.add_class("-active")
            else:
                btn.remove_class("-active")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn_id = event.button.id or ""
        if btn_id.startswith("nav_"):
            target = btn_id[4:]
            self.set_active(target)
            self.post_message(NavRequest(target=target))
