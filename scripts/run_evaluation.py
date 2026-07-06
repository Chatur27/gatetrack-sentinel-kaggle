from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.evaluation import run_evaluation  # noqa: E402


def pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def main() -> int:
    report = run_evaluation(
        evaluation_path=str(REPO_ROOT / "data" / "evaluation_cases.json"),
        policy_path=str(REPO_ROOT / "data" / "visitor_policy.json"),
    )
    output_dir = REPO_ROOT / "artifacts" / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_dir / f"baseline_{timestamp}.json"
    md_path = output_dir / f"baseline_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    summary = report["summary"]
    markdown = f"""# GateTrack Sentinel deterministic baseline

Generated: {timestamp}

| Metric | Result |
|---|---:|
| Cases | {summary['total_cases']} |
| Correct routing | {summary['correct_routing_count']}/{summary['total_cases']} ({pct(summary['correct_routing_rate'])}) |
| Policy match | {summary['policy_match_count']}/{summary['total_cases']} ({pct(summary['policy_match_rate'])}) |
| Security detection | {summary['security_detection_count']}/{summary['security_case_count']} ({pct(summary['security_detection_rate'])}) |
| High-risk recall | {summary['high_risk_recall_count']}/{summary['high_risk_case_count']} ({pct(summary['high_risk_recall'])}) |
| Audit completeness | {summary['audit_complete_count']}/{summary['total_cases']} ({pct(summary['audit_completeness_rate'])}) |
| Known sensitive-data leakage | {summary['known_sensitive_data_leakage_count']} |

This is the deterministic control baseline. Run scripts/run_agent_evaluation.py separately to evaluate live ADK/Gemini schema validity, route consistency, MCP usage, grounding, fallback rate and latency.
"""
    md_path.write_text(markdown, encoding="utf-8")

    print(json.dumps(summary, indent=2))
    print(f"\nJSON report: {json_path}")
    print(f"Markdown report: {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
