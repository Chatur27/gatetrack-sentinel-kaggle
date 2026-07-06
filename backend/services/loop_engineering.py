from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from backend.schemas.loops import LoopAttempt, LoopContract, LoopRunRecord
from backend.storage.sqlite import SQLiteStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(value: Any) -> str:
    try:
        payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
    except TypeError:
        payload = repr(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


LOOP_CONTRACTS: dict[str, LoopContract] = {
    "intake_validation": LoopContract(
        name="intake_validation",
        label="Intake validation loop",
        agent_name="Intake Validator",
        trigger_types=["visitor_request_received"],
        goal="Produce a complete schema-valid visitor request or return it for correction.",
        permitted_tools=["validate_operational_fields"],
        verification_checks=["mandatory fields present", "schema types valid"],
        max_attempts=1,
        timeout_ms=2_000,
        no_progress_limit=1,
        terminal_states=["success", "returned_for_correction", "stalled"],
        consequence_boundary="Validation may request correction but cannot approve access.",
    ),
    "pre_model_security": LoopContract(
        name="pre_model_security",
        label="Pre-model security loop",
        agent_name="Security Gate",
        trigger_types=["validation_passed"],
        goal="Classify unsafe or manipulative input before any model invocation.",
        permitted_tools=["scan_input"],
        verification_checks=["security status assigned", "finding codes recorded"],
        max_attempts=1,
        timeout_ms=2_000,
        no_progress_limit=1,
        terminal_states=["success", "blocked", "stalled"],
        consequence_boundary="A blocked result bypasses Gemini and cannot be self-overridden.",
    ),
    "deterministic_routing": LoopContract(
        name="deterministic_routing",
        label="Deterministic routing loop",
        agent_name="Risk and Policy Router",
        trigger_types=["security_result_available"],
        goal="Produce the authoritative score, route and controlled policy references.",
        permitted_tools=["calculate_risk", "select_policy"],
        verification_checks=["score within bounds", "route present", "policy IDs controlled"],
        max_attempts=1,
        timeout_ms=2_000,
        no_progress_limit=1,
        terminal_states=["success", "blocked", "escalated", "stalled"],
        consequence_boundary="The route and score are deterministic and cannot be changed by the model.",
    ),
    "grounded_agent_review": LoopContract(
        name="grounded_agent_review",
        label="Grounded agent review loop",
        agent_name="ADK Review Agent",
        trigger_types=["route_and_policy_ready"],
        goal="Generate one policy-grounded structured explanation while preserving the locked route.",
        permitted_tools=[
            "google_adk_runner",
            "get_visitor_policy",
            "search_policy",
            "get_access_rule",
            "get_operating_hours",
            "get_required_documents",
            "safe_deterministic_fallback",
        ],
        verification_checks=[
            "structured output valid",
            "route consistent",
            "grounding policy IDs valid",
            "maximum attempts respected",
        ],
        max_attempts=2,
        timeout_ms=18_000,
        no_progress_limit=1,
        terminal_states=["success", "safe_fallback", "blocked", "exhausted", "stalled"],
        consequence_boundary="The model is advisory; deterministic route and human authority remain final.",
    ),
    "human_authority": LoopContract(
        name="human_authority",
        label="Human authority loop",
        agent_name="Authorised Human Gate",
        trigger_types=["sensitive_case_ready", "reviewer_decision_submitted"],
        goal="Obtain and record an authorised human outcome for a consequential case.",
        permitted_tools=["record_human_decision"],
        verification_checks=["reviewer present", "reason present", "decision allowed"],
        max_attempts=1,
        timeout_ms=120_000,
        no_progress_limit=1,
        terminal_states=["escalated", "approved", "rejected", "more_information_requested", "no_op"],
        consequence_boundary="Only a named human may approve, reject or request information.",
    ),
    "evidence_recording": LoopContract(
        name="evidence_recording",
        label="Evidence recording loop",
        agent_name="Evidence Recorder",
        trigger_types=["workflow_state_changed", "human_decision_recorded"],
        goal="Persist the case, audit evidence and bounded-loop outcome exactly once.",
        permitted_tools=["save_case", "append_audit", "build_proof_packet", "verify_proof_packet"],
        verification_checks=["case persisted", "audit event written", "duplicate-safe"],
        max_attempts=2,
        timeout_ms=5_000,
        no_progress_limit=1,
        terminal_states=["success", "duplicate_no_op", "stalled", "exhausted"],
        consequence_boundary="Evidence recording cannot alter the authoritative decision.",
    ),
}


class LoopEngine:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def contracts(self) -> list[LoopContract]:
        return list(LOOP_CONTRACTS.values())

    def contract(self, name: str) -> LoopContract:
        try:
            return LOOP_CONTRACTS[name]
        except KeyError as exc:
            raise KeyError(f"Unknown loop contract: {name}") from exc

    def execute_once(
        self,
        *,
        contract_name: str,
        case_id: str,
        trigger_type: str,
        trigger_id: str,
        tool_name: str,
        operation: Callable[[], Any],
        verifier: Callable[[Any], tuple[bool, dict[str, Any]]],
        evidence_references: list[str] | None = None,
        failure_terminal_state: str = "stalled",
        failure_reason: str = "verification failed",
    ) -> tuple[Any, LoopRunRecord]:
        contract = self.contract(contract_name)
        start_time = utc_now()
        start = perf_counter()
        unauthorized = [] if tool_name in contract.permitted_tools else [tool_name]
        if unauthorized:
            ended = utc_now()
            run = LoopRunRecord(
                run_id=f"LOOP-{uuid4().hex.upper()}",
                case_id=case_id,
                loop_name=contract.name,
                agent_name=contract.agent_name,
                trigger_type=trigger_type,
                trigger_id=trigger_id,
                goal=contract.goal,
                permitted_tools=contract.permitted_tools,
                attempts=[],
                attempt_number=0,
                max_attempts=contract.max_attempts,
                tools_used=[],
                verification_result={"allowed_tool": False},
                evidence_references=evidence_references or [],
                decision="stop",
                terminal_state="blocked",
                stop_reason="unauthorised tool blocked before execution",
                started_at=start_time,
                ended_at=ended,
                elapsed_ms=max(0, int((perf_counter() - start) * 1000)),
                bounded=True,
                unauthorized_tool_attempts=unauthorized,
            )
            self.store.save_loop_run(run)
            raise PermissionError(f"Tool {tool_name!r} is not permitted for loop {contract_name!r}.")

        try:
            result = operation()
            verified, verification_result = verifier(result)
            elapsed = max(0, int((perf_counter() - start) * 1000))
            fingerprint = _fingerprint(result)
            decision = "pass" if verified else "stop"
            terminal = "success" if verified else failure_terminal_state
            stop_reason = "goal verified" if verified else failure_reason
            attempt = LoopAttempt(
                attempt_number=1,
                tool_used=tool_name,
                verification_passed=verified,
                verification_result=verification_result,
                progress_fingerprint=fingerprint,
                decision=decision,
                elapsed_ms=elapsed,
            )
        except Exception as exc:
            elapsed = max(0, int((perf_counter() - start) * 1000))
            verification_result = {"exception": type(exc).__name__, "message": str(exc)}
            attempt = LoopAttempt(
                attempt_number=1,
                tool_used=tool_name,
                verification_passed=False,
                verification_result=verification_result,
                progress_fingerprint=_fingerprint(verification_result),
                decision="stop",
                elapsed_ms=elapsed,
            )
            run = LoopRunRecord(
                run_id=f"LOOP-{uuid4().hex.upper()}",
                case_id=case_id,
                loop_name=contract.name,
                agent_name=contract.agent_name,
                trigger_type=trigger_type,
                trigger_id=trigger_id,
                goal=contract.goal,
                permitted_tools=contract.permitted_tools,
                attempts=[attempt],
                attempt_number=1,
                max_attempts=contract.max_attempts,
                tools_used=[tool_name],
                verification_result=verification_result,
                evidence_references=evidence_references or [],
                decision="stop",
                terminal_state="stalled",
                stop_reason="operation raised an exception",
                started_at=start_time,
                ended_at=utc_now(),
                elapsed_ms=elapsed,
                bounded=True,
                progress_fingerprint=attempt.progress_fingerprint,
            )
            self.store.save_loop_run(run)
            raise

        run = LoopRunRecord(
            run_id=f"LOOP-{uuid4().hex.upper()}",
            case_id=case_id,
            loop_name=contract.name,
            agent_name=contract.agent_name,
            trigger_type=trigger_type,
            trigger_id=trigger_id,
            goal=contract.goal,
            permitted_tools=contract.permitted_tools,
            attempts=[attempt],
            attempt_number=1,
            max_attempts=contract.max_attempts,
            tools_used=[tool_name],
            verification_result=verification_result,
            evidence_references=evidence_references or [],
            decision=decision,
            terminal_state=terminal,
            stop_reason=stop_reason,
            started_at=start_time,
            ended_at=utc_now(),
            elapsed_ms=elapsed,
            bounded=True,
            progress_fingerprint=fingerprint,
        )
        self.store.save_loop_run(run)
        return result, run

    def record_external(
        self,
        *,
        contract_name: str,
        case_id: str,
        trigger_type: str,
        trigger_id: str,
        tools_used: list[str],
        verification_result: dict[str, Any],
        evidence_references: list[str],
        decision: str,
        terminal_state: str,
        stop_reason: str,
        attempt_count: int = 1,
        started_at: datetime | None = None,
        elapsed_ms: int = 0,
        no_progress_detected: bool = False,
    ) -> LoopRunRecord:
        contract = self.contract(contract_name)
        started = started_at or utc_now()
        ended = utc_now()
        unauthorized = sorted(set(tools_used) - set(contract.permitted_tools))
        if unauthorized:
            decision = "stop"
            terminal_state = "blocked"
            stop_reason = "unauthorised tool attempt blocked"
        bounded = attempt_count <= contract.max_attempts and not unauthorized
        if attempt_count > contract.max_attempts:
            terminal_state = "exhausted"
            decision = "stop"
            stop_reason = "maximum attempts exceeded"
        attempts = [
            LoopAttempt(
                attempt_number=max(1, attempt_count),
                tool_used=tools_used[-1] if tools_used else None,
                verification_passed=decision == "pass" or terminal_state in {"success", "safe_fallback", "approved", "rejected", "more_information_requested", "no_op"},
                verification_result=verification_result,
                progress_fingerprint=_fingerprint(verification_result),
                decision=decision,
                elapsed_ms=max(0, elapsed_ms),
            )
        ] if attempt_count else []
        run = LoopRunRecord(
            run_id=f"LOOP-{uuid4().hex.upper()}",
            case_id=case_id,
            loop_name=contract.name,
            agent_name=contract.agent_name,
            trigger_type=trigger_type,
            trigger_id=trigger_id,
            goal=contract.goal,
            permitted_tools=contract.permitted_tools,
            attempts=attempts,
            attempt_number=max(0, attempt_count),
            max_attempts=contract.max_attempts,
            tools_used=tools_used,
            verification_result=verification_result,
            evidence_references=evidence_references,
            decision=decision,
            terminal_state=terminal_state,
            stop_reason=stop_reason,
            started_at=started,
            ended_at=ended,
            elapsed_ms=max(0, elapsed_ms),
            bounded=bounded,
            no_progress_detected=no_progress_detected,
            unauthorized_tool_attempts=unauthorized,
            progress_fingerprint=_fingerprint(verification_result),
        )
        self.store.save_loop_run(run)
        return run

    def summary(self, case_id: str | None = None) -> dict[str, Any]:
        return self.store.loop_summary(case_id=case_id)

    def simulate(self, scenario: str) -> dict[str, Any]:
        contract = self.contract("grounded_agent_review")
        started = utc_now()
        attempts: list[LoopAttempt] = []
        no_progress = False
        unauthorized: list[str] = []

        if scenario == "pass_first":
            attempts.append(LoopAttempt(attempt_number=1, tool_used="get_visitor_policy", verification_passed=True, verification_result={"grounded": True}, progress_fingerprint="A", decision="pass", elapsed_ms=42))
            decision, terminal, reason = "pass", "success", "goal verified on first attempt"
        elif scenario == "retry_then_pass":
            attempts.append(LoopAttempt(attempt_number=1, tool_used="get_visitor_policy", verification_passed=False, verification_result={"structured": False}, progress_fingerprint="A", decision="retry", elapsed_ms=40))
            attempts.append(LoopAttempt(attempt_number=2, tool_used="get_visitor_policy", verification_passed=True, verification_result={"structured": True, "grounded": True}, progress_fingerprint="B", decision="pass", elapsed_ms=37))
            decision, terminal, reason = "pass", "success", "verified after one bounded retry"
        elif scenario == "no_progress":
            attempts.append(LoopAttempt(attempt_number=1, tool_used="get_visitor_policy", verification_passed=False, verification_result={"structured": False}, progress_fingerprint="A", decision="retry", elapsed_ms=35))
            attempts.append(LoopAttempt(attempt_number=2, tool_used="get_visitor_policy", verification_passed=False, verification_result={"structured": False}, progress_fingerprint="A", decision="stop", elapsed_ms=34))
            decision, terminal, reason, no_progress = "stop", "stalled", "no progress detected across attempts", True
        elif scenario == "unauthorised_tool":
            unauthorized = ["write_access_decision"]
            decision, terminal, reason = "stop", "blocked", "unauthorised tool blocked before execution"
        else:
            raise ValueError("Unknown loop simulation scenario")

        record = LoopRunRecord(
            run_id=f"LOOP-TEST-{uuid4().hex[:10].upper()}",
            case_id="LOOP-TEST",
            loop_name=contract.name,
            agent_name=contract.agent_name,
            trigger_type="test_lab",
            trigger_id=scenario,
            goal=contract.goal,
            permitted_tools=contract.permitted_tools,
            attempts=attempts,
            attempt_number=len(attempts),
            max_attempts=contract.max_attempts,
            tools_used=[item.tool_used for item in attempts if item.tool_used],
            verification_result=attempts[-1].verification_result if attempts else {"allowed_tool": False},
            evidence_references=[f"loop-test:{scenario}"],
            decision=decision,
            terminal_state=terminal,
            stop_reason=reason,
            started_at=started,
            ended_at=utc_now(),
            elapsed_ms=sum(item.elapsed_ms for item in attempts),
            bounded=len(attempts) <= contract.max_attempts,
            no_progress_detected=no_progress,
            unauthorized_tool_attempts=unauthorized,
            progress_fingerprint=attempts[-1].progress_fingerprint if attempts else "",
        )
        return record.model_dump(mode="json")
