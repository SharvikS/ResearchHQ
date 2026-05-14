"""Pipeline event types.

Single typed payload (`PipelineEvent`) keeps the on_event(...) signature simple
and back-compatible with the previous StageEvent (which only had stage+detail).

Event types we emit:
- run_started, run_completed, run_failed, run_canceled
- agent_started, agent_progress, agent_finished, agent_failed
- source_found
- llm_call_started, llm_call_finished
- report_section_ready
- ensemble_provider_finished  — one parallel provider completed (or failed)
- ensemble_providers_done     — all parallel providers finished
- ensemble_claims_extracted   — claim extraction complete
- ensemble_consensus_ready    — consensus analysis complete
- ensemble_confidence_scored  — confidence score computed
- ensemble_disagreements_found— major disagreements detected
- ensemble_merge_done         — meta-synthesis finished

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
    # Query understanding
    "query_understood",
    # Differentiated slot pipeline events
    "slot_started",
    "slot_finished",
    "slot_failed",
    "slots_all_done",
    # Ensemble-specific events
    "ensemble_provider_finished",
    "ensemble_providers_done",
    "ensemble_claims_extracted",
    "ensemble_consensus_ready",
    "ensemble_confidence_scored",
    "ensemble_disagreements_found",
    "ensemble_merge_done",
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
