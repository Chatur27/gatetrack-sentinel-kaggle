from pathlib import Path

from backend.services.evaluation import run_evaluation

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_deterministic_evaluation_baseline():
    report = run_evaluation(
        evaluation_path=str(REPO_ROOT / "data" / "evaluation_cases.json"),
        policy_path=str(REPO_ROOT / "data" / "visitor_policy.json"),
    )
    summary = report["summary"]
    assert summary["total_cases"] == 30
    assert summary["correct_routing_rate"] == 1.0
    assert summary["policy_match_rate"] == 1.0
    assert summary["security_detection_rate"] == 1.0
    assert summary["high_risk_recall"] == 1.0
    assert summary["audit_completeness_rate"] == 1.0
