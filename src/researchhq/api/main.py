"""ResearchHQ FastAPI application factory.

Run the API server:
  researchhq-api              (via pyproject.toml script)
  uvicorn researchhq.api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from researchhq.api import db
from researchhq.api.routes import agents, health, logs, query
from researchhq.api.ws import ws_endpoint

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="ResearchHQ API",
        description=(
            "Multi-agent research system. Submit a query and receive a "
            "confidence-scored, cross-verified answer synthesized from "
            "parallel independent AI pipelines."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS — wide open for local dev; lock down in production via env var
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # REST routes
    app.include_router(health.router)
    app.include_router(query.router)
    app.include_router(agents.router)
    app.include_router(logs.router)

    # WebSocket progress streaming
    @app.websocket("/ws/{query_id}")
    async def websocket_route(
        query_id: str,
        websocket: WebSocket,
        api_key: str | None = Query(None),
    ) -> None:
        await ws_endpoint(query_id, websocket, api_key=api_key)

    @app.on_event("startup")
    async def on_startup() -> None:
        db.init_db()
        from researchhq.api.auth import _RATE_LIMIT_RPM, _REQUIRE_AUTH
        auth_msg = "enabled (X-API-Key header)" if _REQUIRE_AUTH else "disabled — set RHQ_REQUIRE_AUTH=true to enable"
        logger.info("ResearchHQ API started. DB at %s", db.get_db_path())
        logger.info("Auth: %s | Rate limit: %d req/min", auth_msg, _RATE_LIMIT_RPM)

    return app


# Module-level app instance consumed by uvicorn
app = create_app()


def serve() -> None:
    """Entry point for `researchhq-api` CLI command."""
    import uvicorn
    uvicorn.run(
        "researchhq.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )
