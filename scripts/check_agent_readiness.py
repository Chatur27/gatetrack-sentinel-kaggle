from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Settings  # noqa: E402
from backend.services.reviewer import build_review_provider  # noqa: E402


def _build(settings: Settings):
    return build_review_provider(
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


def main() -> int:
    settings = Settings.from_env()
    reviewer = _build(settings)
    try:
        readiness = reviewer.readiness()
        if readiness.get("configured") and settings.model_mode != "mock":
            readiness["prewarm"] = reviewer.prewarm()
            readiness.update(
                {
                    "mcp_warmed": reviewer.readiness().get("mcp_warmed", False),
                }
            )
        print(json.dumps(readiness, indent=2))
        return 0 if readiness.get("configured") or settings.model_mode == "mock" else 1
    finally:
        reviewer.close()


if __name__ == "__main__":
    raise SystemExit(main())
