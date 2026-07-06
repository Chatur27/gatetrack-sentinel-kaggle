from enum import Enum


class VisitorType(str, Enum):
    GUEST = "guest"
    CONTRACTOR = "contractor"
    DELIVERY = "delivery"
    INTERVIEWEE = "interviewee"


class RequestedArea(str, Enum):
    RECEPTION = "reception"
    MEETING_ROOM = "meeting_room"
    GENERAL_OFFICE = "general_office"
    SERVER_ROOM = "server_room"
    FINANCE_OFFICE = "finance_office"
    CONTROL_ROOM = "control_room"
    DATA_CENTRE = "data_centre"


class SecurityStatus(str, Enum):
    PASSED = "passed"
    WARNING = "warning"
    BLOCKED = "blocked"


class RiskRoute(str, Enum):
    LOW_RISK = "low_risk"
    HUMAN_REVIEW = "human_review"
    ESCALATED_REVIEW = "escalated_review"
    BLOCKED = "blocked"
    RETURNED_FOR_CORRECTION = "returned_for_correction"


class CaseStatus(str, Enum):
    AUTO_CLEARED = "auto_cleared"
    AWAITING_HUMAN_REVIEW = "awaiting_human_review"
    BLOCKED = "blocked"
    RETURNED_FOR_CORRECTION = "returned_for_correction"
    APPROVED = "approved"
    REJECTED = "rejected"
    MORE_INFORMATION_REQUESTED = "more_information_requested"


class ReviewDecision(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_INFO = "request_info"


class AuditEventType(str, Enum):
    INTAKE_RECEIVED = "intake_received"
    VALIDATION_COMPLETED = "validation_completed"
    SECURITY_COMPLETED = "security_completed"
    ROUTING_COMPLETED = "routing_completed"
    POLICY_RETRIEVED = "policy_retrieved"
    AGENT_STARTED = "agent_started"
    MCP_TOOL_CALLED = "mcp_tool_called"
    MODEL_RESPONSE_VALIDATED = "model_response_validated"
    MODEL_FALLBACK_USED = "model_fallback_used"
    REVIEW_GENERATED = "review_generated"
    MODEL_SKIPPED = "model_skipped"
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    HUMAN_DECISION_RECORDED = "human_decision_recorded"
    INITIAL_WORKFLOW_COMPLETED = "initial_workflow_completed"
    CASE_STATUS_UPDATED = "case_status_updated"
    CASE_FINALISED = "case_finalised"
    LOOP_CONTROL_RECORDED = "loop_control_recorded"
