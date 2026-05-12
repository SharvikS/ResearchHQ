"""Left-rail navigation. Keyboard-driven; emits NavRequest on selection."""

from __future__ import annotations

from dataclasses import dataclass

from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Button, Static


SECTIONS = [
    ("dashboard", "Dashboard", "1"),
    ("research", "Research",  "2"),
    ("reports",  "Reports",   "3"),
    ("settings", "Settings",  "4"),
]


@dataclass
class NavRequest(Message):
    target: str


class Sidebar(Vertical):
    DEFAULT_ID = "sidebar"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("id", "sidebar")
        super().__init__(**kwargs)
        self._active = "dashboard"

    def compose(self):
        # Every row encodes its OWN leading whitespace (2 chars) directly in
        # the text so alignment is independent of any per-widget-type default
        # padding (Button vs Static can disagree). CSS contributes zero
        # horizontal padding on these widgets.
        yield Static("  WORKSPACE", classes="sidebar_section")
        for key, label, hot in SECTIONS:
            btn = Button(f"  {hot}  {label}", id=f"nav_{key}")
            if key == self._active:
                btn.add_class("-active")
            yield btn
        yield Static("  SHORTCUTS", classes="sidebar_section")
        for key, label in (
            ("ctrl+/",  "Query"),
            ("ctrl+r",  "Research"),
            ("ctrl+h",  "History"),
            ("ctrl+,",  "Settings"),
            ("ctrl+t",  "Theme"),
            ("ctrl+q",  "Quit"),
        ):
            yield Static(f"  {key:<7} {label}", classes="kv_label sidebar_hint")

    def set_active(self, target: str) -> None:
        self._active = target
        for key, _label, _hot in SECTIONS:
            try:
                btn = self.query_one(f"#nav_{key}", Button)
            except Exception:
                continue
            if key == target:
                btn.add_class("-active")
            else:
                btn.remove_class("-active")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("nav_"):
            target = event.button.id[len("nav_"):]
            self.set_active(target)
            self.post_message(NavRequest(target=target))
