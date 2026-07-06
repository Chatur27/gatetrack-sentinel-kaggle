from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(REPO_ROOT / ".env")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class Settings:
    environment: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    db_path: str = str(REPO_ROOT / "runtime" / "gatetrack_sentinel.db")
    policy_path: str = str(REPO_ROOT / "data" / "visitor_policy.json")
    evaluation_path: str = str(REPO_ROOT / "data" / "evaluation_cases.json")
    model_mode: str = "mock"
    model_name: str = "gemini-2.5-flash"
    model_timeout_seconds: float = 18.0
    model_max_attempts: int = 2
    mcp_connect_timeout_seconds: float = 12.0
    mcp_reuse_enabled: bool = True
    mcp_prewarm_enabled: bool = True
    model_thinking_budget: int = 0
    circuit_breaker_seconds: float = 90.0
    model_fallback_enabled: bool = True
    agent_evaluation_cases: int = 5
    adk_app_name: str = "gatetrack_sentinel_api"
    adk_user_id: str = "gatetrack_demo_user"
    log_level: str = "INFO"

    @property
    def gemini_key_configured(self) -> bool:
        return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))

    @classmethod
    def from_env(cls, *, db_path: str | None = None) -> Settings:
        resolved_db = db_path or os.getenv(
            "GTS_DB_PATH", str(REPO_ROOT / "runtime" / "gatetrack_sentinel.db")
        )
        if resolved_db != ":memory:":
            db_file = Path(resolved_db)
            if not db_file.is_absolute():
                db_file = REPO_ROOT / db_file
            db_file.parent.mkdir(parents=True, exist_ok=True)
            resolved_db = str(db_file)

        return cls(
            environment=os.getenv("GTS_ENV", "development"),
            api_host=os.getenv("GTS_API_HOST", "127.0.0.1"),
            api_port=int(os.getenv("GTS_API_PORT", "8000")),
            db_path=resolved_db,
            policy_path=os.getenv("GTS_POLICY_PATH", str(REPO_ROOT / "data" / "visitor_policy.json")),
            evaluation_path=os.getenv(
                "GTS_EVALUATION_PATH", str(REPO_ROOT / "data" / "evaluation_cases.json")
            ),
            model_mode=os.getenv("GTS_MODEL_MODE", "mock").lower(),
            model_name=os.getenv("GTS_MODEL", "gemini-2.5-flash"),
            model_timeout_seconds=float(os.getenv("GTS_MODEL_TIMEOUT_SECONDS", "18")),
            model_max_attempts=max(1, int(os.getenv("GTS_MODEL_MAX_ATTEMPTS", "2"))),
            mcp_connect_timeout_seconds=float(
                os.getenv("GTS_MCP_CONNECT_TIMEOUT_SECONDS", "12")
            ),
            mcp_reuse_enabled=_env_bool("GTS_MCP_REUSE_ENABLED", True),
            mcp_prewarm_enabled=_env_bool("GTS_MCP_PREWARM_ENABLED", True),
            model_thinking_budget=int(os.getenv("GTS_MODEL_THINKING_BUDGET", "0")),
            circuit_breaker_seconds=float(
                os.getenv("GTS_AGENT_CIRCUIT_BREAKER_SECONDS", "90")
            ),
            model_fallback_enabled=_env_bool("GTS_MODEL_FALLBACK_ENABLED", True),
            agent_evaluation_cases=max(1, int(os.getenv("GTS_AGENT_EVALUATION_CASES", "5"))),
            adk_app_name=os.getenv("GTS_ADK_APP_NAME", "gatetrack_sentinel_api"),
            adk_user_id=os.getenv("GTS_ADK_USER_ID", "gatetrack_demo_user"),
            log_level=os.getenv("GTS_LOG_LEVEL", "INFO").upper(),
        )
