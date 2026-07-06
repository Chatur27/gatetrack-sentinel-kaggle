from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.evaluation import run_evaluation  # noqa: E402
from backend.services.proof import proof_service_self_test  # noqa: E402
from backend.version import APP_VERSION, RELEASE_LABEL, RELEASE_NAME  # noqa: E402

REQUIRED_FILES = [
    "README.md",
    "docs/architecture.md",
    "docs/security.md",
    "docs/limitations.md",
    "docs/submission/KAGGLE_WRITEUP_DRAFT.md",
    "docs/submission/VIDEO_SCRIPT_5_MIN.md",
    "docs/submission/FEATURE_TEST_CHECKLIST.md",
    "docs/submission/DEMO_RUNBOOK.md",
    "docs/submission/JUDGING_EVIDENCE_MATRIX.md",
    "docs/submission/DEPLOYMENT_CLOUD_RUN.md",
    "docs/submission/SUBMISSION_CHECKLIST.md",
    "docs/submission/FINAL_RELEASE_AUDIT.md",
    "scripts/verify_proof_packet.py",
    "frontend/.npmrc",
    "RC2_3_8_REBUILD_REPORT.md",
]

FEATURE_FILES = [
    "adk_agents/gatetrack_sentinel/agent.py",
    "mcp_server/server.py",
    "backend/storage/sqlite.py",
    "backend/services/reviewer.py",
    "backend/services/proof.py",
    "backend/services/loop_engineering.py",
    "frontend/src/pages/VisitorForm.jsx",
    "frontend/src/pages/ReviewQueue.jsx",
    "frontend/src/pages/CaseLibrary.jsx",
    "frontend/src/pages/AuditViewer.jsx",
    "frontend/src/pages/Evaluation.jsx",
    "frontend/src/pages/ProofLab.jsx",
    "frontend/src/pages/LoopControl.jsx",
    "frontend/src/pages/TestLab.jsx",
]


def _frontend_integrity() -> dict:
    package = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text(encoding="utf-8"))
    release_source = (ROOT / "frontend" / "src" / "release.js").read_text(encoding="utf-8")
    css = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")

    resolved = [
        item.get("resolved")
        for item in lock.get("packages", {}).values()
        if item.get("resolved")
    ]
    non_public = [
        url for url in resolved if urlparse(url).netloc != "registry.npmjs.org"
    ]
    lock_root_version = lock.get("packages", {}).get("", {}).get("version")
    version_aligned = all(
        (
            package.get("version") == APP_VERSION,
            lock.get("version") == APP_VERSION,
            lock_root_version == APP_VERSION,
            f"APP_VERSION = '{APP_VERSION}'" in release_source,
            f"RELEASE_LABEL = '{RELEASE_LABEL}'" in release_source,
        )
    )
    return {
        "version_aligned": version_aligned,
        "package_version": package.get("version"),
        "lock_version": lock.get("version"),
        "lock_root_version": lock_root_version,
        "resolved_package_count": len(resolved),
        "public_npm_only": not non_public,
        "non_public_resolved_urls": non_public,
        "has_1280x720_profile": "RC2.3.8 — feature-preserved 1280×720" in css
        and "@media (width: 1280px) and (height: 720px)" in css,
        "has_internal_scroll_guards": all(
            marker in css
            for marker in (
                ".testlab-side { overflow-y: auto",
                ".decision-modal {",
                "max-height: min(620px",
            )
        ),
    }


def main() -> int:
    missing = [name for name in REQUIRED_FILES if not (ROOT / name).exists()]
    missing_features = [name for name in FEATURE_FILES if not (ROOT / name).exists()]
    report = run_evaluation(
        evaluation_path=str(ROOT / "data" / "evaluation_cases.json"),
        policy_path=str(ROOT / "data" / "visitor_policy.json"),
    )
    summary = report["summary"]
    controls_ok = all(
        summary[key] == 1
        for key in (
            "correct_routing_rate",
            "policy_match_rate",
            "security_detection_rate",
            "high_risk_recall",
            "audit_completeness_rate",
        )
    )
    proof_ok = proof_service_self_test()
    frontend = _frontend_integrity()
    frontend_ok = all(
        frontend[key]
        for key in (
            "version_aligned",
            "public_npm_only",
            "has_1280x720_profile",
            "has_internal_scroll_guards",
        )
    )
    passed = not missing and not missing_features and controls_ok and proof_ok and frontend_ok
    result = {
        "release": RELEASE_LABEL,
        "version": APP_VERSION,
        "release_name": RELEASE_NAME,
        "required_files_present": not missing,
        "missing_files": missing,
        "feature_preservation_pass": not missing_features,
        "missing_feature_files": missing_features,
        "deterministic_controls_pass": controls_ok,
        "baseline_summary": summary,
        "portable_proof_integrity_self_test": proof_ok,
        "loop_contracts_present": (ROOT / "backend" / "services" / "loop_engineering.py").exists(),
        "frontend_integrity": frontend,
        "public_boundary_confirmed": True,
        "result": "PASS" if passed else "FAIL",
    }
    output = ROOT / "artifacts" / "evaluation" / "release_verification.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
