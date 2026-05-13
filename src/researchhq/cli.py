"""researchhq CLI: `research <mode> "<query>" [--format ...] [--quiet|--verbose|--debug]`.

Modes: topic, company, competitor, tech, market, news, academic.
Backward-compatible aliases for the legacy `competiq research` and `competiq pipeline` are
provided as `research company` and `research competitor`."""

from __future__ import annotations

import asyncio
from typing import Optional

import typer

from researchhq.config import settings
from researchhq.effort import DEFAULT_EFFORT, PROFILES
from researchhq.modes import MODES
from researchhq.pipeline import StageEvent, run
from researchhq.reports.exporter import save
from researchhq.utils.logging import configure as configure_logging
from researchhq.utils.rich_ui import (
    banner,
    console,
    progress,
    render_cost,
    render_provider_status,
    render_report,
    render_rules,
    render_stage_costs,
    render_summary,
)

app = typer.Typer(
    help="researchhq - multi-agent research CLI for any topic, company, technology, market, paper, or trend.",
    no_args_is_help=True,
)


# A nested 'research' command group so the universal pattern is `research <mode> "<query>"`.
research_app = typer.Typer(help="Run a research pipeline. Choose a mode subcommand.", no_args_is_help=True)
app.add_typer(research_app, name="research")


def _resolve_verbosity(quiet: bool, verbose: bool, debug: bool) -> str:
    if debug:
        return "debug"
    if verbose:
        return "verbose"
    if quiet:
        return "quiet"
    return settings.verbosity_default


def _resolve_effort(value: Optional[str]) -> str:
    key = (value or DEFAULT_EFFORT).strip().lower()
    if key not in PROFILES:
        raise typer.BadParameter(
            f"--effort must be one of {sorted(PROFILES)}; got '{value}'."
        )
    return key


def _execute(
    mode: str,
    query: str,
    fmt: Optional[str],
    quiet: bool,
    verbose: bool,
    debug: bool,
    effort: Optional[str] = None,
    ensemble: Optional[bool] = None,
    ensemble_mode: Optional[str] = None,
) -> None:
    verbosity = _resolve_verbosity(quiet, verbose, debug)
    effort_resolved = _resolve_effort(effort)
    configure_logging(verbosity)

    # Override ensemble settings from CLI flags
    if ensemble is not None:
        settings.ensemble_enabled = ensemble
    if ensemble_mode is not None:
        valid_modes = ("cheap", "balanced", "max_confidence")
        if ensemble_mode not in valid_modes:
            raise typer.BadParameter(
                f"--ensemble-mode must be one of {valid_modes}; got '{ensemble_mode}'."
            )
        settings.ensemble_mode = ensemble_mode

    show_progress = verbosity in ("verbose", "debug")

    if settings.ensemble_enabled:
        banner(query, mode)
        from researchhq.utils.rich_ui import console as _console
        _console.print(
            f"[bold #7c5cff]⬡ ENSEMBLE MODE[/]: {settings.ensemble_mode} "
            f"(providers: {', '.join(settings.ensemble_providers) or 'auto'})"
        )
    else:
        banner(query, mode)

    def on_event(ev: StageEvent) -> None:
        progress(ev.stage, ev.detail, show_progress)

    with console.status(f"[bold green]Researching ({mode}, effort={effort_resolved})...[/bold green]") if not show_progress else _Null():
        report = asyncio.run(run(mode, query, on_event=on_event, effort=effort_resolved))

    output_path: Optional[str] = None
    if fmt:
        path = save(report, fmt=fmt)
        output_path = str(path)
    else:
        path = save(report, fmt=settings.default_format)
        output_path = str(path)

    if verbosity != "quiet":
        render_report(report)
    render_summary(report, output_path)
    if verbosity != "quiet":
        render_rules(report)
        render_stage_costs(report)
        render_cost()


class _Null:
    """No-op context manager used when we'd otherwise call console.status() but
    want progress lines visible instead of the spinner."""
    def __enter__(self) -> "_Null":
        return self
    def __exit__(self, *exc: object) -> None:
        return None


# Common option set for every mode subcommand.
_FormatOpt = typer.Option(None, "--format", "-f", help="Output format: markdown, json, html.")
_QuietOpt = typer.Option(False, "--quiet", "-q", help="Suppress non-essential output.")
_VerboseOpt = typer.Option(False, "--verbose", "-v", help="Show stage-by-stage progress.")
_DebugOpt = typer.Option(False, "--debug", help="Show debug logs (including HTTP).")
_EffortOpt = typer.Option(
    None, "--effort", "-e",
    help="Research depth: low (fast scan), medium (default, balanced), high (deep dive).",
)
_EnsembleOpt = typer.Option(
    None, "--ensemble/--no-ensemble",
    help="Enable parallel multi-model ensemble synthesis (overrides config).",
)
_EnsembleModeOpt = typer.Option(
    None, "--ensemble-mode",
    help="Ensemble profile: cheap, balanced, max_confidence.",
)


@research_app.command("topic")
def topic(
    query: str = typer.Argument(..., help="Topic to research, e.g. 'AI agents in cybersecurity'."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """General topic research."""
    _execute("topic", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("company")
def company(
    query: str = typer.Argument(..., help="Company name, e.g. 'Supabase'."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """Company profile research."""
    _execute("company", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("competitor")
def competitor(
    query: str = typer.Argument(..., help="Target company for a competitor scan, e.g. 'Linear'."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """Competitor analysis."""
    _execute("competitor", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("tech")
def tech(
    query: str = typer.Argument(..., help="Technology, framework, or platform."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """Technology research."""
    _execute("technology", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("market")
def market(
    query: str = typer.Argument(..., help="Market or industry."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """Market research."""
    _execute("market", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("news")
def news(
    query: str = typer.Argument(..., help="Subject of recent developments."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """News and recent developments."""
    _execute("news", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@research_app.command("academic")
def academic(
    query: str = typer.Argument(..., help="Academic topic or paper title."),
    fmt: Optional[str] = _FormatOpt,
    quiet: bool = _QuietOpt,
    verbose: bool = _VerboseOpt,
    debug: bool = _DebugOpt,
    effort: Optional[str] = _EffortOpt,
    ensemble: Optional[bool] = _EnsembleOpt,
    ensemble_mode: Optional[str] = _EnsembleModeOpt,
) -> None:
    """Academic / paper research."""
    _execute("academic", query, fmt, quiet, verbose, debug, effort, ensemble, ensemble_mode)


@app.command()
def modes() -> None:
    """List available research modes."""
    for name, cls in sorted(set((cls.__name__, cls) for cls in MODES.values()), key=lambda x: x[0]):
        cfg = cls().config
        console.print(f"[bold cyan]{cfg.name:<12}[/bold cyan] {cfg.description}")


@app.command()
def doctor() -> None:
    """Run a health check across deps, providers, paths, and DB."""
    from rich.table import Table
    from researchhq.doctor import has_critical_failure, run_checks

    results = run_checks()
    table = Table(title="researchhq doctor")
    table.add_column("Check"); table.add_column("OK"); table.add_column("Severity"); table.add_column("Detail")
    for r in results:
        ok = "[green]yes[/green]" if r.ok else "[red]no[/red]"
        sev_color = {"critical": "red", "warn": "yellow", "info": "cyan"}.get(r.severity, "white")
        sev = f"[{sev_color}]{r.severity}[/{sev_color}]"
        table.add_row(r.name, ok, sev, r.message)
    console.print(table)

    if has_critical_failure(results):
        console.print("\n[red]One or more critical checks failed.[/red]")
        raise typer.Exit(code=1)
    console.print("\n[green]All critical checks passed.[/green]")


@app.command()
def status() -> None:
    """Show provider configuration status."""
    rows = [
        ("groq", bool(settings.groq_api_key), settings.models.get("groq", "")),
        ("gemini", bool(settings.gemini_api_key), settings.models.get("gemini", "")),
        ("openai", bool(settings.openai_api_key), settings.models.get("openai", "")),
        ("anthropic", bool(settings.anthropic_api_key), settings.models.get("anthropic", "")),
        ("ollama", True, settings.models.get("ollama", "")),
    ]
    render_provider_status(rows)


if __name__ == "__main__":
    app()
