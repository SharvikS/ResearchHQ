"""Status header — provider · model · workspace · effort · runtime · tokens.

Reactive: any pipeline event updates the relevant cell. Single line. On
narrow terminals (<110 cols) the low-priority cells (cost, tokens) drop out
so the high-signal cells stay readable. Provider/model are truncated with
an ellipsis if they would otherwise force wrapping.
"""

from __future__ import annotations

import time

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from researchhq.tui.theme import get_palette


def _ellipsize(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    if limit <= 1:
        return value[:limit]
    return value[: limit - 1] + "…"


class StatusHeader(Static):
    """Single-line top status bar."""

    provider: reactive[str] = reactive("groq")
    model: reactive[str] = reactive("llama-3.3-70b")
    workspace: reactive[str] = reactive("default")
    effort: reactive[str] = reactive("medium")
    active_agent: reactive[str] = reactive("idle")
    tokens_in: reactive[int] = reactive(0)
    tokens_out: reactive[int] = reactive(0)
    cost_usd: reactive[float] = reactive(0.0)
    runtime_s: reactive[float] = reactive(0.0)

    def __init__(self, theme_name: str = "default", **kwargs) -> None:
        kwargs.setdefault("id", "header_bar")
        super().__init__("ResearchHQ HQ", **kwargs)
        self._theme_name = theme_name
        self._run_started_at: float | None = None
        self._available_width: int = 120

    def watch_provider(self) -> None: self._refresh()
    def watch_model(self) -> None: self._refresh()
    def watch_workspace(self) -> None: self._refresh()
    def watch_effort(self) -> None: self._refresh()
    def watch_active_agent(self) -> None: self._refresh()
    def watch_tokens_in(self) -> None: self._refresh()
    def watch_tokens_out(self) -> None: self._refresh()
    def watch_cost_usd(self) -> None: self._refresh()
    def watch_runtime_s(self) -> None: self._refresh()

    def on_mount(self) -> None:
        self._refresh()
        self.set_interval(1.0, self._tick)

    def start_run(self) -> None:
        self._run_started_at = time.monotonic()

    def stop_run(self) -> None:
        self._run_started_at = None

    def _tick(self) -> None:
        if self._run_started_at is not None:
            self.runtime_s = round(time.monotonic() - self._run_started_at, 1)

    def on_resize(self, event) -> None:
        self._available_width = event.size.width
        self._refresh()

    def _refresh(self) -> None:
        p = get_palette(self._theme_name)
        sep = Text("  ·  ", style=p.text_mute)

        # Width budget — provider/model truncate to fit the cell, low-priority
        # cells drop entirely on narrow terminals.
        w = self._available_width
        show_tokens = w >= 110
        show_cost = w >= 130
        show_workspace = w >= 90
        provider_limit = 18 if w < 100 else 28
        provider_value = _ellipsize(f"{self.provider}/{self.model}", provider_limit)

        # Brand: "Research" in teal/accent + "HQ" in purple/accent_2.
        line = Text("Research", style=f"bold {p.accent}")
        line.append("HQ", style=f"bold {p.accent_2}")
        line.append(sep)
        line.append(self._kv(p, "provider", provider_value))
        if show_workspace:
            line.append(sep)
            line.append(self._kv(p, "ws", _ellipsize(self.workspace, 14)))
        line.append(sep)
        line.append(self._kv(p, "effort", self.effort))
        line.append(sep)
        line.append(self._kv(p, "agent", _ellipsize(self.active_agent, 14)))
        if show_tokens:
            line.append(sep)
            line.append(self._kv(p, "tokens", f"{self.tokens_in}↑ {self.tokens_out}↓"))
        if show_cost:
            line.append(sep)
            line.append(self._kv(p, "cost", f"${self.cost_usd:.4f}"))
        line.append(sep)
        line.append(self._kv(p, "runtime", f"{self.runtime_s:.1f}s"))
        line.no_wrap = True
        line.overflow = "ellipsis"
        self.update(line)

    @staticmethod
    def _kv(p, label: str, value: str) -> Text:
        t = Text()
        t.append(f"{label} ", style=p.text_mute)
        t.append(value, style=p.text)
        return t
