from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LoopContract(BaseModel):
    name: str
    label: str
    agent_name: str
    trigger_types: list[str]
    goal: str
    permitted_tools: list[str]
    verification_checks: list[str]
    max_attempts: int = Field(ge=1, le=10)
    timeout_ms: int = Field(ge=100, le=120_000)
    no_progress_limit: int = Field(ge=1, le=10)
    terminal_states: list[str]
    consequence_boundary: str


class LoopAttempt(BaseModel):
    attempt_number: int = Field(ge=1)
    tool_used: str | None = None
    verification_passed: bool
    verification_result: dict[str, Any] = Field(default_factory=dict)
    progress_fingerprint: str = ""
    decision: str
    elapsed_ms: int = Field(ge=0)


class LoopRunRecord(BaseModel):
    run_id: str
    case_id: str
    loop_name: str
    agent_name: str
    trigger_type: str
    trigger_id: str
    goal: str
    permitted_tools: list[str]
    attempts: list[LoopAttempt] = Field(default_factory=list)
    attempt_number: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    tools_used: list[str] = Field(default_factory=list)
    verification_result: dict[str, Any] = Field(default_factory=dict)
    evidence_references: list[str] = Field(default_factory=list)
    decision: str
    terminal_state: str
    stop_reason: str
    started_at: datetime
    ended_at: datetime
    elapsed_ms: int = Field(ge=0)
    bounded: bool = True
    no_progress_detected: bool = False
    unauthorized_tool_attempts: list[str] = Field(default_factory=list)
    progress_fingerprint: str = ""


class LoopTestRequest(BaseModel):
    scenario: str
