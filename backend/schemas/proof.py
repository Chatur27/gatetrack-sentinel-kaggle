from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class ReplayScenario(str, Enum):
    HOST_CONFIRMATION_REMOVED = "host_confirmation_removed"
    AFTER_HOURS_ACCESS = "after_hours_access"
    RESTRICTED_AREA = "restricted_area"
    POLICY_TENSION_STACK = "policy_tension_stack"
    PROMPT_INJECTION = "prompt_injection"
    MODEL_OUTAGE = "model_outage"


class ReplayRequest(BaseModel):
    scenario: ReplayScenario
