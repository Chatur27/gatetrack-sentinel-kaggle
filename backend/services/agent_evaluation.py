from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from backend.policies.repository import PolicyRepository
from backend.schemas import ReplayScenario, VisitorRequest
from backend.services.proof import replay_case
from backend.services.reviewer import ReviewProvider
from backend.services.workflow import WorkflowService
from backend.storage.sqlite import SQLiteStore


def _select_diverse_cases(labelled_cases: list[dict[str, Any]], max_cases: int) -> list[dict[str, Any]]:
    eligible = [
        item
        for item in labelled_cases
        if item.get("expected_route") not in {"blocked", "returned_for_correction"}
    ]
    preferred = [
        ("low_risk", "VP-1.1"),
        ("human_review", "VP-2.1"),
        ("human_review", "VP-5.1"),
        ("human_review", "VP-4.3"),
        ("escalated_review", "VP-4.3"),
    ]
    selected: list[dict[str, Any]] = []
    used_ids: set[str] = set()
    for route, policy in preferred:
        match = next(
            (
                item
                for item in eligible
                if item.get("expected_route") == route
                and item.get("expected_policy") == policy
                and item.get("case_id") not in used_ids
            ),
            None,
        )
        if match:
            selected.append(match)
            used_ids.add(match["case_id"])
            if len(selected) >= max_cases:
                return selected
    for item in eligible:
        if item.get("case_id") in used_ids:
            continue
        selected.append(item)
        if len(selected) >= max_cases:
            break
    return selected


def _health_status(rate: float) -> str:
    if rate >= 0.999:
        return "healthy"
    if rate >= 0.6:
        return "partial"
    if rate > 0:
        return "degraded"
    return "unavailable"


def run_agent_evaluation(
    *,
    evaluation_path: str,
    policy_path: str,
    reviewer: ReviewProvider,
    max_cases: int = 5,
) -> dict[str, Any]:
    readiness = reviewer.readiness()
    if not readiness.get("live_model_available"):
        return {
            "available": False,
            "readiness": readiness,
            "summary": None,
            "cases": [],
            "resilience_checks": [],
            "message": "Live ADK/Gemini evaluation requires installed dependencies and an API key.",
        }

    labelled_cases = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
    eligible = _select_diverse_cases(labelled_cases, max_cases)
    policy_repository = PolicyRepository(policy_path)

    store = SQLiteStore(":memory:")
    service = WorkflowService(
        store=store,
        policies=policy_repository,
        reviewer=reviewer,
    )

    results: list[dict[str, Any]] = []
    records = []
    structured_valid = 0
    route_consistent = 0
    grounding_valid = 0
    mcp_eligible_count = 0
    live_success_count = 0
    live_success_with_mcp = 0
    unexpected_fallback_count = 0
    total_latency = 0
    live_success_latency = 0
    fallback_reasons: Counter[str] = Counter()

    try:
        for labelled in eligible:
            record = service.process(VisitorRequest.model_validate(labelled["input"]))
            records.append(record)
            review = record.review
            if review is None:
                results.append(
                    {
                        "label_case_id": labelled["case_id"],
                        "generated_case_id": record.case_id,
                        "classification": "missing_review",
                        "route": record.risk.route.value,
                        "expected_policy": labelled.get("expected_policy"),
                    }
                )
                continue

            expected_policy = labelled.get("expected_policy")
            grounded = review.grounding_valid and (
                expected_policy is None or expected_policy in review.grounding_policy_ids
            )
            structured_valid += int(review.structured_output_valid)
            route_consistent += int(review.route_consistent)
            grounding_valid += int(grounded)
            total_latency += review.latency_ms
            mcp_eligible_count += 1

            live_success = bool(review.model_invoked and not review.fallback_used)
            if live_success:
                live_success_count += 1
                live_success_latency += review.latency_ms
                live_success_with_mcp += int(bool(review.tool_calls))
                classification = "live_success"
            else:
                unexpected_fallback_count += 1
                reason = (review.fallback_reason or "unknown").strip().lower().replace(" ", "_")
                fallback_reasons[reason] += 1
                classification = "unexpected_fallback"

            results.append(
                {
                    "label_case_id": labelled["case_id"],
                    "generated_case_id": record.case_id,
                    "classification": classification,
                    "route": record.risk.route.value,
                    "expected_route": labelled.get("expected_route"),
                    "expected_policy": expected_policy,
                    "grounding_policy_ids": review.grounding_policy_ids,
                    "structured_output_valid": review.structured_output_valid,
                    "route_consistent": review.route_consistent,
                    "grounding_valid": grounded,
                    "mcp_tool_calls": [trace.tool_name for trace in review.tool_calls],
                    "fallback_used": review.fallback_used,
                    "latency_ms": review.latency_ms,
                    "provider": review.provider,
                    "model_name": review.model_name,
                    "fallback_reason": review.fallback_reason,
                    "failure_stage": review.failure_stage,
                    "attempt_count": review.attempt_count,
                    "retry_count": review.retry_count,
                    "repair_used": review.repair_used,
                    "mcp_connection_reused": review.mcp_connection_reused,
                }
            )

        resilience_checks: list[dict[str, Any]] = []
        blocked_label = next(
            (item for item in labelled_cases if item.get("expected_route") == "blocked"), None
        )
        if blocked_label:
            blocked_record = service.process(
                VisitorRequest.model_validate(blocked_label["input"])
            )
            bypass_passed = blocked_record.risk.route.value == "blocked" and blocked_record.review is None
            resilience_checks.append(
                {
                    "id": "pre_model_security_bypass",
                    "label": "Expected security bypass",
                    "status": "pass" if bypass_passed else "fail",
                    "detail": "Unsafe input was blocked without invoking the model."
                    if bypass_passed
                    else "Unsafe input did not follow the required pre-model path.",
                    "counts_against_live_reliability": False,
                }
            )

        if records:
            outage = replay_case(records[0], ReplayScenario.MODEL_OUTAGE, policy_repository)
            outage_passed = bool(
                outage["simulated"]["model_path"]["authoritative_route_preserved"]
                and not outage["simulated"]["model_path"]["invoked"]
            )
            resilience_checks.append(
                {
                    "id": "model_outage_route_preserved",
                    "label": "Expected outage recovery",
                    "status": "pass" if outage_passed else "fail",
                    "detail": "The deterministic route survived a simulated model outage."
                    if outage_passed
                    else "The route was not preserved during outage replay.",
                    "counts_against_live_reliability": False,
                }
            )
    finally:
        store.close()

    total = len(results)
    live_success_rate = live_success_count / total if total else 0
    mcp_success_rate = live_success_with_mcp / live_success_count if live_success_count else 0
    mcp_coverage_rate = live_success_with_mcp / mcp_eligible_count if mcp_eligible_count else 0
    resilience_pass_count = sum(
        1 for item in resilience_checks if item.get("status") == "pass"
    )
    resilience_rate = (
        resilience_pass_count / len(resilience_checks) if resilience_checks else 0
    )
    health = _health_status(live_success_rate)

    summary = {
        "total_cases": total,
        "live_eligible_cases": total,
        "live_success_count": live_success_count,
        "live_success_rate": live_success_rate,
        "unexpected_fallback_count": unexpected_fallback_count,
        "unexpected_fallback_rate": unexpected_fallback_count / total if total else 0,
        "fallback_breakdown": dict(sorted(fallback_reasons.items())),
        "structured_output_rate": structured_valid / total if total else 0,
        "route_consistency_rate": route_consistent / total if total else 0,
        "grounding_accuracy_rate": grounding_valid / total if total else 0,
        "mcp_tool_usage_rate": mcp_coverage_rate,
        "mcp_usage_among_live_success_rate": mcp_success_rate,
        "fallback_rate": unexpected_fallback_count / total if total else 0,
        "average_latency_ms": round(total_latency / total) if total else 0,
        "average_live_success_latency_ms": round(live_success_latency / live_success_count)
        if live_success_count
        else 0,
        "resilience_pass_count": resilience_pass_count,
        "resilience_check_count": len(resilience_checks),
        "resilience_pass_rate": resilience_rate,
        "health_status": health,
        "provider": readiness.get("provider"),
        "model": readiness.get("model"),
        "evaluation_type": "diverse live-eligible ADK + MCP + Gemini reliability check",
        "interpretation": (
            "Fallbacks shown here are unexpected failures among model-eligible cases. "
            "Intentional security bypass and model-outage recovery are reported separately."
        ),
    }
    return {
        "available": True,
        "readiness": readiness,
        "summary": summary,
        "cases": results,
        "resilience_checks": resilience_checks,
        "message": "Live-agent reliability and separate resilience checks completed.",
    }
