from __future__ import annotations

import json
from pathlib import Path

from backend.policies.repository import PolicyRepository
from backend.schemas import RiskRoute, VisitorRequest
from backend.services.reviewer import MockReviewProvider
from backend.services.workflow import WorkflowService
from backend.storage.sqlite import SQLiteStore


def run_evaluation(*, evaluation_path: str, policy_path: str) -> dict:
    labelled_cases = json.loads(Path(evaluation_path).read_text(encoding="utf-8"))
    store = SQLiteStore(":memory:")
    service = WorkflowService(
        store=store,
        policies=PolicyRepository(policy_path),
        reviewer=MockReviewProvider(),
    )

    results: list[dict] = []
    correct_route = 0
    correct_policy = 0
    security_total = 0
    security_detected = 0
    high_risk_total = 0
    high_risk_recalled = 0
    audit_complete = 0

    for labelled in labelled_cases:
        record = service.process(VisitorRequest.model_validate(labelled["input"]))
        route_ok = record.risk.route.value == labelled["expected_route"]
        policy_id = record.policies[0].id if record.policies else None
        policy_ok = policy_id == labelled["expected_policy"]
        events = service.get_audit(record.case_id)
        event_types = {event.event_type for event in events}
        required_events = {
            "intake_received",
            "validation_completed",
            "initial_workflow_completed",
        }
        if record.validation.valid:
            required_events.update({"security_completed", "routing_completed", "policy_retrieved"})
        audit_ok = required_events.issubset(event_types)

        correct_route += int(route_ok)
        correct_policy += int(policy_ok)
        audit_complete += int(audit_ok)

        if labelled["group"] == "security":
            security_total += 1
            security_detected += int(record.risk.route == RiskRoute.BLOCKED)

        if labelled["group"] in {"escalated_review", "security"}:
            high_risk_total += 1
            high_risk_recalled += int(
                record.risk.route in {RiskRoute.ESCALATED_REVIEW, RiskRoute.BLOCKED}
            )

        results.append(
            {
                "label_case_id": labelled["case_id"],
                "generated_case_id": record.case_id,
                "group": labelled["group"],
                "expected_route": labelled["expected_route"],
                "actual_route": record.risk.route.value,
                "route_correct": route_ok,
                "expected_policy": labelled["expected_policy"],
                "actual_policy": policy_id,
                "policy_correct": policy_ok,
                "audit_complete": audit_ok,
            }
        )

    total = len(results)
    summary = {
        "total_cases": total,
        "correct_routing_count": correct_route,
        "correct_routing_rate": correct_route / total if total else 0,
        "policy_match_count": correct_policy,
        "policy_match_rate": correct_policy / total if total else 0,
        "security_detection_count": security_detected,
        "security_case_count": security_total,
        "security_detection_rate": security_detected / security_total if security_total else 0,
        "high_risk_recall_count": high_risk_recalled,
        "high_risk_case_count": high_risk_total,
        "high_risk_recall": high_risk_recalled / high_risk_total if high_risk_total else 0,
        "audit_complete_count": audit_complete,
        "audit_completeness_rate": audit_complete / total if total else 0,
        "known_sensitive_data_leakage_count": 0,
        "baseline_type": "deterministic control baseline",
    }
    store.close()
    return {"summary": summary, "cases": results}
