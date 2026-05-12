"""Pipeline event types.

Single typed payload (`PipelineEvent`) keeps the on_event(...) signature simple
and back-compatible with the previous StageEvent (which only had stage+detail).

Event types we emit:
- run_started, run_completed, run_failed, run_canceled
- agent_started, agent_progress, agent_finished, agent_failed
- source_found
- llm_call_started, llm_call_finished
- report_section_ready

Consumers can ignore types they don't care about. Any unrecognized event type is
treated as an agent_progress for legacy renderers (CLI's progress() display).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

EventType = Literal[
    "run_started",
    "run_completed",
    "run_failed",
    "run_canceled",
    "agent_started",
    "agent_progress",
    "agent_finished",
    "agent_failed",
    "source_found",
    "llm_call_started",
    "llm_call_finished",
    "report_section_ready",
]


@dataclass
class PipelineEvent:
    type: str  # one of EventType (str for forward-compat)
    stage: str = ""
    detail: str = ""
    data: dict[str, Any] = field(default_factory=dict)


# Back-compat alias: existing CLI renderer treats StageEvent as something with
# .stage and .detail. PipelineEvent has both and adds .type/.data.
StageEvent = PipelineEvent
