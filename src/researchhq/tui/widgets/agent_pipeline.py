"""Live multi-agent pipeline visualization.

One row per agent. State machine: pending → active → done | fail.
Each row shows a glyph, stage name, live status note, and elapsed time.
The synthesizer row expands into an "ensemble" variant with provider sub-rows.
"""

from __future__ import annotations

import time
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static

# ── Stage metadata ────────────────────────────────────────────────────

AGENT_ORDER = [
    "planner", "searcher", "source_ranker", "fetcher",
    "extractor", "synthesizer", "verifier", "formatter",
]

ENSEMBLE_AGENT_ORDER = [
    "planner", "searcher", "source_ranker", "fetcher",
    "extractor", "ensemble", "verifier", "formatter",
]

# Geometric glyphs: pending ○, active spinner, done ◆, fail ✕
# Premium aesthetic — geometric over ASCII characters.
SPINNER     = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
GLYPH_DONE  = "◆"
GLYPH_FAIL  = "✕"
GLYPH_IDLE  = "○"

# Stage display names (right-pad to 14 chars)
STAGE_LABELS: dict[str, str] = {
    "planner":      "planner",
    "searcher":     "searcher",
    "source_ranker": "ranker",
    "fetcher":      "fetcher",
    "extractor":    "extractor",
    "synthesizer":  "synthesizer",
    "ensemble":     "ensemble",
    "verifier":     "verifier",
    "formatter":    "formatter",
}

# Per-stage accent colors (Textual Rich markup) — cool color ramp
STAGE_COLORS: dict[str, str] = {
    "planner":      "#7c5cff",   # violet
    "searcher":     "#4a9eff",   # blue
    "source_ranker": "#38bdf8",  # sky
    "fetcher":      "#34d4bb",   # teal
    "extractor":    "#a3e635",   # lime
    "synthesizer":  "#f59e0b",   # amber
    "ensemble":     "#f59e0b",   # amber
    "verifier":     "#10b981",   # emerald
    "formatter":    "#e879f9",   # fuchsia
}


# ── AgentRow ──────────────────────────────────────────────────────────

class AgentRow(Static):
    """Single pipeline stage row.

    Renders as:
      <glyph>  <name:13>  <detail>  <elapsed:6>
    """

    DEFAULT_CSS = "AgentRow { height: 1; padding: 0 1; }"

    def __init__(self, name: str, **kwargs) -> None:
        super().__init__("", **kwargs)
        self._name      = name
        self._label     = STAGE_LABELS.get(name, name)
        self._state     = "pending"   # pending | active | done | fail
        self._detail    = ""
        self._started   = 0.0
        self._elapsed   = 0.0
        self._spin_idx  = 0
        self._tick_ref  = None

    # ── Public API ────────────────────────────────────────────────────

    def set_pending(self) -> None:
        self._state = "pending"
        self._detail = ""
        self._elapsed = 0.0
        self._stop_tick()
        self._render()

    def set_active(self, detail: str = "") -> None:
        self._state   = "active"
        self._detail  = detail
        self._started = time.monotonic()
        self._spin_idx = 0
        self._stop_tick()
        self._tick_ref = self.set_interval(0.09, self._tick)
        self.add_class("-active")
        self.remove_class("-pending", "-done", "-fail")
        self._render()

    def set_progress(self, detail: str) -> None:
        self._detail = detail
        if self._state == "active":
            self._render()

    def set_done(self, detail: str = "") -> None:
        self._state   = "done"
        self._elapsed = time.monotonic() - self._started
        self._detail  = detail
        self._stop_tick()
        self.add_class("-done")
        self.remove_class("-active", "-pending", "-fail")
        self._render()

    def set_fail(self, detail: str = "") -> None:
        self._state   = "fail"
        self._elapsed = time.monotonic() - self._started
        self._detail  = detail or "failed"
        self._stop_tick()
        self.add_class("-fail")
        self.remove_class("-active", "-pending", "-done")
        self._render()

    def reset(self) -> None:
        self.set_pending()

    # ── Internal ──────────────────────────────────────────────────────

    def _stop_tick(self) -> None:
        if self._tick_ref is not None:
            try:
                self._tick_ref.stop()
            except Exception:  # noqa: BLE001
                pass
            self._tick_ref = None

    def _tick(self) -> None:
        self._spin_idx = (self._spin_idx + 1) % len(SPINNER)
        self._render()

    def _render(self) -> None:
        state   = self._state
        label   = self._label
        detail  = self._detail
        elapsed = self._elapsed
        color   = STAGE_COLORS.get(self._name, "#888888")

        if state == "done":
            glyph       = f"[bold {color}]{GLYPH_DONE}[/]"
            name_markup = f"[dim]{label:<13}[/dim]"
            detail_mu   = f"[dim]{detail[:50]}[/dim]"
            elapsed_mu  = f"[dim]{elapsed:5.1f}s[/dim]"
        elif state == "fail":
            glyph       = f"[bold red]{GLYPH_FAIL}[/]"
            name_markup = f"[bold red]{label:<13}[/bold red]"
            detail_mu   = f"[red]{detail[:50]}[/red]"
            elapsed_mu  = f"[dim red]{elapsed:5.1f}s[/dim red]"
        elif state == "active":
            spin        = SPINNER[self._spin_idx]
            glyph       = f"[bold {color}]{spin}[/]"
            name_markup = f"[bold {color}]{label:<13}[/bold {color}]"
            detail_mu   = f"[{color}]{detail[:50]}[/{color}]"
            now         = time.monotonic() - self._started
            elapsed_mu  = f"[dim]{now:5.1f}s[/dim]"
        else:  # pending
            glyph       = f"[dim]{GLYPH_IDLE}[/dim]"
            name_markup = f"[dim]{label:<13}[/dim]"
            detail_mu   = ""
            elapsed_mu  = ""

        self.update(f"{glyph} {name_markup}  {detail_mu:<50}  {elapsed_mu}")


# ── AgentPipeline ─────────────────────────────────────────────────────

class AgentPipeline(Widget):
    """Vertical stack of AgentRow widgets, one per pipeline stage."""

    DEFAULT_ID = "agent_pipeline"

    def __init__(self, ensemble_mode: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self._ensemble   = ensemble_mode
        self._order      = ENSEMBLE_AGENT_ORDER if ensemble_mode else AGENT_ORDER
        self._rows: dict[str, AgentRow] = {}

    # ── Composition ───────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        for name in self._order:
            row = AgentRow(name, id=f"row_{name}", classes="agent_row -pending")
            self._rows[name] = row
            yield row

    # ── Public API ────────────────────────────────────────────────────

    def reset(self) -> None:
        for row in self._rows.values():
            row.reset()

    def set_ensemble_mode(self, enabled: bool) -> None:
        if enabled == self._ensemble:
            return
        self._ensemble = enabled
        self._order    = ENSEMBLE_AGENT_ORDER if enabled else AGENT_ORDER
        self._rows     = {}
        self.remove_children()
        for name in self._order:
            row = AgentRow(name, id=f"row_{name}", classes="agent_row -pending")
            self._rows[name] = row
            self.mount(row)

    def on_pipeline_event(
        self,
        type_: str,
        stage: str,
        detail: str,
        data: dict,
    ) -> None:
        """Route a PipelineEvent to the appropriate AgentRow."""
        # "synthesizer" and "ensemble" share the same slot depending on mode
        canonical = stage
        if stage == "synthesizer" and "ensemble" in self._rows:
            canonical = "ensemble"
        elif stage == "ensemble" and "synthesizer" in self._rows:
            canonical = "synthesizer"

        row = self._rows.get(canonical)
        if row is None:
            return

        if type_ == "agent_started":
            row.set_active(detail or "…")
        elif type_ == "agent_progress":
            row.set_progress(detail)
        elif type_ == "agent_finished":
            row.set_done(detail)
        elif type_ == "agent_failed":
            row.set_fail(detail)
        elif type_ in ("ensemble_provider_finished", "ensemble_providers_done"):
            # Update ensemble row detail with provider count
            count = len(data.get("providers", [])) if "providers" in data else ""
            suffix = f"provider done · {count}" if count else "provider done"
            row.set_progress(suffix)
