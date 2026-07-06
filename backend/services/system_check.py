from __future__ import annotations

from typing import Any

from backend.policies.repository import PolicyRepository
from backend.services.evaluation import run_evaluation
from backend.services.proof import proof_service_self_test
from backend.services.reviewer import ReviewProvider
from backend.storage.sqlite import SQLiteStore


def run_system_check(
    *,
    evaluation_path: str,
    policy_path: str,
    store: SQLiteStore,
    policies: PolicyRepository,
    reviewer: ReviewProvider,
    app_version: str,
    release_label: str,
    release_name: str,
) -> dict[str, Any]:
    baseline = run_evaluation(evaluation_path=evaluation_path, policy_path=policy_path)
    summary = baseline["summary"]
    readiness = reviewer.readiness()
    counts = store.summary()
    loop_summary = store.loop_summary()

    checks = [
        {
            "id": "release",
            "label": "Release identity",
            "status": "pass" if app_version and release_label and release_name else "fail",
            "detail": f"Backend reports {release_label} · v{app_version} — {release_name}.",
            "required": True,
        },
        {
            "id": "api",
            "label": "API runtime",
            "status": "pass",
            "detail": "FastAPI self-test endpoint responded.",
            "required": True,
        },
        {
            "id": "storage",
            "label": "SQLite evidence store",
            "status": "pass",
            "detail": f"Storage available with {counts['total']} synthetic case(s).",
            "required": True,
        },
        {
            "id": "policies",
            "label": "Read-only policy corpus",
            "status": "pass" if policies.section_count >= 1 else "fail",
            "detail": f"{policies.section_count} policy section(s) loaded.",
            "required": True,
        },
        {
            "id": "routing",
            "label": "Deterministic routing",
            "status": "pass" if summary["correct_routing_rate"] == 1 else "fail",
            "detail": f"{summary['correct_routing_count']}/{summary['total_cases']} routes correct.",
            "required": True,
        },
        {
            "id": "security",
            "label": "Pre-model security gate",
            "status": "pass" if summary["security_detection_rate"] == 1 else "fail",
            "detail": "Defined prompt-injection cases were blocked before model review.",
            "required": True,
        },
        {
            "id": "audit",
            "label": "Audit completeness",
            "status": "pass" if summary["audit_completeness_rate"] == 1 else "fail",
            "detail": f"Audit evidence completeness: {summary['audit_completeness_rate'] * 100:.0f}%.",
            "required": True,
        },
        {
            "id": "proof",
            "label": "Proof-carrying evidence",
            "status": "pass" if proof_service_self_test() else "fail",
            "detail": "Portable SHA-256 packet, JSON round-trip, audit chain and tamper-detection checks passed.",
            "required": True,
        },
        {
            "id": "loops",
            "label": "Bounded loop contracts",
            "status": "pass" if loop_summary["bounded_rate"] == 1 and loop_summary["unauthorized_tool_attempts"] == 0 else "fail",
            "detail": (
                f"{loop_summary['bounded_runs']}/{loop_summary['total_runs']} recorded runs bounded; "
                f"{loop_summary['unauthorized_tool_attempts']} unauthorised tool execution(s)."
            ),
            "required": True,
        },
        {
            "id": "agent",
            "label": "ADK · MCP · Gemini",
            "status": "pass" if readiness.get("live_model_available") else "warning",
            "detail": (
                "Live agent configured; deterministic authority remains locked."
                if readiness.get("live_model_available")
                else "Live agent unavailable; safe deterministic fallback remains operational."
            ),
            "required": False,
        },
        {
            "id": "mcp",
            "label": "MCP warm connection",
            "status": "pass" if readiness.get("mcp_warmed") else "warning",
            "detail": (
                "Read-only MCP connection is warm and reusable."
                if readiness.get("mcp_warmed")
                else "MCP will initialise lazily or fallback safely."
            ),
            "required": False,
        },
    ]
    required_passed = all(item["status"] == "pass" for item in checks if item["required"])
    return {
        "overall": "pass" if required_passed else "fail",
        "release": release_label,
        "version": app_version,
        "release_name": release_name,
        "checks": checks,
        "case_counts": counts,
        "agent": readiness,
        "baseline_summary": summary,
        "loop_summary": loop_summary,
    }
