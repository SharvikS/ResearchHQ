"""Reports browser — Phase 1: scrollable, search-filterable list.

Phase 2 will add: open, compare, pin/favorite, export. For now, this is a
read-only listing so users can confirm runs were saved correctly.
"""

from __future__ import annotations

from rich.table import Table
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Vertical, VerticalScroll
from textual.widgets import Input, Static

from researchhq.history import list_runs


class ReportsView(Container):
    def compose(self) -> ComposeResult:
        with Container(classes="card", id="reports_filter_card"):
            yield Static("REPORT HISTORY", classes="card_title")
            yield Input(placeholder="Filter by query, mode, or provider…", id="reports_filter")
        with VerticalScroll(id="reports_scroll"):
            yield Static("", id="reports_table_holder")

    def on_mount(self) -> None:
        self._refresh("")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "reports_filter":
            self._refresh(event.value)

    def _refresh(self, text: str) -> None:
        try:
            rows = list_runs(text=text or None, limit=200)
        except Exception:
            rows = []
        if not rows:
            self.query_one("#reports_table_holder", Static).update(
                "[dim italic]No reports match — adjust the filter or run new research.[/]"
            )
            return
        t = Table(show_header=True, header_style="bold #34d4bb",
                  show_edge=False, expand=True, pad_edge=False)
        t.add_column("when",   no_wrap=True, style="dim", width=14)
        t.add_column("mode",   no_wrap=True, width=10)
        t.add_column("query",  ratio=4)
        t.add_column("conf",   no_wrap=True, justify="right", width=6)
        t.add_column("cost",   no_wrap=True, justify="right", width=9)
        t.add_column("toks",   no_wrap=True, justify="right", width=12)
        for r in rows:
            t.add_row(
                r.generated_at[:16] if r.generated_at else "",
                r.mode or "",
                r.query or "",
                f"{float(r.confidence or 0):.2f}",
                f"${r.equivalent_cost_usd:.4f}",
                f"{r.input_tokens}↑ {r.output_tokens}↓",
            )
        self.query_one("#reports_table_holder", Static).update(t)
