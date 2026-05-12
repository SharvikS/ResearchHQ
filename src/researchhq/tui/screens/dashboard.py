"""Startup dashboard — wordmark + provider status, recent reports, quick
actions, tips. Pure read view; mutations happen on the Research screen.
"""

from __future__ import annotations

from datetime import datetime

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import Static

from researchhq.config import settings
from researchhq.history import list_runs
from researchhq.llm.cost_tracker import tracker
from researchhq.tui.widgets.logo import ResponsiveWordmark


class _Card(Container):
    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(classes="card", **kwargs)
        self._title = title

    def compose(self):
        yield Static(self._title, classes="card_title")


class ProviderCard(_Card):
    def __init__(self) -> None:
        super().__init__("PROVIDERS", id="card_providers")

    def compose(self):
        yield from super().compose()
        rows = [
            ("groq",      bool(settings.groq_api_key),      settings.models.get("groq", "")),
            ("gemini",    bool(settings.gemini_api_key),    settings.models.get("gemini", "")),
            ("openai",    bool(settings.openai_api_key),    settings.models.get("openai", "")),
            ("anthropic", bool(settings.anthropic_api_key), settings.models.get("anthropic", "")),
            ("ollama",    True,                              settings.models.get("ollama", "")),
        ]
        t = Table.grid(padding=(0, 2))
        t.add_column(justify="left", no_wrap=True)
        t.add_column(justify="left")
        t.add_column(justify="left")
        for name, ready, model in rows:
            mark = "[#4ade80]●[/]" if ready else "[#5a6573]○[/]"
            label = Text(name, style="bold")
            t.add_row(mark, label, Text(model or "—", style="dim"))
        yield Static(t)


class RecentReportsCard(_Card):
    def __init__(self) -> None:
        super().__init__("RECENT REPORTS", id="card_recent")

    def compose(self):
        yield from super().compose()
        try:
            rows = list_runs(limit=6)
        except Exception:
            rows = []
        if not rows:
            yield Static("[dim]No reports yet — start one with [bold]/research[/bold] or [bold]Ctrl+R[/].[/]")
            return
        t = Table.grid(padding=(0, 1))
        t.add_column(no_wrap=True)
        t.add_column()
        t.add_column(justify="right", no_wrap=True)
        for r in rows:
            when = _fmt_when(r.generated_at)
            mode = (r.mode or "?")[:10]
            query = (r.query or "")[:48]
            t.add_row(
                Text(when, style="dim"),
                Text(f"[{mode}] {query}"),
                Text(f"conf {float(r.confidence or 0):.2f}", style="dim"),
            )
        yield Static(t)


class QuickActionsCard(_Card):
    def __init__(self) -> None:
        super().__init__("QUICK ACTIONS", id="card_actions")

    def compose(self):
        yield from super().compose()
        items = [
            ("Ctrl+R", "Start a new research run"),
            ("Ctrl+K", "Open the command palette"),
            ("Ctrl+T", "Cycle theme"),
            ("Ctrl+H", "Browse report history"),
            ("Ctrl+,", "Open settings"),
            ("Ctrl+Q", "Quit"),
        ]
        t = Table.grid(padding=(0, 2))
        t.add_column(no_wrap=True)
        t.add_column()
        for key, label in items:
            t.add_row(Text(key, style="bold #34d4bb"), Text(label))
        yield Static(t)


class TipsCard(_Card):
    def __init__(self) -> None:
        super().__init__("TIPS", id="card_tips")

    def compose(self):
        yield from super().compose()
        yield Static(
            "[dim]·[/] Type a query in the bar at the bottom and press [bold]Enter[/]\n"
            "[dim]·[/] [bold]Ctrl+/[/] focuses the query bar from anywhere\n"
            "[dim]·[/] [bold]high[/] effort uses ~3× tokens — best for deep dives\n"
            "[dim]·[/] Mode and effort live on the [bold]Research[/] tab — change them before running\n"
            "[dim]·[/] Reports auto-save to [italic]reports/[/italic] in markdown"
        )


class UsageCard(_Card):
    def __init__(self) -> None:
        super().__init__("THIS SESSION", id="card_usage")

    def compose(self):
        yield from super().compose()
        records = tracker.records
        calls = len(records)
        in_tok = sum(r.input_tokens for r in records)
        out_tok = sum(r.output_tokens for r in records)
        cost = sum(r.equivalent_cost_usd for r in records)
        t = Table.grid(padding=(0, 3))
        t.add_column(); t.add_column(justify="right")
        t.add_row(Text("LLM calls", style="dim"),     Text(str(calls), style="bold"))
        t.add_row(Text("input tokens", style="dim"),  Text(f"{in_tok:,}"))
        t.add_row(Text("output tokens", style="dim"), Text(f"{out_tok:,}"))
        t.add_row(Text("equiv cost", style="dim"),    Text(f"${cost:.4f}"))
        yield Static(t)


class ActivityFeedCard(_Card):
    """Lightweight feed of app-lifecycle events. Read from app._activity_log
    if available; otherwise synthesize a small set from current state."""

    def __init__(self) -> None:
        super().__init__("ACTIVITY FEED", id="card_activity")

    def compose(self):
        yield from super().compose()
        events: list[tuple[str, str]] = []
        try:
            events = list(getattr(self.app, "_activity_log", []) or [])
        except Exception:
            events = []
        if not events:
            now = datetime.now().strftime("%H:%M")
            ws = getattr(self.app, "_workspace", "default")
            events = [
                (now, "Dashboard loaded"),
                (now, f'Workspace "{ws}" activated'),
                (now, f"Provider {settings.default_provider} ready"),
                (now, "ResearchHQ started"),
            ]
        # Render newest-last for natural reading order
        t = Table.grid(padding=(0, 2))
        t.add_column(no_wrap=True, style="dim", width=6)
        t.add_column()
        for when, msg in events[-6:]:
            t.add_row(Text(when), Text(msg))
        yield Static(t)


class DashboardView(Container):
    """Two-column dashboard: wordmark + tips on the left, status cards right.

    Lives inside the ContentSwitcher (not a Screen), so the persistent shell
    (sidebar, header, global query bar) stays visible.
    """

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="dashboard_scroll"):
            yield ResponsiveWordmark(theme_name=getattr(self.app, "_theme_name", "default"))
            with Horizontal(id="dashboard_grid"):
                with Vertical(classes="dash_col"):
                    yield RecentReportsCard()
                    yield TipsCard()
                    yield UsageCard()
                with Vertical(classes="dash_col"):
                    yield ProviderCard()
                    yield QuickActionsCard()
                    yield ActivityFeedCard()


def _fmt_when(iso: str) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%m-%d %H:%M")
    except Exception:
        return iso[:16]
