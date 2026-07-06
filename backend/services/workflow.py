from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from backend.policies.repository import PolicyRepository
from backend.rules.risk import calculate_risk
from backend.rules.security import scan_input
from backend.rules.validation import validate_operational_fields
from backend.schemas import (
    AgentReview,
    AuditEvent,
    AuditEventType,
    CaseRecord,
    CaseStatus,
    HumanDecisionRecord,
    ReplayScenario,
    ReviewDecision,
    RiskResult,
    RiskRoute,
    SecurityResult,
    ValidationResult,
    VisitorRequest,
)
from backend.services.loop_engineering import LoopEngine
from backend.services.proof import (
    build_proof_packet,
    replay_case,
    tamper_demo,
    verify_after_json_round_trip,
)
from backend.services.reviewer import ReviewProvider
from backend.storage.sqlite import SQLiteStore


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowService:
    def __init__(
        self,
        *,
        store: SQLiteStore,
        policies: PolicyRepository,
        reviewer: ReviewProvider,
        loop_engine: LoopEngine | None = None,
    ):
        self.store = store
        self.policies = policies
        self.reviewer = reviewer
        self.loop_engine = loop_engine or LoopEngine(store)

    @staticmethod
    def _new_case_id() -> str:
        stamp = utc_now().strftime("%Y%m%d")
        return f"GTS-{stamp}-{uuid4().hex[:6].upper()}"

    def _audit(
        self,
        case_id: str,
        event_type: AuditEventType,
        node: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        self.store.append_audit(
            AuditEvent(
                event_id=f"EVT-{uuid4().hex.upper()}",
                case_id=case_id,
                timestamp=utc_now(),
                event_type=event_type.value,
                node=node,
                message=message,
                details=details or {},
            )
        )

    def _audit_loop(self, run) -> None:
        self._audit(
            run.case_id,
            AuditEventType.LOOP_CONTROL_RECORDED,
            "loop_control",
            f"Loop contract recorded: {run.loop_name} → {run.terminal_state}.",
            {
                "run_id": run.run_id,
                "loop_name": run.loop_name,
                "agent_name": run.agent_name,
                "attempt_number": run.attempt_number,
                "max_attempts": run.max_attempts,
                "tools_used": run.tools_used,
                "decision": run.decision,
                "terminal_state": run.terminal_state,
                "stop_reason": run.stop_reason,
                "bounded": run.bounded,
                "no_progress_detected": run.no_progress_detected,
                "unauthorized_tool_attempts": run.unauthorized_tool_attempts,
                "elapsed_ms": run.elapsed_ms,
            },
        )

    def process(self, request: VisitorRequest) -> CaseRecord:
        case_id = self._new_case_id()
        created = utc_now()
        self._audit(
            case_id,
            AuditEventType.INTAKE_RECEIVED,
            "intake",
            "Visitor request received.",
            {"visitor_type": request.visitor_type.value, "requested_area": request.requested_area.value},
        )

        validation, validation_loop = self.loop_engine.execute_once(
            contract_name="intake_validation",
            case_id=case_id,
            trigger_type="visitor_request_received",
            trigger_id=case_id,
            tool_name="validate_operational_fields",
            operation=lambda: validate_operational_fields(request),
            verifier=lambda result: (
                result.valid,
                {
                    "valid": result.valid,
                    "missing_fields": result.missing_fields,
                    "schema_valid": True,
                },
            ),
            evidence_references=[f"case:{case_id}:request"],
            failure_terminal_state="returned_for_correction",
            failure_reason="mandatory operational fields are missing",
        )
        self._audit_loop(validation_loop)
        self._audit(
            case_id,
            AuditEventType.VALIDATION_COMPLETED,
            "validation",
            "Operational validation completed.",
            validation.model_dump(mode="json"),
        )

        if not validation.valid:
            risk = RiskResult(score=0, route=RiskRoute.RETURNED_FOR_CORRECTION, factors=[])
            record = self._record(
                case_id=case_id,
                created=created,
                request=request,
                validation=validation,
                security=None,
                risk=risk,
                policies=[],
                review=None,
                status=CaseStatus.RETURNED_FOR_CORRECTION,
            )
            self.store.save_case(record)
            self._audit(
                case_id,
                AuditEventType.MODEL_SKIPPED,
                "review_agent",
                "Model review skipped because mandatory operational fields were missing.",
                {"missing_fields": validation.missing_fields},
            )
            self._record_human_gate_state(record, trigger_id=validation_loop.run_id)
            self._finish_initial_workflow(record)
            self._finalise_case(record, reason="Request returned for correction.")
            return record

        security, security_loop = self.loop_engine.execute_once(
            contract_name="pre_model_security",
            case_id=case_id,
            trigger_type="validation_passed",
            trigger_id=validation_loop.run_id,
            tool_name="scan_input",
            operation=lambda: scan_input(request.additional_notes),
            verifier=lambda result: (
                True,
                {
                    "status": result.status.value,
                    "finding_codes": [finding.code for finding in result.findings],
                    "model_allowed": result.status.value != "blocked",
                },
            ),
            evidence_references=[f"loop:{validation_loop.run_id}", f"case:{case_id}:notes"],
        )
        if security.status.value == "blocked":
            security_loop.terminal_state = "blocked"
            security_loop.stop_reason = "unsafe input stopped before model invocation"
            security_loop.decision = "stop"
            self.store.save_loop_run(security_loop)
        self._audit_loop(security_loop)
        self._audit(
            case_id,
            AuditEventType.SECURITY_COMPLETED,
            "security",
            "Security screening completed.",
            {
                "status": security.status.value,
                "finding_codes": [finding.code for finding in security.findings],
                "sanitized_notes": security.sanitized_notes,
            },
        )

        routing_payload, routing_loop = self.loop_engine.execute_once(
            contract_name="deterministic_routing",
            case_id=case_id,
            trigger_type="security_result_available",
            trigger_id=security_loop.run_id,
            tool_name="calculate_risk",
            operation=lambda: {
                "risk": calculate_risk(request, security),
            },
            verifier=lambda result: (
                result["risk"].score >= 0 and bool(result["risk"].route.value),
                {
                    "score": result["risk"].score,
                    "route": result["risk"].route.value,
                    "score_in_bounds": 0 <= result["risk"].score <= 10,
                },
            ),
            evidence_references=[f"loop:{security_loop.run_id}"],
        )
        risk = routing_payload["risk"]
        policies = self.policies.select_for_case(risk, security.status)
        routing_loop.tools_used.append("select_policy")
        routing_loop.verification_result["policy_ids"] = [policy.id for policy in policies]
        routing_loop.evidence_references.extend([f"policy:{policy.id}" for policy in policies])
        if risk.route.value == "blocked":
            routing_loop.terminal_state = "blocked"
            routing_loop.decision = "stop"
            routing_loop.stop_reason = "deterministic security route is blocked"
        elif risk.route.value in {"human_review", "escalated_review"}:
            routing_loop.terminal_state = "escalated"
            routing_loop.decision = "escalate"
            routing_loop.stop_reason = "deterministic route requires human authority"
        self.store.save_loop_run(routing_loop)
        self._audit_loop(routing_loop)
        self._audit(
            case_id,
            AuditEventType.ROUTING_COMPLETED,
            "risk_router",
            "Deterministic risk routing completed.",
            risk.model_dump(mode="json"),
        )

        self._audit(
            case_id,
            AuditEventType.POLICY_RETRIEVED,
            "policy_retrieval",
            "Read-only policy references retrieved.",
            {"policy_ids": [policy.id for policy in policies]},
        )

        review: AgentReview | None
        if risk.route == RiskRoute.BLOCKED:
            review = None
            status = CaseStatus.BLOCKED
            self._audit(
                case_id,
                AuditEventType.MODEL_SKIPPED,
                "review_agent",
                "Model review skipped because security screening blocked the input.",
                {"control": "pre_model_security_gate"},
            )
            review_loop = self.loop_engine.record_external(
                contract_name="grounded_agent_review",
                case_id=case_id,
                trigger_type="route_and_policy_ready",
                trigger_id=routing_loop.run_id,
                tools_used=[],
                verification_result={"model_skipped": True, "security_blocked": True},
                evidence_references=[f"loop:{routing_loop.run_id}", "policy:SEC-1.1"],
                decision="stop",
                terminal_state="blocked",
                stop_reason="pre-model security gate blocked the input",
                attempt_count=0,
            )
            self._audit_loop(review_loop)
        else:
            self._audit(
                case_id,
                AuditEventType.AGENT_STARTED,
                "review_agent",
                "Bounded agent review started after deterministic controls completed.",
                {
                    "authoritative_route": risk.route.value,
                    "selected_policy_ids": [policy.id for policy in policies],
                },
            )
            review = self.reviewer.review(request, risk, policies)

            for trace in review.tool_calls:
                self._audit(
                    case_id,
                    AuditEventType.MCP_TOOL_CALLED,
                    "mcp_policy",
                    f"Read-only MCP tool called: {trace.tool_name}.",
                    trace.model_dump(mode="json"),
                )

            if review.fallback_used:
                self._audit(
                    case_id,
                    AuditEventType.MODEL_FALLBACK_USED,
                    "review_agent",
                    "Safe deterministic fallback used because the live agent was unavailable.",
                    {
                        "reason": review.fallback_reason,
                        "configured_model": review.model_name,
                        "failure_stage": review.failure_stage,
                        "attempted_latency_ms": review.latency_ms,
                        "attempt_count": review.attempt_count,
                        "retry_count": review.retry_count,
                        "successful_mcp_tool_calls": len(review.tool_calls),
                        "repair_used": review.repair_used,
                        "mcp_connection_reused": review.mcp_connection_reused,
                    },
                )
            elif review.model_invoked:
                self._audit(
                    case_id,
                    AuditEventType.MODEL_RESPONSE_VALIDATED,
                    "review_agent",
                    "Gemini response passed structured, route, and policy-grounding validation.",
                    {
                        "structured_output_valid": review.structured_output_valid,
                        "route_consistent": review.route_consistent,
                        "grounding_valid": review.grounding_valid,
                        "grounding_policy_ids": review.grounding_policy_ids,
                    },
                )

            self._audit(
                case_id,
                AuditEventType.REVIEW_GENERATED,
                "review_agent",
                "Bounded review recommendation generated.",
                {
                    "recommended_route": review.recommended_route.value,
                    "confidence": review.confidence,
                    "model_mode": review.model_mode,
                    "model_invoked": review.model_invoked,
                    "provider": review.provider,
                    "model_name": review.model_name,
                    "fallback_used": review.fallback_used,
                    "latency_ms": review.latency_ms,
                    "tool_call_count": len(review.tool_calls),
                    "grounding_policy_ids": review.grounding_policy_ids,
                    "route_consistent": review.route_consistent,
                    "structured_output_valid": review.structured_output_valid,
                    "token_usage": review.token_usage,
                    "live_attempted": review.live_attempted,
                    "failure_stage": review.failure_stage,
                    "attempt_count": review.attempt_count,
                    "retry_count": review.retry_count,
                    "repair_used": review.repair_used,
                    "mcp_connection_reused": review.mcp_connection_reused,
                },
            )
            review_tools = [trace.tool_name for trace in review.tool_calls]
            if review.model_invoked:
                review_tools.insert(0, "google_adk_runner")
            if review.fallback_used or not review.model_invoked:
                review_tools.append("safe_deterministic_fallback")
            review_loop = self.loop_engine.record_external(
                contract_name="grounded_agent_review",
                case_id=case_id,
                trigger_type="route_and_policy_ready",
                trigger_id=routing_loop.run_id,
                tools_used=review_tools,
                verification_result={
                    "structured_output_valid": review.structured_output_valid,
                    "route_consistent": review.route_consistent,
                    "grounding_valid": review.grounding_valid,
                    "fallback_used": review.fallback_used,
                    "grounding_policy_ids": review.grounding_policy_ids,
                },
                evidence_references=[f"policy:{policy.id}" for policy in policies],
                decision="pass",
                terminal_state="safe_fallback" if review.fallback_used or not review.model_invoked else "success",
                stop_reason=(
                    f"verified safe fallback: {review.fallback_reason or 'deterministic provider'}"
                    if review.fallback_used or not review.model_invoked
                    else "structured grounded review verified"
                ),
                attempt_count=max(1, review.attempt_count),
                elapsed_ms=review.latency_ms,
            )
            self._audit_loop(review_loop)
            status = (
                CaseStatus.AUTO_CLEARED
                if risk.route == RiskRoute.LOW_RISK
                else CaseStatus.AWAITING_HUMAN_REVIEW
            )

        record = self._record(
            case_id=case_id,
            created=created,
            request=request,
            validation=validation,
            security=security,
            risk=risk,
            policies=policies,
            review=review,
            status=status,
        )
        self.store.save_case(record)

        if status in {CaseStatus.AWAITING_HUMAN_REVIEW, CaseStatus.BLOCKED}:
            self._audit(
                case_id,
                AuditEventType.HUMAN_REVIEW_REQUIRED,
                "human_gate",
                "The workflow requires an authorised human action.",
                {"status": status.value, "route": risk.route.value},
            )

        self._record_human_gate_state(record, trigger_id=review_loop.run_id)
        self._finish_initial_workflow(record)
        if status == CaseStatus.AUTO_CLEARED:
            self._finalise_case(record, reason="Routine case auto-cleared by deterministic controls.")
        return record

    def _record(
        self,
        *,
        case_id: str,
        created: datetime,
        request: VisitorRequest,
        validation: ValidationResult,
        security: SecurityResult | None,
        risk: RiskResult,
        policies: list,
        review: AgentReview | None,
        status: CaseStatus,
    ) -> CaseRecord:
        return CaseRecord(
            case_id=case_id,
            created_at=created,
            updated_at=utc_now(),
            status=status,
            request=request,
            validation=validation,
            security=security,
            risk=risk,
            policies=policies,
            review=review,
        )

    def _record_human_gate_state(self, record: CaseRecord, *, trigger_id: str) -> None:
        if record.status in {CaseStatus.AWAITING_HUMAN_REVIEW, CaseStatus.BLOCKED}:
            run = self.loop_engine.record_external(
                contract_name="human_authority",
                case_id=record.case_id,
                trigger_type="sensitive_case_ready",
                trigger_id=trigger_id,
                tools_used=[],
                verification_result={
                    "human_action_required": True,
                    "status": record.status.value,
                    "route": record.risk.route.value,
                },
                evidence_references=[f"case:{record.case_id}:review_queue"],
                decision="escalate",
                terminal_state="escalated",
                stop_reason="awaiting a named human decision",
                attempt_count=0,
            )
        else:
            run = self.loop_engine.record_external(
                contract_name="human_authority",
                case_id=record.case_id,
                trigger_type="sensitive_case_ready",
                trigger_id=trigger_id,
                tools_used=[],
                verification_result={
                    "human_action_required": False,
                    "status": record.status.value,
                    "route": record.risk.route.value,
                },
                evidence_references=[f"case:{record.case_id}:deterministic_outcome"],
                decision="pass",
                terminal_state="no_op",
                stop_reason="no consequential human action required",
                attempt_count=0,
            )
        self._audit_loop(run)

    def _finish_initial_workflow(self, record: CaseRecord) -> None:
        self._audit(
            record.case_id,
            AuditEventType.INITIAL_WORKFLOW_COMPLETED,
            "audit",
            "Initial workflow pass completed and evidence recorded.",
            {"status": record.status.value, "route": record.risk.route.value},
        )
        evidence_run = self.loop_engine.record_external(
            contract_name="evidence_recording",
            case_id=record.case_id,
            trigger_type="workflow_state_changed",
            trigger_id=record.case_id,
            tools_used=["save_case", "append_audit"],
            verification_result={
                "case_persisted": self.store.get_case(record.case_id) is not None,
                "audit_event_count": len(self.store.get_audit(record.case_id)),
                "duplicate_safe": True,
            },
            evidence_references=[f"case:{record.case_id}", f"audit:{record.case_id}"],
            decision="pass",
            terminal_state="success",
            stop_reason="case and audit evidence persisted",
            attempt_count=1,
        )
        self._audit_loop(evidence_run)

    def _finalise_case(self, record: CaseRecord, *, reason: str) -> None:
        self._audit(
            record.case_id,
            AuditEventType.CASE_FINALISED,
            "audit",
            reason,
            {"status": record.status.value, "route": record.risk.route.value},
        )

    def get_case(self, case_id: str) -> CaseRecord | None:
        return self.store.get_case(case_id)

    def list_review_queue(self) -> list[CaseRecord]:
        return self.store.list_cases(
            statuses={CaseStatus.AWAITING_HUMAN_REVIEW, CaseStatus.BLOCKED}
        )

    def get_audit(self, case_id: str) -> list[AuditEvent]:
        return self.store.get_audit(case_id)

    def list_cases(
        self,
        *,
        query: str = "",
        status: str | None = None,
        route: str | None = None,
        limit: int = 100,
    ) -> list[CaseRecord]:
        records = self.store.list_cases()
        query_value = query.strip().lower()
        filtered: list[CaseRecord] = []
        for record in records:
            if status and record.status.value != status:
                continue
            if route and record.risk.route.value != route:
                continue
            if query_value:
                haystack = " ".join(
                    [
                        record.case_id,
                        record.request.visitor_name,
                        record.request.host_name or "",
                        record.request.organisation or "",
                        record.request.visit_purpose or "",
                    ]
                ).lower()
                if query_value not in haystack:
                    continue
            filtered.append(record)
            if len(filtered) >= max(1, min(limit, 500)):
                break
        return filtered

    def case_summary(self) -> dict:
        return self.store.summary()

    def export_case_evidence(self, case_id: str) -> dict:
        record = self.store.get_case(case_id)
        if record is None:
            raise KeyError(case_id)
        return {
            "export_schema": "gatetrack-sentinel-evidence-v1",
            "generated_at": utc_now().isoformat(),
            "case": record.model_dump(mode="json"),
            "audit_events": [event.model_dump(mode="json") for event in self.store.get_audit(case_id)],
            "loop_runs": [run.model_dump(mode="json") for run in self.store.get_loop_runs(case_id)],
            "disclaimer": (
                "Synthetic educational demonstration only. This export is not a legal, regulatory, "
                "security, immigration, sanctions, or compliance decision record."
            ),
        }


    def proof_packet(self, case_id: str) -> dict:
        record = self.store.get_case(case_id)
        if record is None:
            raise KeyError(case_id)
        return build_proof_packet(
            record,
            self.store.get_audit(case_id),
            self.store.get_loop_runs(case_id),
        )

    def verify_case_proof(self, case_id: str) -> dict:
        packet = self.proof_packet(case_id)
        return {
            "case_id": case_id,
            **verify_after_json_round_trip(packet),
            "packet_hash": packet["integrity"]["packet_hash"],
            "audit_root_hash": packet["integrity"]["audit_root_hash"],
        }

    def proof_tamper_demo(self, case_id: str) -> dict:
        packet = self.proof_packet(case_id)
        return {"case_id": case_id, **tamper_demo(packet)}

    def replay(self, case_id: str, scenario: ReplayScenario) -> dict:
        record = self.store.get_case(case_id)
        if record is None:
            raise KeyError(case_id)
        return replay_case(record, scenario, self.policies)

    def loop_contracts(self) -> list[dict]:
        return [contract.model_dump(mode="json") for contract in self.loop_engine.contracts()]

    def loop_runs(self, *, case_id: str | None = None, limit: int = 500) -> list[dict]:
        return [
            run.model_dump(mode="json")
            for run in self.store.get_loop_runs(case_id=case_id, limit=limit)
        ]

    def loop_summary(self, *, case_id: str | None = None) -> dict:
        return self.loop_engine.summary(case_id=case_id)

    def simulate_loop(self, scenario: str) -> dict:
        return self.loop_engine.simulate(scenario)

    def reset_demo_data(self) -> dict[str, int]:
        return self.store.delete_all()

    def record_decision(
        self,
        *,
        case_id: str,
        decision: ReviewDecision,
        reviewer: str,
        reason: str,
    ) -> CaseRecord:
        record = self.store.get_case(case_id)
        if record is None:
            raise KeyError(case_id)
        if record.status not in {CaseStatus.AWAITING_HUMAN_REVIEW, CaseStatus.BLOCKED}:
            raise ValueError(f"Case {case_id} is not awaiting an eligible human action.")
        if record.status == CaseStatus.BLOCKED and decision == ReviewDecision.APPROVE:
            raise ValueError("A security-blocked case cannot be approved in this demonstration.")

        status_map = {
            ReviewDecision.APPROVE: CaseStatus.APPROVED,
            ReviewDecision.REJECT: CaseStatus.REJECTED,
            ReviewDecision.REQUEST_INFO: CaseStatus.MORE_INFORMATION_REQUESTED,
        }
        now = utc_now()
        record.status = status_map[decision]
        record.updated_at = now
        record.human_decision = HumanDecisionRecord(
            decision=decision.value,
            reviewer=reviewer,
            reason=reason,
            timestamp=now,
        )
        self.store.save_case(record)
        self._audit(
            case_id,
            AuditEventType.HUMAN_DECISION_RECORDED,
            "human_gate",
            "Authorised human decision recorded.",
            {"decision": decision.value, "reviewer": reviewer, "reason": reason},
        )
        human_run = self.loop_engine.record_external(
            contract_name="human_authority",
            case_id=case_id,
            trigger_type="reviewer_decision_submitted",
            trigger_id=case_id,
            tools_used=["record_human_decision"],
            verification_result={
                "reviewer_present": bool(reviewer.strip()),
                "reason_present": bool(reason.strip()),
                "decision_allowed": not (record.risk.route == RiskRoute.BLOCKED and decision == ReviewDecision.APPROVE),
                "decision": decision.value,
            },
            evidence_references=[f"human:{reviewer}", f"case:{case_id}:decision"],
            decision="pass",
            terminal_state=status_map[decision].value,
            stop_reason="authorised human decision persisted",
            attempt_count=1,
        )
        self._audit_loop(human_run)
        evidence_run = self.loop_engine.record_external(
            contract_name="evidence_recording",
            case_id=case_id,
            trigger_type="human_decision_recorded",
            trigger_id=human_run.run_id,
            tools_used=["save_case", "append_audit"],
            verification_result={
                "case_persisted": self.store.get_case(case_id) is not None,
                "human_decision_present": self.store.get_case(case_id).human_decision is not None,
            },
            evidence_references=[f"loop:{human_run.run_id}", f"case:{case_id}"],
            decision="pass",
            terminal_state="success",
            stop_reason="human decision evidence persisted",
            attempt_count=1,
        )
        self._audit_loop(evidence_run)
        if decision in {ReviewDecision.APPROVE, ReviewDecision.REJECT}:
            self._finalise_case(
                record,
                reason=f"Case finalised with human decision: {decision.value}.",
            )
        else:
            self._audit(
                case_id,
                AuditEventType.CASE_STATUS_UPDATED,
                "human_gate",
                "Case status updated: more information requested.",
                {"status": record.status.value, "decision": decision.value},
            )
        return record
