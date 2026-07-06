from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.router import router
from backend.config import Settings
from backend.policies.repository import PolicyRepository
from backend.services.reviewer import build_review_provider
from backend.services.workflow import WorkflowService
from backend.storage.sqlite import SQLiteStore
from backend.version import APP_VERSION, RELEASE_LABEL, RELEASE_NAME


def create_app(*, db_path: str | None = None) -> FastAPI:
    settings = Settings.from_env(db_path=db_path)
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

    store = SQLiteStore(settings.db_path)
    policies = PolicyRepository(settings.policy_path)
    reviewer = build_review_provider(
        model_mode=settings.model_mode,
        model_name=settings.model_name,
        timeout_seconds=settings.model_timeout_seconds,
        max_attempts=settings.model_max_attempts,
        fallback_enabled=settings.model_fallback_enabled,
        app_name=settings.adk_app_name,
        user_id=settings.adk_user_id,
        mcp_connect_timeout_seconds=settings.mcp_connect_timeout_seconds,
        mcp_reuse_enabled=settings.mcp_reuse_enabled,
        mcp_prewarm_enabled=settings.mcp_prewarm_enabled,
        thinking_budget=settings.model_thinking_budget,
        circuit_breaker_seconds=settings.circuit_breaker_seconds,
    )
    service = WorkflowService(store=store, policies=policies, reviewer=reviewer)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        prewarm = reviewer.prewarm()
        logging.getLogger(__name__).info("Agent prewarm status: %s", prewarm)
        try:
            yield
        finally:
            reviewer.close()
            store.close()

    application = FastAPI(
        title="GateTrack Sentinel API",
        version=APP_VERSION,
        lifespan=lifespan,
        description=(
            "Synthetic, human-governed visitor risk triage demonstration with deterministic "
            "controls, Google ADK, a read-only MCP policy server, Gemini, safe fallback, tamper-evident proof packets, source-confidence mapping, deterministic replay, and bounded loop contracts with explicit stop states. "
            "Not a production legal, security, or compliance decision system."
        ),
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.state.settings = settings
    application.state.workflow_service = service
    application.state.review_provider = reviewer
    application.include_router(router)

    @application.get("/")
    def root() -> dict:
        return {
            "name": "GateTrack Sentinel",
            "version": APP_VERSION,
            "release": RELEASE_LABEL,
            "release_name": RELEASE_NAME,
            "status": "Feature-preserved submission-clean release running",
            "docs": "/docs",
            "agent": reviewer.readiness(),
            "disclaimer": "Synthetic educational demonstration only.",
        }

    return application


app = create_app()


if __name__ == "__main__":
    settings = app.state.settings
    uvicorn.run("backend.main:app", host=settings.api_host, port=settings.api_port, reload=False)
