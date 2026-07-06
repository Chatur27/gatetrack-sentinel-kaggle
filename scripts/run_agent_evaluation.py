from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import Settings  # noqa: E402
from backend.services.agent_evaluation import run_agent_evaluation  # noqa: E402
from backend.services.reviewer import build_review_provider  # noqa: E402


def main() -> int:
    settings = Settings.from_env()
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
    try:
        if reviewer.readiness().get("configured"):
            reviewer.prewarm()
        report = run_agent_evaluation(
            evaluation_path=settings.evaluation_path,
            policy_path=settings.policy_path,
            reviewer=reviewer,
            max_cases=settings.agent_evaluation_cases,
        )
    finally:
        reviewer.close()

    output_dir = REPO_ROOT / "artifacts" / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = output_dir / f"agent_{timestamp}.json"
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report.get("summary") or report.get("readiness"), indent=2))
    print(f"\nReport: {output_path}")
    if not report["available"]:
        print(report["message"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
