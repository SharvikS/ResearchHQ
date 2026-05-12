"""Rich UI helpers — consistent banners, progress lines, report rendering, per-stage stats."""

from __future__ import annotations

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from researchhq.llm.cost_tracker import tracker
from researchhq.reports.exporter import to_markdown
from researchhq.reports.schema import ResearchReport

console = Console()


STAGE_COLORS = {
    "planner": "cyan",
    "searcher": "blue",
    "source_ranker": "magenta",
    "fetcher": "yellow",
    "extractor": "yellow",
    "synthesizer": "green",
    "verifier": "bright_blue",
    "formatter": "bright_magenta",
}


def banner(query: str, mode: str) -> None:
    console.print(Panel(
        f"[bold]Research[/bold] - [italic]{mode}[/italic] mode\n[bold cyan]{query}[/bold cyan]",
        border_style="cyan",
        expand=False,
    ))


def progress(stage: str, detail: str, verbose: bool) -> None:
    if not verbose:
        return
    color = STAGE_COLORS.get(stage, "white")
    console.print(f"[bold {color}][{stage:<14}][/bold {color}] {detail}")


def render_report(report: ResearchReport) -> None:
    md = to_markdown(report)
    console.print()
    console.print(Panel(
        Markdown(md),
        title=f"Report - {report.mode} - {report.query}",
        border_style="green",
    ))


def render_summary(report: ResearchReport, output_path: str | None) -> None:
    sources_by_tier: dict[str, int] = {}
    for s in report.sources:
        sources_by_tier[s.tier.value] = sources_by_tier.get(s.tier.value, 0) + 1

    table = Table(title="Run summary", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value")
    table.add_row("Mode", report.mode)
    table.add_row("Query", report.query)
    table.add_row("Provider used", report.provider_used or "n/a")
    table.add_row("Sources kept", str(len(report.sources)))
    fetched_ok = sum(1 for p in report.fetched_pages if p.chars > 0)
    table.add_row("Pages fetched", f"{fetched_ok}/{len(report.fetched_pages)}")
    table.add_row("Facts extracted", str(len(report.facts)))
    if report.verifier:
        failed = sum(1 for r in report.verifier.rules if not r.passed)
        table.add_row("Rules failed", f"{failed}/{len(report.verifier.rules)}")
        table.add_row("Citation violations", str(len(report.verifier.violations)))
        table.add_row("Confidence", f"{report.verifier.overall_confidence:.2f}")
    if sources_by_tier:
        table.add_row("Sources by tier", ", ".join(f"{k}:{v}" for k, v in sorted(sources_by_tier.items())))
    if output_path:
        table.add_row("Saved to", output_path)
    console.print(table)


def render_rules(report: ResearchReport) -> None:
    if not report.verifier or not report.verifier.rules:
        return
    table = Table(title="Verifier rules")
    table.add_column("Rule")
    table.add_column("Severity")
    table.add_column("Result")
    table.add_column("Message")
    for r in report.verifier.rules:
        result = "[green]pass[/green]" if r.passed else f"[red]{r.severity}[/red]"
        table.add_row(r.name, r.severity, result, r.message)
    console.print(table)


def render_stage_costs(report: ResearchReport) -> None:
    if not report.stage_costs:
        return
    table = Table(title="Per-stage LLM usage")
    table.add_column("Stage")
    table.add_column("Calls", justify="right")
    table.add_column("In tokens", justify="right")
    table.add_column("Out tokens", justify="right")
    table.add_column("Equiv $", justify="right")
    for sc in report.stage_costs:
        table.add_row(
            sc.stage, str(sc.calls), f"{sc.input_tokens:,}",
            f"{sc.output_tokens:,}", f"${sc.equivalent_paid_cost_usd:.4f}",
        )
    console.print(table)


def render_cost() -> None:
    s = tracker.summary()
    if s["calls"] == 0:
        return
    table = Table(title="Total LLM usage", show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Calls", str(s["calls"]))
    table.add_row("Input tokens", f"{s['input_tokens']:,}")
    table.add_row("Output tokens", f"{s['output_tokens']:,}")
    table.add_row("Equivalent paid cost", f"${s['equivalent_paid_cost_usd']:.4f}")
    console.print(table)


def render_provider_status(rows: list[tuple[str, bool, str]]) -> None:
    table = Table(title="Provider status")
    table.add_column("Provider")
    table.add_column("Configured")
    table.add_column("Model")
    for name, configured, model in rows:
        flag = "[green]yes[/green]" if configured else "[red]no[/red]"
        table.add_row(name, flag, model or "-")
    console.print(table)
