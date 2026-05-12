"""Research view — live agent pipeline + streaming logs + report panel.

The query input lives in the persistent global bar at app level. This view
exposes a `run_query(text)` method that the app's submit handler calls. Mode
and effort selectors live in a small toolbar at the top of the view.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from rich.markdown import Markdown
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import RichLog, Select, Static

from researchhq.config import settings
from researchhq.effort import DEFAULT_EFFORT
from researchhq.events import PipelineEvent
from researchhq.pipeline import run as pipeline_run
from researchhq.reports.exporter import save as save_report
from researchhq.tui.widgets.agent_pipeline import AgentPipeline
from researchhq.tui.widgets.effort_selector import EffortChanged, EffortSelector


MODE_CHOICES = [
    ("topic",      "topic"),
    ("company",    "company"),
    ("competitor", "competitor"),
    ("technology", "tech"),
    ("market",     "market"),
    ("news",       "news"),
    ("academic",   "academic"),
]


class RunCompleted(Message):
    def __init__(self, ok: bool, message: str) -> None:
        super().__init__()
        self.ok = ok
        self.message = message


_EMPTY_REPORT = (
    "[dim italic]No report yet.[/]\n\n"
    "[dim]Type a query in the bar at the bottom (or press [bold]Ctrl+/[/]) "
    "and hit [bold]Enter[/] to start a research run. Findings, citations, and "
    "the full markdown report will stream into this panel as the agents complete.[/]"
)


class _ReportPane(Container):
    def compose(self):
        yield Static(_EMPTY_REPORT, id="report_view")

    def render_sections(self, sections, header_query: str) -> None:
        body = f"# {header_query}\n\n"
        for sec in sections:
            body += f"## {sec.heading}\n\n{sec.body}\n\n"
        view = self.query_one("#report_view", Static)
        view.update(Markdown(body, code_theme="monokai"))

    def reset_placeholder(self, message: str | None = None) -> None:
        self.query_one("#report_view", Static).update(message or _EMPTY_REPORT)


class ResearchView(Container):
    """Live research workflow — driven by the app-level global query bar."""

    BINDINGS = [
        ("escape", "cancel_run", "cancel"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._effort = DEFAULT_EFFORT
        self._mode = "topic"
        self._cancel_flag = False
        self._worker_task: Optional[asyncio.Task] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="research_top"):
            with Horizontal(classes="toolbar"):
                yield Select(options=MODE_CHOICES, value="topic",
                             id="mode_select", allow_blank=False)
                yield EffortSelector(current=self._effort, id="effort_selector")
            yield AgentPipeline()
        with Horizontal(id="research_bottom", classes="research_split"):
            with Vertical(id="log_card", classes="scroll_card"):
                yield Static("LIVE LOG", classes="card_title")
                yield RichLog(id="log_console", wrap=True, markup=True, highlight=False)
            with Vertical(id="report_card", classes="scroll_card"):
                yield Static("REPORT", classes="card_title")
                yield _ReportPane(id="report_pane")

    def on_mount(self) -> None:
        self._log("[dim]ready · pick mode/effort, then type a query in the bar below.[/]")

    # --- public API for the app shell ---------------------------------------

    def run_query(self, query: str) -> None:
        """Called by the global query bar (or programmatically) to launch a run."""
        self._launch(query)

    # --- key actions ---------------------------------------------------------

    def action_cancel_run(self) -> None:
        if self._worker_task and not self._worker_task.done():
            self._cancel_flag = True
            self._log("[#fbbf24]⏹  cancel requested — stopping at next stage boundary[/]")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "mode_select" and event.value:
            self._mode = str(event.value)

    def on_effort_changed(self, message: EffortChanged) -> None:
        self._effort = message.value
        self._log(f"[dim]effort → [bold]{self._effort}[/][/]")
        try:
            self.app.query_one("#header_bar").effort = self._effort  # type: ignore[attr-defined]
        except Exception:
            pass

    # --- run lifecycle -------------------------------------------------------

    def _launch(self, query: str) -> None:
        query = (query or "").strip()
        if not query:
            self._log("[#f87171]empty query — type something first[/]")
            return
        if self._worker_task and not self._worker_task.done():
            self._log("[#fbbf24]a run is already in progress — Esc to cancel[/]")
            return
        self._cancel_flag = False
        self.query_one(AgentPipeline).reset()
        self.query_one(_ReportPane).reset_placeholder("[dim italic]planning queries…[/]")
        self._log(
            f"[#34d4bb]▶  start[/] [bold]{self._mode}[/]  ·  effort=[bold]{self._effort}[/]  ·  {query}"
        )

        try:
            header = self.app.query_one("#header_bar")  # type: ignore[assignment]
            header.start_run()
            header.active_agent = "starting"
            header.tokens_in = 0
            header.tokens_out = 0
            header.cost_usd = 0.0
        except Exception:
            pass

        self._worker_task = asyncio.create_task(self._run_pipeline(self._mode, query, self._effort))

    async def _run_pipeline(self, mode: str, query: str, effort: str) -> None:
        try:
            report = await pipeline_run(
                mode, query,
                on_event=self._on_event,
                cancel_check=lambda: self._cancel_flag,
                effort=effort,
            )
        except asyncio.CancelledError:
            self.post_message(RunCompleted(ok=False, message="run cancelled"))
            return
        except Exception as e:  # noqa: BLE001
            self.post_message(RunCompleted(ok=False, message=f"run failed: {e}"))
            return
        try:
            self.query_one(_ReportPane).render_sections(report.sections, header_query=query)
        except Exception:
            pass
        try:
            path = save_report(report, fmt=settings.default_format)
            msg = f"saved to {path}"
        except Exception as e:  # noqa: BLE001
            msg = f"saved failed: {e}"
        self.post_message(RunCompleted(ok=True, message=msg))

    def on_run_completed(self, message: RunCompleted) -> None:
        try:
            header = self.app.query_one("#header_bar")  # type: ignore[assignment]
            header.stop_run()
            header.active_agent = "idle"
        except Exception:
            pass
        if message.ok:
            self._log(f"[#4ade80]✓  done[/]  ·  {message.message}")
            try:
                self.app.notify(f"Research completed — {message.message}", severity="information")
            except Exception:
                pass
        else:
            self._log(f"[#f87171]✗  {message.message}[/]")
            try:
                self.app.notify(message.message, severity="error")
            except Exception:
                pass

    def _on_event(self, ev: PipelineEvent) -> None:
        try:
            self.query_one(AgentPipeline).on_pipeline_event(
                type_=ev.type, stage=ev.stage, detail=ev.detail, data=ev.data
            )
        except Exception:
            pass
        try:
            header = self.app.query_one("#header_bar")  # type: ignore[assignment]
            if ev.type == "agent_started":
                header.active_agent = ev.stage
            if ev.type == "llm_call_finished":
                header.tokens_in += int(ev.data.get("input_tokens", 0))
                header.tokens_out += int(ev.data.get("output_tokens", 0))
                header.cost_usd += float(ev.data.get("equivalent_cost_usd", 0))
        except Exception:
            pass
        if ev.type == "run_started":
            self._log(f"[dim]· planning…[/]")
        elif ev.type == "agent_started":
            self._log(f"  [#34d4bb]▸[/] {ev.stage}  [dim]{ev.detail}[/]")
        elif ev.type == "agent_finished":
            self._log(f"  [#4ade80]✓[/] {ev.stage}  [dim]{ev.detail}[/]")
        elif ev.type == "source_found":
            url = ev.data.get("url", "")
            self._log(f"     [dim]+ {url}[/]")
        elif ev.type == "report_section_ready":
            heading = ev.data.get("heading", "?")
            self._log(f"  [#7c5cff]§[/] {heading}")
        elif ev.type == "llm_call_finished":
            stage = ev.data.get("stage_tag", ev.stage)
            cost = ev.data.get("equivalent_cost_usd", 0)
            tin = ev.data.get("input_tokens", 0); tout = ev.data.get("output_tokens", 0)
            self._log(f"     [dim]llm {stage}: {tin}↑ {tout}↓  ${cost:.4f}[/]")
        elif ev.type == "run_completed":
            elapsed = ev.data.get("elapsed_s", 0.0)
            conf = ev.data.get("confidence", 0)
            self._log(f"[#4ade80]●  run completed[/]  · {elapsed}s  · conf {conf:.2f}")

    def _log(self, message: str) -> None:
        try:
            log = self.query_one("#log_console", RichLog)
            log.write(Text.from_markup(message))
        except Exception:
            pass
