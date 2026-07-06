from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.schemas import (
    CaseRecord,
    ReplayRequest,
    ReviewDecision,
    ReviewDecisionInput,
    VisitorRequest,
    LoopTestRequest,
)
from backend.services.agent_evaluation import run_agent_evaluation
from backend.services.evaluation import run_evaluation
from backend.services.proof import REPLAY_SCENARIOS, verify_after_json_round_trip
from backend.services.system_check import run_system_check
from backend.services.workflow import WorkflowService
from backend.version import APP_VERSION, RELEASE_LABEL, RELEASE_NAME

router = APIRouter(prefix="/api")


def service_from(request: Request) -> WorkflowService:
    return request.app.state.workflow_service


@router.get("/health")
def health(request: Request) -> dict:
    settings = request.app.state.settings
    reviewer = request.app.state.review_provider
    return {
        "status": "ok",
        "service": "GateTrack Sentinel",
        "version": APP_VERSION,
        "release": RELEASE_LABEL,
        "release_name": RELEASE_NAME,
        "environment": settings.environment,
        "model_mode": settings.model_mode,
        "model_name": settings.model_name,
        "agent": reviewer.readiness(),
    }


@router.post("/visitors", response_model=CaseRecord, status_code=201)
def create_visitor_case(payload: VisitorRequest, request: Request) -> CaseRecord:
    return service_from(request).process(payload)


@router.get("/visitors/{case_id}", response_model=CaseRecord)
def get_visitor_case(case_id: str, request: Request) -> CaseRecord:
    record = service_from(request).get_case(case_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return record


@router.get("/cases", response_model=list[CaseRecord])
def list_cases(
    request: Request,
    query: str = "",
    status: str | None = None,
    route: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[CaseRecord]:
    return service_from(request).list_cases(
        query=query,
        status=status,
        route=route,
        limit=limit,
    )


@router.get("/cases/summary")
def case_summary(request: Request) -> dict:
    return service_from(request).case_summary()


@router.get("/exports/cases/{case_id}")
def export_case(case_id: str, request: Request) -> dict:
    try:
        return service_from(request).export_case_evidence(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.get("/proof/{case_id}")
def get_proof_packet(case_id: str, request: Request) -> dict:
    try:
        return service_from(request).proof_packet(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.get("/proof/{case_id}/verify")
def verify_proof_packet(case_id: str, request: Request) -> dict:
    try:
        return service_from(request).verify_case_proof(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.post("/proof/verify-portable")
def verify_portable_proof_packet(payload: dict) -> dict:
    return verify_after_json_round_trip(payload)


@router.get("/proof/{case_id}/tamper-demo")
def proof_tamper_demo(case_id: str, request: Request) -> dict:
    try:
        return service_from(request).proof_tamper_demo(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.get("/replay/scenarios")
def replay_scenarios() -> dict:
    return {"scenarios": REPLAY_SCENARIOS}


@router.post("/replay/{case_id}")
def run_replay(case_id: str, payload: ReplayRequest, request: Request) -> dict:
    try:
        return service_from(request).replay(case_id, payload.scenario)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc


@router.get("/loops/contracts")
def loop_contracts(request: Request) -> dict:
    return {"contracts": service_from(request).loop_contracts()}


@router.get("/loops/runs")
def loop_runs(
    request: Request,
    case_id: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> dict:
    return {
        "case_id": case_id,
        "runs": service_from(request).loop_runs(case_id=case_id, limit=limit),
        "summary": service_from(request).loop_summary(case_id=case_id),
    }


@router.get("/loops/summary")
def loop_summary(request: Request, case_id: str | None = None) -> dict:
    return service_from(request).loop_summary(case_id=case_id)


@router.post("/loops/simulate")
def simulate_loop(payload: LoopTestRequest, request: Request) -> dict:
    try:
        return service_from(request).simulate_loop(payload.scenario)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/system/check")
def system_check(request: Request) -> dict:
    settings = request.app.state.settings
    return run_system_check(
        evaluation_path=settings.evaluation_path,
        policy_path=settings.policy_path,
        store=request.app.state.workflow_service.store,
        policies=request.app.state.workflow_service.policies,
        reviewer=request.app.state.review_provider,
        app_version=APP_VERSION,
        release_label=RELEASE_LABEL,
        release_name=RELEASE_NAME,
    )


@router.delete("/demo/reset")
def reset_demo(request: Request) -> dict:
    deleted = service_from(request).reset_demo_data()
    return {"status": "reset", **deleted}


@router.get("/reviews", response_model=list[CaseRecord])
def get_review_queue(request: Request) -> list[CaseRecord]:
    return service_from(request).list_review_queue()


def _record_decision(
    case_id: str,
    decision: ReviewDecision,
    payload: ReviewDecisionInput,
    request: Request,
) -> CaseRecord:
    try:
        return service_from(request).record_decision(
            case_id=case_id,
            decision=decision,
            reviewer=payload.reviewer,
            reason=payload.reason,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Case not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/reviews/{case_id}/approve", response_model=CaseRecord)
def approve_case(case_id: str, payload: ReviewDecisionInput, request: Request) -> CaseRecord:
    return _record_decision(case_id, ReviewDecision.APPROVE, payload, request)


@router.post("/reviews/{case_id}/reject", response_model=CaseRecord)
def reject_case(case_id: str, payload: ReviewDecisionInput, request: Request) -> CaseRecord:
    return _record_decision(case_id, ReviewDecision.REJECT, payload, request)


@router.post("/reviews/{case_id}/request-info", response_model=CaseRecord)
def request_more_information(
    case_id: str, payload: ReviewDecisionInput, request: Request
) -> CaseRecord:
    return _record_decision(case_id, ReviewDecision.REQUEST_INFO, payload, request)


@router.get("/audits/{case_id}")
def get_audit(case_id: str, request: Request) -> dict:
    service = service_from(request)
    if service.get_case(case_id) is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case_id, "events": service.get_audit(case_id)}


@router.post("/evaluation/run")
def evaluate(request: Request) -> dict:
    settings = request.app.state.settings
    return run_evaluation(
        evaluation_path=settings.evaluation_path,
        policy_path=settings.policy_path,
    )


@router.post("/evaluation/agent/run")
def evaluate_live_agent(request: Request) -> dict:
    settings = request.app.state.settings
    return run_agent_evaluation(
        evaluation_path=settings.evaluation_path,
        policy_path=settings.policy_path,
        reviewer=request.app.state.review_provider,
        max_cases=settings.agent_evaluation_cases,
    )
