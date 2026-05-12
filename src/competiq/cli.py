import asyncio
import logging

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from competiq.agents.researcher import research_company
from competiq.config import settings
from competiq.llm.cost_tracker import tracker

app = typer.Typer(help="CompetIQ - multi-agent competitive intelligence for SaaS.")
console = Console()


@app.command()
def research(company: str = typer.Argument(..., help="Company name to research")):
    """Week-1 single-agent briefing (kept for comparison)."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    console.print(Panel(f"[bold cyan]Researching:[/bold cyan] {company}", expand=False))

    with console.status("[bold green]Searching web and synthesizing briefing...[/bold green]"):
        result = asyncio.run(research_company(company))

    console.print(
        Panel(
            Markdown(result.briefing),
            title=f"Briefing: {company}",
            border_style="green",
        )
    )

    console.print(f"\n[dim]LLM provider used:[/dim] [bold]{result.provider_used}[/bold]")
    console.print(f"[dim]Sources collected:[/dim] {len(result.sources)}\n")
    _print_cost_table()


@app.command()
def pipeline(company: str = typer.Argument(..., help="Company name to research")):
    """Week-2 multi-agent pipeline: planner -> 3 workers in parallel -> synthesizer."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_run_pipeline(company))


async def _run_pipeline(company: str) -> None:
    # Imported lazily so Week-1 `research` command doesn't pay LangGraph import cost
    from competiq.graph.workflow import graph

    console.print(Panel(f"[bold cyan]Multi-agent research:[/bold cyan] {company}", expand=False))
    console.print("[dim]planner -> (market || signal || news) -> synthesizer[/dim]\n")


    initial = {
        "company": company,
        "plan": None,
        "findings": [],
        "final_report": "",
        "synthesis_provider": "",
    }

    state: dict = dict(initial)
    async for event in graph.astream(initial, stream_mode="updates"):
        for node, update in event.items():
            _render_node_update(node, update)
            if "findings" in update:
                state["findings"] = state["findings"] + update["findings"]
            for k, v in update.items():
                if k != "findings":
                    state[k] = v

    console.print()
    console.print(
        Panel(
            Markdown(state["final_report"]),
            title=f"Final Briefing: {company}",
            border_style="green",
        )
    )

    timing = Table(title="Agent Performance")
    timing.add_column("Agent")
    timing.add_column("Sources", justify="right")
    timing.add_column("Time (s)", justify="right")
    timing.add_column("Provider")
    for f in state["findings"]:
        timing.add_row(f.agent, str(len(f.sources)), f"{f.elapsed_seconds:.1f}", f.provider)
    timing.add_row("synthesizer", "-", "-", state["synthesis_provider"])
    console.print(timing)

    _print_cost_table()


def _render_node_update(node: str, update: dict) -> None:
    if node == "planner":
        plan = update.get("plan")
        if plan:
            total = len(plan.market_queries) + len(plan.signal_queries) + len(plan.news_queries)
            console.print(f"[bold cyan][OK] planner    [/bold cyan] {total} queries planned")
    elif node in ("market", "signal", "news"):
        findings = update.get("findings", [])
        if findings:
            f = findings[0]
            console.print(
                f"[bold green][OK] {node:<10}[/bold green] {len(f.sources)} sources | "
                f"{f.elapsed_seconds:.1f}s | {f.provider}"
            )
    elif node == "synthesizer":
        provider = update.get("synthesis_provider", "?")
        console.print(f"[bold magenta][OK] synthesizer[/bold magenta] via {provider}")


def _print_cost_table() -> None:
    summary = tracker.summary()
    table = Table(title="Cost Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("LLM calls", str(summary["calls"]))
    table.add_row("Input tokens", f"{summary['input_tokens']:,}")
    table.add_row("Output tokens", f"{summary['output_tokens']:,}")
    table.add_row("Actual cost", f"${summary['actual_cost_usd']:.4f}")
    table.add_row("Equivalent paid cost", f"${summary['equivalent_paid_cost_usd']:.4f}")
    console.print(table)


@app.command()
def status():
    """Show which providers are configured."""
    table = Table(title="Provider Status")
    table.add_column("Provider")
    table.add_column("Configured")
    table.add_column("Model")
    table.add_row(
        "Groq",
        "[green]yes[/green]" if settings.groq_api_key else "[red]no[/red]",
        settings.groq_model,
    )
    table.add_row(
        "Gemini",
        "[green]yes[/green]" if settings.gemini_api_key else "[red]no[/red]",
        settings.gemini_model,
    )
    table.add_row(
        "Ollama",
        f"[yellow]{settings.ollama_host}[/yellow]",
        settings.ollama_model,
    )
    console.print(table)


if __name__ == "__main__":
    app()
