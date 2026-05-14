"""GET /health and GET /ready — liveness and readiness probes."""

from __future__ import annotations

from fastapi import APIRouter

from researchhq.api.schemas import HealthResponse
from researchhq.ensemble.orchestrator import build_provider

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — always returns 200 if the process is alive."""
    from researchhq import __version__ as ver
    return HealthResponse(status="ok", version=ver, providers_available=[])


@router.get("/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    """Readiness probe — checks which LLM providers are configured."""
    from researchhq import __version__ as ver

    available: list[str] = []
    for name in ["groq", "gemini", "openai", "anthropic", "ollama"]:
        if build_provider(name) is not None:
            available.append(name)

    if not available:
        from fastapi import HTTPException
        raise HTTPException(503, detail="No LLM providers are configured.")

    return HealthResponse(status="ready", version=ver, providers_available=available)
