"""GET /api/v1/agents — list available pipeline agents and their configurations."""

from __future__ import annotations

from fastapi import APIRouter

from researchhq.api.schemas import AgentInfo, AgentsResponse
from researchhq.ensemble.pipeline_specs import PIPELINE_SPECS, select_slots

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.get("/agents", response_model=AgentsResponse)
async def list_agents() -> AgentsResponse:
    """Return all available pipeline agents and the slot sets per pipeline mode."""
    agents = [
        AgentInfo(
            id=spec.slot,
            name=spec.name,
            description=spec.description,
            slot=spec.slot,
            preferred_providers=spec.preferred_providers,
        )
        for spec in PIPELINE_SPECS.values()
    ]

    pipeline_modes = {
        "fast": select_slots("analytical", 2, False, False, "fast"),
        "balanced": select_slots("analytical", 3, False, False, "balanced"),
        "balanced_technical": select_slots("technical", 3, True, False, "balanced"),
        "deep": select_slots("analytical", 5, False, True, "deep"),
        "deep_technical": select_slots("technical", 5, True, True, "deep"),
    }

    return AgentsResponse(agents=agents, pipeline_modes=pipeline_modes)
