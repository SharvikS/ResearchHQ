"""Live multi-agent pipeline visualization.

One row per agent. Each row tracks state (pending → active → done | fail),
elapsed time, and a free-form status note ("12 sources", "1.4k tokens", …).

Driven by `PipelineEvent`s from researchhq.events; an event handler outside
this widget updates the rows. The widget itself is purely presentational.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import Label


AGENT_ORDER = [
    "planner", "searcher", "source_ranker", "fetcher",
    "extractor", "synthesizer", "verifier", "formatter",
]

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


@dataclass
class _AgentRowState:
    name: str
    status: str = "pending"   # pending | active | done | fail
    detail: str = "queued"
    started_at: float | None = None
    finished_at: float | None = None
    extra: dict = field(default_factory=dict)


class AgentRow(Label):
    """Single line: ● <agent>   <status note>   <elapsed>"""

    def __init__(self, name: str, **kwargs) -> None:
        self._state = _AgentRowState(name=name)
        self._spin_idx = 0
        super().__init__(self._compose_text(), classes="agent_row -pending", **kwargs)

    def on_mount(self) -> None:
        self.set_interval(0.08, self._spin)

    def update_state(
        self, *, status: str | None = None, detail: str | None = None,
        started_at: float | None = None, finished_at: float | None = None,
    ) -> None:
        s = self._state
        if status is not None:
            s.status = status
            self.remove_class("-pending", "-active", "-done", "-fail")
            self.add_class(f"-{status}")
        if detail is not None:
            s.detail = detail
        if started_at is not None:
            s.started_at = started_at
        if finished_at is not None:
            s.finished_at = finished_at
        self.update(self._compose_text())

    def _spin(self) -> None:
        self._spin_idx = (self._spin_idx + 1) % len(SPINNER)
        if self._state.status == "active":
            self.update(self._compose_text())

    def _glyph(self) -> str:
        s = self._state.status
        if s == "active":
            return SPINNER[self._spin_idx]
        if s == "done":
            return "✓"
        if s == "fail":
            return "✗"
        return "·"

    def _elapsed(self) -> str:
        s = self._state
        if s.started_at is None:
            return ""
        end = s.finished_at or time.monotonic()
        return f"{end - s.started_at:.1f}s"

    def _compose_text(self) -> Text:
        s = self._state
        line = Text()
        line.append(f" {self._glyph()}  ")
        line.append(f"{s.name:<14}", style="bold")
        line.append("  ")
        line.append(s.detail or "—")
        line.append(f"   {self._elapsed():>6}")
        return line


class AgentPipeline(Vertical):
    """Container holding one AgentRow per pipeline stage."""

    DEFAULT_ID = "agent_pipeline"

    def __init__(self, **kwargs) -> None:
        kwargs.setdefault("id", "agent_pipeline")
        super().__init__(**kwargs)
        self._rows: dict[str, AgentRow] = {}

    def compose(self):
        for name in AGENT_ORDER:
            row = AgentRow(name=name, id=f"row_{name}")
            self._rows[name] = row
            yield row

    def reset(self) -> None:
        for name, row in self._rows.items():
            row._state = _AgentRowState(name=name)
            row.remove_class("-active", "-done", "-fail")
            row.add_class("-pending")
            row.update(row._compose_text())

    def on_pipeline_event(self, *, type_: str, stage: str, detail: str, data: dict) -> None:
        """Hook from the running pipeline. Translates events into row updates."""
        row = self._rows.get(stage)
        if not row:
            return
        if type_ == "agent_started":
            row.update_state(status="active", detail=detail or "running",
                             started_at=time.monotonic())
        elif type_ == "agent_finished":
            row.update_state(status="done", detail=detail or "complete",
                             finished_at=time.monotonic())
