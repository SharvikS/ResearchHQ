"""ResearchHQ CLI — premium terminal interface.

Entry points
  research-hq              interactive mode (menu-driven)
  research-hq query "…"   direct query with live pipeline display
  research-hq history      paginated run history table
  research-hq agents       configured provider chain
  research-hq settings     show / set configuration values
  research-hq config       raw config file inspection
  research-hq doctor       full health-check suite
  research-hq setup        first-time API key wizard
  research-hq models       list models per provider
  research-hq test-models  send a probe request to every provider
  research-hq export       export saved reports
  research-hq logs         tail the application log
  research-hq clear-history delete all history records
  research-hq reset-config  restore config.yaml to defaults

  research <mode> "…"      legacy mode subcommands (backward-compat)
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import typer
from rich import box
from rich.align import Align
from rich.columns import Columns
from rich.console import Console, Group
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.rule import Rule
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

# ── Constants ─────────────────────────────────────────────────────────
_VERSION = "2.1.0"

_STAGE_ORDER = [
    "planner", "searcher", "source_ranker", "fetcher",
    "extractor", "synthesizer", "verifier", "formatter",
]
_STAGE_COLOR: dict[str, str] = {
    "planner": "cyan",        "searcher": "blue",
    "source_ranker": "magenta", "fetcher": "yellow",
    "extractor": "bright_yellow", "synthesizer": "green",
    "verifier": "bright_blue", "formatter": "bright_magenta",
}
_STAGE_ICON: dict[str, str] = {
    "planner": "◈", "searcher": "⌖", "source_ranker": "⊞",
    "fetcher": "⬇", "extractor": "⚗", "synthesizer": "⬡",
    "verifier": "◉", "formatter": "◎",
}

_VALID_MODES = ("cheap", "balanced", "max_confidence")
_VALID_EFFORTS = ("low", "medium", "high")
_VALID_FORMATS = ("markdown", "json", "html")

# ── Console ───────────────────────────────────────────────────────────
console = Console(highlight=False)

# ── Apps ─────────────────────────────────────────────────────────────
app = typer.Typer(
    name="research-hq",
    help="[bold]ResearchHQ[/bold] — multi-agent AI research platform",
    rich_markup_mode="rich",
    no_args_is_help=False,
    add_completion=False,
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
)

# Legacy research-mode subgroup (research topic|company|…)
research_app = typer.Typer(
    help="[dim]Legacy mode subcommands — research topic|company|tech|…[/dim]",
    rich_markup_mode="rich",
    no_args_is_help=True,
    add_completion=False,
)
app.add_typer(research_app, name="research")


# ── Rendering helpers ─────────────────────────────────────────────────

def _print_logo() -> None:
    t = Text()
    t.append("ResearchHQ", style="bold white")
    t.append(f"  v{_VERSION}", style="dim")
    t.append("\nMulti-agent AI research platform", style="dim")
    console.print(Panel(Align.center(t), border_style="bright_blue", padding=(0, 6)))


def _conf_bar(score: float, width: int = 14) -> Text:
    filled = round(score * width)
    color = "green" if score >= 0.75 else "yellow" if score >= 0.5 else "red"
    label = "High" if score >= 0.75 else "Medium" if score >= 0.5 else "Low"
    t = Text()
    t.append("█" * filled + "░" * (width - filled), style=color)
    t.append(f"  {score * 100:.0f}%", style=f"bold {color}")
    t.append(f"  {label}", style=f"dim {color}")
    return t


def _status_badge(status: str) -> Text:
    palette = {
        "ok": ("green", "✓"),
        "done": ("green", "✓"),
        "failed": ("red", "✗"),
        "warn": ("yellow", "⚠"),
        "running": ("cyan", "⟳"),
        "pending": ("dim", "○"),
    }
    color, icon = palette.get(status, ("dim", "·"))
    t = Text()
    t.append(f" {icon} ", style=f"bold {color}")
    return t


def _time_ago(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        secs = int((datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds())
        if secs < 60:  return "just now"
        if secs < 3600:  return f"{secs // 60}m ago"
        if secs < 86400: return f"{secs // 3600}h ago"
        return f"{secs // 86400}d ago"
    except Exception:  # noqa: BLE001
        return iso[:10] if len(iso) >= 10 else iso


def _format_report_cost(report) -> str:
    costs = getattr(report, "stage_costs", None) or []
    total = sum(float(getattr(c, "equivalent_paid_cost_usd", 0)) for c in costs)
    tokens = sum(
        int(getattr(c, "input_tokens", 0)) + int(getattr(c, "output_tokens", 0))
        for c in costs
    )
    parts = []
    if total > 0:
        parts.append(f"${total:.4f}")
    if tokens > 0:
        parts.append(f"{tokens:,} tokens")
    return "  ·  ".join(parts) if parts else "—"


# ── Live Pipeline Display ─────────────────────────────────────────────

class PipelineDisplay:
    """Builds a Rich renderable that reflects live pipeline event state."""

    def __init__(self, query: str, mode: str, effort: str, ensemble: bool) -> None:
        self.query = query
        self.mode = mode
        self.effort = effort
        self.ensemble = ensemble
        self.started_at = time.monotonic()
        self._stage_started: dict[str, float] = {}
        self._stages: dict[str, dict] = {}       # stage → {status, detail, elapsed}
        self._ens_providers: list[dict] = []      # [{provider, status}]

    def handle(self, ev) -> None:
        t   = getattr(ev, "type", "") or ""
        stg = getattr(ev, "stage", "") or ""
        det = getattr(ev, "detail", "") or ""
        dat = getattr(ev, "data", {}) or {}

        if t == "agent_started":
            self._stage_started[stg] = time.monotonic()
            self._stages[stg] = {"status": "running", "detail": "…", "elapsed": None}
        elif t == "agent_progress":
            self._stages.setdefault(stg, {"status": "running", "detail": "", "elapsed": None})
            self._stages[stg]["detail"] = det
            self._stage_started.setdefault(stg, time.monotonic())
        elif t == "agent_finished":
            el = time.monotonic() - self._stage_started.get(stg, self.started_at)
            self._stages[stg] = {"status": "done", "detail": det, "elapsed": el}
        elif t == "agent_failed":
            el = time.monotonic() - self._stage_started.get(stg, self.started_at)
            self._stages[stg] = {"status": "failed", "detail": det or "failed", "elapsed": el}
        elif t == "ensemble_provider_finished":
            self._ens_providers.append({
                "provider": dat.get("provider", "?"),
                "status": dat.get("status", "done"),
            })

    def render(self) -> Panel:
        elapsed = time.monotonic() - self.started_at

        # ── top info row ──────────────────────────────────────────────
        q_text = self.query[:72] + ("…" if len(self.query) > 72 else "")
        meta = Text()
        meta.append(f"  {self.mode}", style="cyan")
        meta.append("  ·  ", style="dim")
        meta.append(f"effort {self.effort}", style="dim")
        if self.ensemble:
            meta.append("  ·  ensemble", style="dim violet")

        # ── stage table ───────────────────────────────────────────────
        tbl = Table(box=None, show_header=False, padding=(0, 1), expand=True)
        tbl.add_column(width=2, no_wrap=True)   # icon
        tbl.add_column(width=15, no_wrap=True)  # name
        tbl.add_column(ratio=1)                 # detail
        tbl.add_column(width=6, justify="right", no_wrap=True)  # elapsed

        ordered = [s for s in _STAGE_ORDER if s in self._stages or s in self._stage_started]
        extras  = [s for s in self._stages if s not in _STAGE_ORDER]
        for stg in ordered + extras:
            info = self._stages.get(stg)
            if info is None:
                info = {"status": "running", "detail": "…", "elapsed": None}

            status  = info["status"]
            detail  = info.get("detail", "")
            elapsed_s = info.get("elapsed")
            col = _STAGE_COLOR.get(stg, "white")

            if status == "done":
                icon_t = Text(_STAGE_ICON.get(stg, "✓"), style="green")
                ns = "dim"; ds = "dim"
            elif status == "failed":
                icon_t = Text("✗", style="red")
                ns = "red"; ds = "red"
            elif status == "running":
                icon_t = Text("⟳", style=f"bold {col}")
                ns = f"bold {col}"; ds = col
            else:
                icon_t = Text("○", style="dim")
                ns = "dim"; ds = "dim"

            elapsed_str = f"{elapsed_s:.1f}s" if elapsed_s is not None else ""
            tbl.add_row(icon_t, Text(stg, style=ns),
                        Text((detail or "")[:64], style=ds),
                        Text(elapsed_str, style="dim"))

            # Ensemble provider sub-rows under synthesizer
            if stg == "synthesizer" and self._ens_providers:
                total_ep = len(self._ens_providers)
                for i, ep in enumerate(self._ens_providers):
                    corner = "└─" if i == total_ep - 1 else "├─"
                    ep_status = ep["status"]
                    ep_ok = "done" in ep_status or ep_status == "success"
                    ep_icon = "✓" if ep_ok else "✗" if "fail" in ep_status else "⟳"
                    ep_sty = "dim green" if ep_ok else "dim red" if "fail" in ep_status else "dim yellow"
                    tbl.add_row(
                        Text(""), Text(f"  {corner} {ep['provider'][:13]}", style="dim"),
                        Text(ep_icon, style=ep_sty), Text(""),
                    )

        body = Group(
            Text.assemble(("Query  ", "dim"), (q_text, "bold white")),
            meta,
            Rule(style="dim"),
            tbl,
            Text(f"\n  Elapsed  {elapsed:.1f}s", style="dim"),
        )
        return Panel(body, title="[bold]Running research[/bold]", border_style="bright_blue", padding=(0, 1))


# ── Core execution (shared by query cmd + legacy research subgroup) ───

def _resolve_verbosity(quiet: bool, verbose: bool, debug: bool) -> str:
    from researchhq.config import settings as _s
    if debug:   return "debug"
    if verbose: return "verbose"
    if quiet:   return "quiet"
    return _s.verbosity_default


def _resolve_effort(value: Optional[str]) -> str:
    from researchhq.effort import DEFAULT_EFFORT, PROFILES
    key = (value or DEFAULT_EFFORT).strip().lower()
    if key not in PROFILES:
        raise typer.BadParameter(f"--effort must be one of {sorted(PROFILES)}; got '{value}'.")
    return key


def _run_query(
    *,
    mode: str,
    query: str,
    effort: str,
    fmt: Optional[str],
    quiet: bool,
    verbose: bool,
    debug: bool,
    ensemble: Optional[bool],
    ensemble_mode: Optional[str],
    live_display: bool = True,
) -> None:
    from researchhq.config import settings
    from researchhq.events import StageEvent
    from researchhq.pipeline import run
    from researchhq.reports.exporter import save
    from researchhq.utils.rich_ui import (
        render_cost, render_rules, render_stage_costs,
    )
    try:
        from researchhq.utils.logging import configure as _configure_logging
        _configure_logging(_resolve_verbosity(quiet, verbose, debug))
    except Exception:  # noqa: BLE001
        pass

    if ensemble is not None:
        settings.ensemble_enabled = ensemble
    if ensemble_mode is not None:
        if ensemble_mode not in _VALID_MODES:
            raise typer.BadParameter(f"--ensemble-mode must be one of {_VALID_MODES}; got '{ensemble_mode}'.")
        settings.ensemble_mode = ensemble_mode

    disp = PipelineDisplay(query, mode, effort, settings.ensemble_enabled)

    if live_display:
        with Live(disp.render(), console=console, refresh_per_second=8, transient=False) as live:
            def on_event(ev: StageEvent) -> None:
                disp.handle(ev)
                live.update(disp.render())
            report = asyncio.run(run(mode, query, on_event=on_event, effort=effort))
    else:
        events: list[StageEvent] = []
        def on_event(ev: StageEvent) -> None:
            events.append(ev)
        with console.status("[cyan]Researching…[/cyan]"):
            report = asyncio.run(run(mode, query, on_event=on_event, effort=effort))

    # Save report
    out_fmt = fmt or settings.default_format
    saved_path = save(report, fmt=out_fmt)

    # ── Result panel ─────────────────────────────────────────────────
    if not quiet:
        from researchhq.reports.schema import ResearchReport
        _render_result(report, saved_path)
        if verbose or debug:
            render_rules(report)
            render_stage_costs(report)
            render_cost()


def _render_result(report, saved_path: Path) -> None:
    """Render the full result to the terminal after a run completes."""
    from researchhq.reports.schema import ResearchReport

    console.print()
    console.print(Rule("[bold]Research complete[/bold]", style="bright_blue"))
    console.print()

    # Answer panel
    answer = (
        getattr(report, "answer", None)
        or getattr(report, "report", None)
        or ""
    )
    if answer:
        console.print(Panel(
            Markdown(answer[:8000] + ("\n\n*[truncated — see saved file for full output]*" if len(answer) > 8000 else "")),
            title="[bold green]Answer[/bold green]",
            border_style="green",
            padding=(1, 2),
        ))
        console.print()

    # Metadata grid
    verifier = getattr(report, "verifier", None)
    confidence = getattr(verifier, "overall_confidence", None) if verifier else None
    sources = getattr(report, "sources", []) or []
    facts   = getattr(report, "facts", []) or []
    provider = getattr(report, "provider_used", None) or "—"
    mode_used = getattr(report, "mode", "—")

    grid = Table(box=None, show_header=False, padding=(0, 3), expand=False)
    grid.add_column(style="dim", no_wrap=True)
    grid.add_column()

    grid.add_row("Mode",     f"[cyan]{mode_used}[/cyan]")
    grid.add_row("Provider", f"[white]{provider}[/white]")
    grid.add_row("Sources",  f"[white]{len(sources)}[/white]")
    grid.add_row("Facts",    f"[white]{len(facts)}[/white]")
    if confidence is not None:
        grid.add_row("Confidence", _conf_bar(confidence))
    grid.add_row("Cost",     _format_report_cost(report))
    grid.add_row("Saved to", f"[dim]{saved_path}[/dim]")

    console.print(Panel(grid, title="[bold]Run summary[/bold]", border_style="dim", padding=(0, 1)))

    # Top sources
    if sources:
        console.print()
        src_tbl = Table(title="Top sources", box=box.SIMPLE, show_edge=False, header_style="bold dim")
        src_tbl.add_column("#", width=3, style="dim")
        src_tbl.add_column("Title", ratio=2)
        src_tbl.add_column("URL", ratio=3, style="dim blue")
        src_tbl.add_column("Tier", width=8, justify="center")
        for i, s in enumerate(sources[:10], 1):
            tier = str(getattr(s, "tier", getattr(s, "tier_value", "?")))
            tier_val = tier.lower().replace("tiersource.", "").replace("tier", "")
            tier_color = {"1": "green", "2": "cyan", "3": "yellow", "primary": "green", "secondary": "cyan"}.get(tier_val, "dim")
            src_tbl.add_row(
                str(i),
                str(getattr(s, "title", ""))[:60],
                str(getattr(s, "url", ""))[:70],
                Text(tier_val, style=tier_color),
            )
        console.print(src_tbl)


# ── App callback → interactive mode ───────────────────────────────────

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """ResearchHQ — run bare for interactive mode, or use a subcommand."""
    if ctx.invoked_subcommand is not None:
        return
    _interactive_mode()


def _interactive_mode() -> None:
    """Full interactive terminal session."""
    from researchhq.config import settings
    from researchhq.effort import DEFAULT_EFFORT

    console.clear()
    _print_logo()
    console.print()

    # Quick status
    try:
        from researchhq.llm.router import LLMRouter
        providers = [p.name for p in LLMRouter().providers]
        status_line = "[green]●[/green] " + "  ".join(f"[dim]{p}[/dim]" for p in providers)
    except Exception:  # noqa: BLE001
        status_line = "[red]●[/red] [dim]No providers found — run [bold]research-hq doctor[/bold][/dim]"
    console.print(f"  Providers  {status_line}")
    console.print()

    # Mode selection
    mode_choices = ["topic", "company", "tech", "market", "news", "academic", "competitor"]
    effort_choice = DEFAULT_EFFORT

    while True:
        console.print(Rule(style="dim"))
        console.print()

        # Mode
        mode_table = Table(box=None, show_header=False, padding=(0, 2))
        mode_table.add_column(style="bold cyan", no_wrap=True)
        mode_table.add_column(style="dim")
        descriptions = {
            "topic": "General topic research",
            "company": "Company profile deep-dive",
            "tech": "Technology / framework analysis",
            "market": "Market & industry overview",
            "news": "Recent news & developments",
            "academic": "Academic paper / research",
            "competitor": "Competitor landscape scan",
        }
        for i, m in enumerate(mode_choices, 1):
            mode_table.add_row(f"[{i}] {m}", descriptions.get(m, ""))
        console.print(Panel(mode_table, title="[bold]Select mode[/bold]", border_style="dim", padding=(0, 1)))

        mode_raw = Prompt.ask(
            "\n  [bold]Mode[/bold]",
            choices=[str(i) for i in range(1, len(mode_choices) + 1)] + mode_choices,
            default="1",
            show_choices=False,
        )
        try:
            mode = mode_choices[int(mode_raw) - 1]
        except (ValueError, IndexError):
            mode = mode_raw if mode_raw in mode_choices else "topic"

        # Effort
        effort_raw = Prompt.ask(
            "  [bold]Effort[/bold] [dim](low / medium / high)[/dim]",
            choices=["low", "medium", "high"],
            default=DEFAULT_EFFORT,
            show_choices=False,
        )
        effort_choice = effort_raw if effort_raw in _VALID_EFFORTS else DEFAULT_EFFORT

        # Ensemble
        ensemble_enabled = settings.ensemble_enabled
        ens_default = "y" if ensemble_enabled else "n"
        ens_raw = Prompt.ask(
            f"  [bold]Ensemble[/bold] [dim](y/n)[/dim]",
            default=ens_default,
            show_choices=False,
        )
        ensemble_on = ens_raw.lower().strip() in ("y", "yes", "1", "true")

        # Query
        console.print()
        query = Prompt.ask("  [bold white]Query[/bold white]").strip()
        if not query:
            console.print("[dim]  Empty query — skipped.[/dim]\n")
            continue

        console.print()
        try:
            _run_query(
                mode=mode,
                query=query,
                effort=effort_choice,
                fmt=None,
                quiet=False,
                verbose=False,
                debug=False,
                ensemble=ensemble_on,
                ensemble_mode=None,
                live_display=True,
            )
        except KeyboardInterrupt:
            console.print("\n[dim]  Interrupted.[/dim]")
        except Exception as exc:  # noqa: BLE001
            console.print(f"\n[red]  Error:[/red] {exc}")

        console.print()
        again = Confirm.ask("  Run another query?", default=True)
        if not again:
            console.print("\n[dim]  Goodbye.[/dim]\n")
            raise typer.Exit()
        console.clear()
        _print_logo()
        console.print()


# ── query command ─────────────────────────────────────────────────────

@app.command()
def query(
    query_text: str = typer.Argument(..., metavar="QUERY", help="Research question or topic."),
    mode: str = typer.Option("topic", "--mode", "-m", help=f"Research mode: {', '.join(['topic','company','tech','market','news','academic','competitor'])}."),
    effort: Optional[str] = typer.Option(None, "--effort", "-e", help="Depth: low | medium | high."),
    fmt: Optional[str] = typer.Option(None, "--format", "-f", help="Output format: markdown | json | html."),
    ensemble: Optional[bool] = typer.Option(None, "--ensemble/--no-ensemble", help="Enable multi-model ensemble."),
    ensemble_mode: Optional[str] = typer.Option(None, "--ensemble-mode", help="Ensemble profile: cheap | balanced | max_confidence."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show extra metrics after run."),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging."),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress result output."),
) -> None:
    """[bold]Run a research query[/bold] with live pipeline progress."""
    effort_r = _resolve_effort(effort)
    _run_query(
        mode=mode, query=query_text, effort=effort_r,
        fmt=fmt, quiet=quiet, verbose=verbose, debug=debug,
        ensemble=ensemble, ensemble_mode=ensemble_mode,
        live_display=True,
    )


# ── history command ───────────────────────────────────────────────────

@app.command()
def history(
    limit: int = typer.Option(20, "--limit", "-n", help="Number of records to show."),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Filter by research mode."),
    search: Optional[str] = typer.Option(None, "--search", "-s", help="Filter by query text."),
    fmt: str = typer.Option("table", "--format", "-f", help="Output format: table | json."),
) -> None:
    """[bold]Browse run history[/bold] — past research sessions."""
    from researchhq.history import list_runs, aggregate, reindex_from_folder, db_path

    with console.status("[dim]Loading history…[/dim]"):
        reindex_from_folder()
        runs = list_runs(mode=mode, text=search, limit=limit)
        agg  = aggregate()

    if fmt == "json":
        import dataclasses
        console.print_json(json.dumps([
            {k: getattr(r, k) for k in ["id", "mode", "query", "provider", "confidence",
                                          "sources_count", "facts_count", "equivalent_cost_usd",
                                          "generated_at"]}
            for r in runs
        ], default=str))
        return

    if not runs:
        console.print(Panel("[dim]No history found.[/dim]", border_style="dim"))
        return

    # Summary stats
    stats = Table(box=None, show_header=False, padding=(0, 3))
    stats.add_column(style="dim")
    stats.add_column(style="bold white")
    stats.add_row("Total runs", str(agg["total_reports"]))
    stats.add_row("Total sources", str(agg["total_sources"]))
    stats.add_row("Total cost", f"${agg['total_cost']:.4f}")
    stats.add_row("Last run", _time_ago(agg.get("last_run_at", "")))
    console.print(Panel(stats, title="[bold]History[/bold]", border_style="bright_blue", padding=(0, 1)))
    console.print()

    # Run table
    tbl = Table(
        box=box.SIMPLE, show_edge=False,
        header_style="bold dim", row_styles=["", "dim"],
        expand=True,
    )
    tbl.add_column("#",         width=4,  style="dim")
    tbl.add_column("Mode",      width=12, style="cyan")
    tbl.add_column("Query",     ratio=3)
    tbl.add_column("Provider",  width=10, style="dim")
    tbl.add_column("Conf",      width=6,  justify="right")
    tbl.add_column("Sources",   width=7,  justify="right", style="dim")
    tbl.add_column("Cost",      width=8,  justify="right", style="dim")
    tbl.add_column("When",      width=10, style="dim")

    for i, r in enumerate(runs, 1):
        conf_str = f"{r.confidence * 100:.0f}%" if r.confidence else "—"
        conf_sty = (
            "green" if r.confidence and r.confidence >= 0.75
            else "yellow" if r.confidence and r.confidence >= 0.5
            else "red" if r.confidence else "dim"
        )
        tbl.add_row(
            str(i),
            r.mode,
            r.query[:80],
            r.provider or "—",
            Text(conf_str, style=conf_sty),
            str(r.sources_count),
            f"${r.equivalent_cost_usd:.4f}" if r.equivalent_cost_usd else "—",
            _time_ago(r.generated_at),
        )

    console.print(tbl)
    if len(runs) == limit:
        console.print(f"[dim]  Showing {limit} most recent. Use --limit N for more.[/dim]")


# ── agents command ────────────────────────────────────────────────────

@app.command()
def agents() -> None:
    """[bold]Show configured AI providers[/bold] and the active routing chain."""
    from researchhq.config import settings

    # Provider chain
    try:
        from researchhq.llm.router import LLMRouter
        router = LLMRouter()
        providers = router.providers
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to load router:[/red] {exc}")
        raise typer.Exit(1)

    tbl = Table(
        title="Provider chain", box=box.SIMPLE, show_edge=False,
        header_style="bold dim", expand=False,
    )
    tbl.add_column("#",        width=3, style="dim")
    tbl.add_column("Name",     width=12)
    tbl.add_column("Model",    width=30, style="dim")
    tbl.add_column("Status",   width=12)
    tbl.add_column("API key",  width=10)

    key_map = {
        "groq":      bool(settings.groq_api_key),
        "gemini":    bool(settings.gemini_api_key),
        "openai":    bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "ollama":    True,
    }

    for i, p in enumerate(providers, 1):
        name = getattr(p, "name", str(p))
        model = settings.models.get(name, "—")
        has_key = key_map.get(name.lower(), False)
        key_txt = Text("✓ set", style="green") if has_key else Text("✗ missing", style="red")
        tbl.add_row(str(i), f"[bold]{name}[/bold]", model, Text("● active", style="green"), key_txt)

    console.print()
    console.print(tbl)

    # Ensemble settings
    console.print()
    ens_tbl = Table(box=None, show_header=False, padding=(0, 3), expand=False)
    ens_tbl.add_column(style="dim")
    ens_tbl.add_column(style="bold white")
    ens_tbl.add_row("Ensemble", "enabled" if settings.ensemble_enabled else "disabled")
    if settings.ensemble_enabled:
        ens_tbl.add_row("Mode",       settings.ensemble_mode)
        ens_tbl.add_row("Providers",  ", ".join(settings.ensemble_providers) or "auto")
        ens_tbl.add_row("Timeout",    f"{settings.ensemble_provider_timeout}s")
        ens_tbl.add_row("Parallel",   str(settings.ensemble_max_parallel_providers))
    console.print(Panel(ens_tbl, title="[bold]Ensemble[/bold]", border_style="dim", padding=(0, 1)))


# ── settings command ──────────────────────────────────────────────────

settings_app = typer.Typer(
    name="settings",
    help="[bold]View and modify settings.[/bold]",
    rich_markup_mode="rich",
    no_args_is_help=False,
    invoke_without_command=True,
)
app.add_typer(settings_app, name="settings")


@settings_app.callback(invoke_without_command=True)
def settings_cmd(ctx: typer.Context) -> None:
    """[bold]Show all current settings.[/bold]"""
    if ctx.invoked_subcommand is not None:
        return

    from researchhq.config import settings

    sections: dict[str, list[tuple[str, str]]] = {
        "Connection": [
            ("default_provider", settings.default_provider),
            ("fallback_chain", " → ".join(settings.fallback_chain)),
            ("ollama_host", settings.ollama_host),
        ],
        "Pipeline": [
            ("verbosity_default", settings.verbosity_default),
            ("default_format", settings.default_format),
            ("output_folder", str(settings.output_folder)),
        ],
        "Ensemble": [
            ("ensemble_enabled", str(settings.ensemble_enabled)),
            ("ensemble_mode", settings.ensemble_mode),
            ("ensemble_providers", ", ".join(settings.ensemble_providers) or "auto"),
            ("ensemble_provider_timeout", f"{settings.ensemble_provider_timeout}s"),
            ("ensemble_max_parallel_providers", str(settings.ensemble_max_parallel_providers)),
        ],
        "Search": [
            ("search_engines", ", ".join(settings.search_engines)),
            ("max_results_per_query", str(settings.max_results_per_query)),
            ("max_total_sources", str(settings.max_total_sources)),
        ],
        "Models": [
            (k, v) for k, v in settings.models.items()
        ],
        "API Keys": [
            ("groq",      "✓ set" if settings.groq_api_key else "✗ not set"),
            ("gemini",    "✓ set" if settings.gemini_api_key else "✗ not set"),
            ("openai",    "✓ set" if settings.openai_api_key else "✗ not set"),
            ("anthropic", "✓ set" if settings.anthropic_api_key else "✗ not set"),
        ],
    }

    for section, rows in sections.items():
        tbl = Table(box=None, show_header=False, padding=(0, 3), expand=False)
        tbl.add_column(style="dim", width=36)
        tbl.add_column(style="white")
        for k, v in rows:
            val_style = "green" if "✓" in v else "red" if "✗" in v else "white"
            tbl.add_row(k, Text(v, style=val_style))
        console.print(Panel(tbl, title=f"[bold]{section}[/bold]", border_style="dim", padding=(0, 1)))
        console.print()


@settings_app.command("set")
def settings_set(
    key: str   = typer.Argument(..., help="Setting key, e.g. default_provider"),
    value: str = typer.Argument(..., help="New value."),
    global_: bool = typer.Option(False, "--global", "-g", help="Write to global ~/.researchhq/config.yaml."),
) -> None:
    """Set a single configuration value and persist it to config.yaml."""
    from researchhq.config import save_settings

    path = Path.home() / ".researchhq" / "config.yaml" if global_ else None
    saved = save_settings({key: value}, path=path)
    console.print(f"[green]✓[/green] Saved [bold]{key}[/bold] = [cyan]{value}[/cyan]  →  [dim]{saved}[/dim]")


# ── config command ────────────────────────────────────────────────────

@app.command()
def config(
    edit: bool = typer.Option(False, "--edit", "-e", help="Open config in $EDITOR."),
) -> None:
    """[bold]Show config file locations and raw content.[/bold]"""
    import yaml

    candidates = [
        Path.home() / ".researchhq" / "config.yaml",
        Path("config.yaml"),
        Path("researchhq.yaml"),
    ]
    env_path = os.environ.get("RESEARCHHQ_CONFIG")
    if env_path:
        candidates.insert(0, Path(env_path))

    found = [p for p in candidates if p.exists()]

    if not found:
        console.print(Panel(
            "[dim]No config.yaml found. Using built-in defaults.[/dim]\n"
            "Run [bold]research-hq setup[/bold] to create one.",
            border_style="dim",
        ))
        return

    for p in found:
        if edit:
            editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
            subprocess.run([editor, str(p)])
            return

        raw = p.read_text(encoding="utf-8")
        console.print(Panel(
            Syntax(raw, "yaml", theme="monokai", line_numbers=True),
            title=f"[bold]{p}[/bold]",
            border_style="dim",
        ))
        console.print()


# ── doctor command ────────────────────────────────────────────────────

@app.command()
def doctor() -> None:
    """[bold]Full health check[/bold] — deps, providers, DB, paths."""
    from researchhq.doctor import has_critical_failure, run_checks

    console.print()
    with console.status("[dim]Running checks…[/dim]"):
        results = run_checks()

    groups = {"critical": [], "warn": [], "info": []}
    for r in results:
        groups[r.severity].append(r)

    for severity, label, style in [
        ("critical", "Critical", "bold red"),
        ("warn",     "Warnings", "bold yellow"),
        ("info",     "Info",     "bold dim"),
    ]:
        batch = groups[severity]
        if not batch:
            continue
        tbl = Table(box=None, show_header=False, padding=(0, 2), expand=True)
        tbl.add_column(width=3, no_wrap=True)
        tbl.add_column(width=28, no_wrap=True)
        tbl.add_column(ratio=1)
        for r in batch:
            icon = Text("✓", style="green") if r.ok else Text("✗", style="red")
            tbl.add_row(icon, Text(r.name, style="bold" if not r.ok else "dim"), r.message)
        console.print(Panel(tbl, title=f"[{style}]{label}[/{style}]", border_style="dim", padding=(0, 1)))
        console.print()

    if has_critical_failure(results):
        console.print("[red]  ✗ One or more critical checks failed. Fix the issues above before running queries.[/red]")
        raise typer.Exit(code=1)
    console.print("[green]  ✓ All critical checks passed.[/green]")


# ── setup command (wizard) ────────────────────────────────────────────

@app.command()
def setup() -> None:
    """[bold]First-time setup wizard[/bold] — configure API keys and defaults."""
    from researchhq.config import save_settings

    _print_logo()
    console.print()
    console.print(Panel(
        "[bold]Welcome to ResearchHQ Setup[/bold]\n"
        "[dim]This wizard will help you configure API keys and preferences.\n"
        "Values are saved to [bold]~/.researchhq/config.yaml[/bold].[/dim]",
        border_style="bright_blue",
        padding=(0, 2),
    ))
    console.print()

    config_path = Path.home() / ".researchhq" / "config.yaml"
    updates: dict = {}

    console.print("[bold]API Keys[/bold] [dim](press Enter to skip)[/dim]\n")

    for provider, env_var in [
        ("Groq",      "GROQ_API_KEY"),
        ("Gemini",    "GEMINI_API_KEY"),
        ("OpenAI",    "OPENAI_API_KEY"),
        ("Anthropic", "ANTHROPIC_API_KEY"),
    ]:
        existing = os.environ.get(env_var, "")
        masked = existing[:8] + "…" if existing else "[dim]not set[/dim]"
        key = Prompt.ask(f"  {provider} key [dim]({env_var})[/dim]", default="", password=True, show_default=False)
        if key.strip():
            updates[env_var.lower()] = key.strip()
        elif existing:
            console.print(f"    [dim]Keeping existing: {masked}[/dim]")

    console.print()
    console.print("[bold]Defaults[/bold]\n")

    default_provider = Prompt.ask(
        "  Default provider",
        choices=["groq", "gemini", "openai", "anthropic", "ollama"],
        default="groq",
    )
    updates["default_provider"] = default_provider

    output_folder = Prompt.ask(
        "  Report output folder",
        default=str(Path.home() / "researchhq_reports"),
    )
    updates["output_folder"] = output_folder

    console.print()
    if Confirm.ask("  Save these settings?", default=True):
        saved = save_settings(updates, path=config_path)
        console.print(f"\n[green]✓[/green] Configuration saved to [bold]{saved}[/bold]")
        console.print("\n[dim]Run [bold]research-hq doctor[/bold] to verify everything is working.[/dim]")
    else:
        console.print("\n[dim]Setup cancelled — nothing saved.[/dim]")


# ── models command ────────────────────────────────────────────────────

@app.command()
def models() -> None:
    """[bold]List configured models[/bold] per provider."""
    from researchhq.config import settings

    tbl = Table(
        title="Configured models",
        box=box.SIMPLE, show_edge=False,
        header_style="bold dim", expand=False,
    )
    tbl.add_column("Provider", style="cyan", width=14)
    tbl.add_column("Model",    style="white")
    tbl.add_column("API Key",  width=10)

    key_map = {
        "groq":      bool(settings.groq_api_key),
        "gemini":    bool(settings.gemini_api_key),
        "openai":    bool(settings.openai_api_key),
        "anthropic": bool(settings.anthropic_api_key),
        "ollama":    True,
    }

    for provider, model in settings.models.items():
        has_key = key_map.get(provider.lower(), False)
        key_txt = Text("✓ set", style="green") if has_key else Text("✗ missing", style="dim red")
        tbl.add_row(provider, model, key_txt)

    console.print()
    console.print(tbl)


# ── test-models command ───────────────────────────────────────────────

@app.command(name="test-models")
def test_models(
    provider: Optional[str] = typer.Option(None, "--provider", "-p", help="Test a specific provider only."),
) -> None:
    """[bold]Send a test prompt[/bold] to each configured provider and measure latency."""
    from researchhq.config import settings

    TEST_PROMPT = "Reply with exactly: OK"

    try:
        from researchhq.llm.router import LLMRouter
        all_providers = LLMRouter().providers
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Router failed to load:[/red] {exc}")
        raise typer.Exit(1)

    if provider:
        all_providers = [p for p in all_providers if p.name.lower() == provider.lower()]
        if not all_providers:
            console.print(f"[red]No provider named '{provider}' in the chain.[/red]")
            raise typer.Exit(1)

    tbl = Table(
        title="Provider connectivity test",
        box=box.SIMPLE, show_edge=False,
        header_style="bold dim",
    )
    tbl.add_column("Provider",  style="cyan", width=14)
    tbl.add_column("Model",     width=30)
    tbl.add_column("Status",    width=10)
    tbl.add_column("Latency",   width=10, justify="right")
    tbl.add_column("Response",  ratio=1,  style="dim")

    for p in all_providers:
        model = settings.models.get(p.name, "—")
        with console.status(f"[dim]Testing {p.name}…[/dim]"):
            t0 = time.monotonic()
            try:
                # Each provider should have a .complete() or similar async method
                resp = asyncio.run(p.complete(TEST_PROMPT))
                latency = time.monotonic() - t0
                resp_text = str(resp)[:60] if resp else "—"
                tbl.add_row(
                    p.name, model,
                    Text("✓ OK", style="green"),
                    f"{latency:.2f}s",
                    resp_text,
                )
            except Exception as exc:  # noqa: BLE001
                latency = time.monotonic() - t0
                tbl.add_row(
                    p.name, model,
                    Text("✗ Fail", style="red"),
                    f"{latency:.2f}s",
                    str(exc)[:60],
                )

    console.print()
    console.print(tbl)


# ── logs command ──────────────────────────────────────────────────────

@app.command()
def logs(
    lines: int = typer.Option(50, "--lines", "-n", help="Number of log lines to show."),
) -> None:
    """[bold]Show recent application log entries.[/bold]"""
    from researchhq.config import settings

    candidates = [
        Path(settings.output_folder) / "researchhq.log",
        Path.home() / ".researchhq" / "researchhq.log",
        Path("researchhq.log"),
    ]
    log_file = next((p for p in candidates if p.exists()), None)

    if not log_file:
        console.print(Panel(
            "[dim]No log file found.[/dim]\n"
            f"Checked:\n" + "\n".join(f"  {p}" for p in candidates),
            border_style="dim",
        ))
        return

    all_lines = log_file.read_text(encoding="utf-8", errors="replace").splitlines()
    tail = all_lines[-lines:]

    tbl = Table(box=None, show_header=False, padding=(0, 1), expand=True)
    tbl.add_column(width=8,  style="dim", no_wrap=True)   # level
    tbl.add_column(width=22, style="dim", no_wrap=True)   # timestamp
    tbl.add_column(ratio=1)                                # message

    for line in tail:
        level_color = "white"
        if "ERROR" in line or "CRITICAL" in line:
            level_color = "red"
        elif "WARNING" in line or "WARN" in line:
            level_color = "yellow"
        elif "DEBUG" in line:
            level_color = "dim"
        tbl.add_row("", Text(line[:22], style="dim"), Text(line, style=level_color))

    console.print(Panel(
        tbl,
        title=f"[bold]Logs[/bold]  [dim]{log_file}  (last {len(tail)} lines)[/dim]",
        border_style="dim",
        padding=(0, 1),
    ))


# ── export command ────────────────────────────────────────────────────

@app.command()
def export(
    output: str = typer.Option("./exports", "--output", "-o", help="Destination directory."),
    last: int = typer.Option(10, "--last", "-n", help="Export the N most recent reports."),
    fmt: str = typer.Option("markdown", "--format", "-f", help="Format: markdown | json."),
) -> None:
    """[bold]Export saved reports[/bold] to a directory."""
    from researchhq.history import list_runs, reindex_from_folder
    from researchhq.reports.exporter import save as _save

    out_dir = Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    with console.status("[dim]Scanning history…[/dim]"):
        reindex_from_folder()
        runs = list_runs(limit=last)

    if not runs:
        console.print("[dim]No reports found.[/dim]")
        return

    imported = 0
    for r in runs:
        src = Path(r.json_path)
        if not src.exists():
            continue
        try:
            import json as _json
            data = _json.loads(src.read_text(encoding="utf-8"))
            dest = out_dir / src.name
            if fmt == "markdown":
                dest = dest.with_suffix(".md")
                from researchhq.reports.exporter import to_markdown
                # Build a minimal report object or just copy the JSON
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            else:
                dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            imported += 1
        except Exception as exc:  # noqa: BLE001
            console.print(f"[dim]  Skipped {src.name}: {exc}[/dim]")

    console.print(f"[green]✓[/green] Exported [bold]{imported}[/bold] reports to [dim]{out_dir.resolve()}[/dim]")


# ── clear-history command ─────────────────────────────────────────────

@app.command(name="clear-history")
def clear_history(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    older_than: Optional[int] = typer.Option(None, "--older-than", help="Only clear records older than N days."),
) -> None:
    """[bold]Delete all history records[/bold] from the database."""
    import sqlite3
    from contextlib import closing
    from researchhq.history import db_path, ensure_db

    if not yes:
        msg = "Delete ALL history records?"
        if older_than:
            msg = f"Delete history records older than {older_than} days?"
        if not Confirm.ask(f"  [yellow]{msg}[/yellow]", default=False):
            console.print("[dim]  Cancelled.[/dim]")
            return

    ensure_db()
    p = db_path()
    with closing(sqlite3.connect(str(p))) as conn:
        if older_than:
            conn.execute(
                "DELETE FROM runs WHERE generated_at < datetime('now', ?)",
                (f"-{older_than} days",),
            )
        else:
            conn.execute("DELETE FROM runs")
        deleted = conn.execute("SELECT changes()").fetchone()[0]
        conn.commit()

    console.print(f"[green]✓[/green] Deleted [bold]{deleted}[/bold] records.")


# ── reset-config command ──────────────────────────────────────────────

@app.command(name="reset-config")
def reset_config(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
    global_: bool = typer.Option(False, "--global", "-g", help="Reset global config (~/.researchhq/config.yaml)."),
) -> None:
    """[bold]Reset config.yaml to built-in defaults.[/bold]"""
    path = Path.home() / ".researchhq" / "config.yaml" if global_ else Path("config.yaml")

    if not path.exists():
        console.print(f"[dim]No config file at {path} — nothing to reset.[/dim]")
        return

    if not yes and not Confirm.ask(f"  [yellow]Reset {path} to defaults?[/yellow]", default=False):
        console.print("[dim]  Cancelled.[/dim]")
        return

    backup = path.with_suffix(".yaml.bak")
    path.rename(backup)
    console.print(f"[green]✓[/green] Backed up to [dim]{backup}[/dim]")
    console.print("[dim]  A fresh config will be generated on next run.[/dim]")


# ── modes command ─────────────────────────────────────────────────────

@app.command()
def modes() -> None:
    """[bold]List all available research modes.[/bold]"""
    from researchhq.modes import MODES

    tbl = Table(box=box.SIMPLE, show_edge=False, header_style="bold dim", expand=False)
    tbl.add_column("Mode",        style="cyan", width=14)
    tbl.add_column("Description", ratio=1)

    seen: set[str] = set()
    for name, cls in MODES.items():
        if name in seen:
            continue
        seen.add(name)
        try:
            cfg = cls().config
            desc = getattr(cfg, "description", "")
        except Exception:  # noqa: BLE001
            desc = ""
        tbl.add_row(name, desc)

    console.print()
    console.print(tbl)


# ── status command (provider keys quick-view) ─────────────────────────

@app.command()
def status() -> None:
    """[bold]Quick provider status[/bold] — show which API keys are configured."""
    from researchhq.config import settings

    rows = [
        ("groq",      settings.groq_api_key,      settings.models.get("groq", "—")),
        ("gemini",    settings.gemini_api_key,     settings.models.get("gemini", "—")),
        ("openai",    settings.openai_api_key,     settings.models.get("openai", "—")),
        ("anthropic", settings.anthropic_api_key,  settings.models.get("anthropic", "—")),
        ("ollama",    True,                         settings.models.get("ollama", "—")),
    ]

    tbl = Table(box=box.SIMPLE, show_edge=False, header_style="bold dim", expand=False)
    tbl.add_column("Provider", style="cyan",  width=12)
    tbl.add_column("Key",      width=12)
    tbl.add_column("Model",    style="dim")
    for name, has_key, model in rows:
        key_txt = Text("✓ set", style="green") if has_key else Text("✗ missing", style="dim red")
        tbl.add_row(name, key_txt, model)

    console.print()
    console.print(tbl)


# ── Legacy research subgroup (backward compat) ────────────────────────

_FormatOpt  = typer.Option(None, "--format", "-f",         help="Output format: markdown, json, html.")
_QuietOpt   = typer.Option(False, "--quiet", "-q",         help="Suppress non-essential output.")
_VerboseOpt = typer.Option(False, "--verbose", "-v",       help="Show stage-by-stage progress.")
_DebugOpt   = typer.Option(False, "--debug",               help="Show debug logs.")
_EffortOpt  = typer.Option(None, "--effort", "-e",         help="Depth: low | medium | high.")
_EnsOpt     = typer.Option(None, "--ensemble/--no-ensemble", help="Multi-model ensemble.")
_EnsModeOpt = typer.Option(None, "--ensemble-mode",        help="Ensemble profile: cheap | balanced | max_confidence.")


def _legacy(mode: str, query: str, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode) -> None:
    _run_query(
        mode=mode, query=query, effort=_resolve_effort(effort),
        fmt=fmt, quiet=quiet, verbose=verbose, debug=debug,
        ensemble=ensemble, ensemble_mode=ensemble_mode,
        live_display=not quiet,
    )


@research_app.command("topic")
def _r_topic(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """General topic research."""
    _legacy("topic", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("company")
def _r_company(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """Company profile research."""
    _legacy("company", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("competitor")
def _r_competitor(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """Competitor analysis."""
    _legacy("competitor", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("tech")
def _r_tech(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """Technology research."""
    _legacy("technology", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("market")
def _r_market(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """Market research."""
    _legacy("market", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("news")
def _r_news(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """News and recent developments."""
    _legacy("news", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("academic")
def _r_academic(
    query: str = typer.Argument(...), fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt, verbose: bool = _VerboseOpt, debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt, ensemble: Optional[bool] = _EnsOpt,
    ensemble_mode: Optional[str] = _EnsModeOpt,
) -> None:
    """Academic / paper research."""
    _legacy("academic", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


# ── Entry point ───────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
