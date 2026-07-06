from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .enums import CaseStatus, RiskRoute, SecurityStatus
from .visitor import VisitorRequest


class ValidationResult(BaseModel):
    valid: bool
    missing_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class SecurityFinding(BaseModel):
    code: str
    severity: str
    message: str


class SecurityResult(BaseModel):
    status: SecurityStatus
    findings: list[SecurityFinding] = Field(default_factory=list)
    sanitized_notes: str = ""


class RiskFactor(BaseModel):
    code: str
    points: int
    description: str


class RiskResult(BaseModel):
    score: int
    route: RiskRoute
    factors: list[RiskFactor] = Field(default_factory=list)


class PolicyReference(BaseModel):
    id: str
    title: str
    rule: str


class AgentToolTrace(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""


class AgentReview(BaseModel):
    summary: str
    risk_factors: list[str]
    recommended_route: RiskRoute
    confidence: float = Field(ge=0, le=1)
    limitations: str
    model_mode: str
    model_invoked: bool
    provider: str = "deterministic"
    model_name: str = "deterministic-mock"
    fallback_used: bool = False
    fallback_reason: str | None = None
    latency_ms: int = 0
    tool_calls: list[AgentToolTrace] = Field(default_factory=list)
    grounding_policy_ids: list[str] = Field(default_factory=list)
    grounding_valid: bool = True
    route_consistent: bool = True
    structured_output_valid: bool = True
    token_usage: dict[str, int] = Field(default_factory=dict)
    live_attempted: bool = False
    failure_stage: str | None = None
    attempt_count: int = 0
    retry_count: int = 0
    repair_used: bool = False
    mcp_connection_reused: bool = False


class HumanDecisionRecord(BaseModel):
    decision: str
    reviewer: str
    reason: str
    timestamp: datetime


class CaseRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=False)

    case_id: str
    created_at: datetime
    updated_at: datetime
    status: CaseStatus
    request: VisitorRequest
    validation: ValidationResult
    security: SecurityResult | None = None
    risk: RiskResult
    policies: list[PolicyReference] = Field(default_factory=list)
    review: AgentReview | None = None
    human_decision: HumanDecisionRecord | None = None


class AuditEvent(BaseModel):
    event_id: str
    case_id: str
    timestamp: datetime
    event_type: str
    node: str
    message: str
    details: dict = Field(default_factory=dict)
