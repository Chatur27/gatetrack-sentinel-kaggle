from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.services.proof import tamper_demo, verify_after_json_round_trip  # noqa: E402


def _mark(value: bool) -> str:
    return "PASS" if value else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify a GateTrack Sentinel portable proof packet."
    )
    parser.add_argument("packet", type=Path, help="Path to a downloaded proof-packet JSON file.")
    parser.add_argument(
        "--tamper-demo",
        action="store_true",
        help="Also alter one copied field and confirm that verification fails.",
    )
    args = parser.parse_args()

    try:
        packet = json.loads(args.packet.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Unable to load packet: {exc}", file=sys.stderr)
        return 2

    result = verify_after_json_round_trip(packet)
    checks = result.get("checks", {})
    rows = [
        ("AUDIT CHAIN", checks.get("audit_chain", False)),
        ("AUDIT ROOT HASH", checks.get("audit_root_hash", False)),
        ("CASE HASH", checks.get("case_hash", False)),
        ("SOURCE MAP HASH", checks.get("source_map_hash", False)),
        ("CONFLICT MAP HASH", checks.get("conflict_map_hash", False)),
    ]
    if "loop_control_map_hash" in checks:
        rows.append(("LOOP CONTROL MAP HASH", checks["loop_control_map_hash"]))
    if "loop_runs_hash" in checks:
        rows.append(("LOOP RUNS HASH", checks["loop_runs_hash"]))
    rows.append(("PACKET HASH", checks.get("packet_hash", False)))
    print(f"Packet: {args.packet}")
    print(f"Canonical profile: {result.get('canonical_profile', 'unknown')}")
    print(f"Signature: {result.get('signature_status', 'unsigned')}")
    print("-" * 46)
    for label, passed in rows:
        print(f"{label:<28} {_mark(bool(passed))}")
    print("-" * 46)
    print(f"OVERALL{'':<21} {_mark(bool(result.get('verified')))}")

    if args.tamper_demo:
        demo = tamper_demo(deepcopy(packet))
        print()
        print("Tamper demonstration")
        print(f"Baseline verified: {_mark(bool(demo['baseline_verified']))}")
        print(f"Tampered packet rejected: {_mark(bool(demo['detected']))}")
        print(f"Mutation: {demo['mutation']}")
        print(f"Failed checks: {', '.join(demo['tampered_failed_checks']) or 'none'}")
        if not demo["detected"]:
            return 1

    return 0 if result.get("verified") else 1


if __name__ == "__main__":
    raise SystemExit(main())
