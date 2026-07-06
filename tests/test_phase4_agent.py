from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

from backend.policies.repository import PolicyRepository
from backend.rules.risk import calculate_risk
from backend.rules.security import scan_input
from backend.schemas import AgentToolTrace
from backend.services.agent_evaluation import run_agent_evaluation
from backend.services.reviewer import (
    ADKReviewProvider,
    AgentOutputValidationError,
    AgentPipelineError,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_adk_provider_uses_safe_fallback_without_api_key(monkeypatch, make_request):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    request = make_request()
    risk = calculate_risk(request, scan_input(request.additional_notes))
    policies = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json").select_for_case(
        risk, scan_input(request.additional_notes).status
    )
    provider = ADKReviewProvider(model_name="gemini-2.5-flash")

    review = provider.review(request, risk, policies)

    assert review.fallback_used is True
    assert review.fallback_reason == "missing_api_key"
    assert review.model_invoked is False
    assert review.recommended_route == risk.route
    assert review.grounding_policy_ids == [policy.id for policy in policies]


def test_agent_evaluation_reports_unavailable_without_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    provider = ADKReviewProvider(model_name="gemini-2.5-flash")

    report = run_agent_evaluation(
        evaluation_path=str(REPO_ROOT / "data" / "evaluation_cases.json"),
        policy_path=str(REPO_ROOT / "data" / "visitor_policy.json"),
        reviewer=provider,
        max_cases=2,
    )

    assert report["available"] is False
    assert report["summary"] is None
    assert report["readiness"]["api_key_configured"] is False


def test_adk_mcp_tool_discovery():
    pytest.importorskip("google.adk")
    pytest.importorskip("mcp")

    from google.adk.tools.mcp_tool import McpToolset
    from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
    from mcp import StdioServerParameters

    async def discover() -> list[str]:
        toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=sys.executable,
                    args=[str(REPO_ROOT / "mcp_server" / "server.py")],
                    cwd=str(REPO_ROOT),
                )
            )
        )
        try:
            return [tool.name for tool in await toolset.get_tools()]
        finally:
            await toolset.close()

    names = asyncio.run(discover())
    assert names == [
        "get_visitor_policy",
        "search_policy",
        "get_access_rule",
        "get_operating_hours",
        "get_required_documents",
    ]


def test_adk_provider_falls_back_on_cancelled_error(monkeypatch, make_request):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    request = make_request()
    security = scan_input(request.additional_notes)
    risk = calculate_risk(request, security)
    policies = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json").select_for_case(
        risk, security.status
    )
    provider = ADKReviewProvider(model_name="gemini-2.5-flash")

    async def cancelled(*_args, **_kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(provider, "_review_async", cancelled)
    try:
        review = provider.review(request, risk, policies)
    finally:
        provider.close()

    assert review.fallback_used is True
    assert review.fallback_reason == "cancelled"
    assert review.live_attempted is True
    assert review.recommended_route == risk.route


def test_adk_provider_classifies_nested_timeout():
    provider = ADKReviewProvider(model_name="gemini-2.5-flash")
    outer = RuntimeError("wrapper")
    outer.__cause__ = TimeoutError("model timeout")
    assert provider._error_category(outer) == "timeout"


def test_runner_root_llm_agents_use_chat_mode():
    import ast

    source_path = REPO_ROOT / "backend" / "services" / "reviewer.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modes: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if function_name != "LlmAgent":
            continue
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                modes.append(keyword.value.value)

    assert modes == ["chat"]


def test_local_json_repair_uses_mcp_evidence():
    trace = AgentToolTrace(
        tool_name="get_visitor_policy",
        arguments={"section_id": "VP-1.1"},
        result_summary='{"found": true}',
    )
    payload, repaired = ADKReviewProvider._parse_payload(
        final_text="""```json
{"review_summary":"Routine case is grounded in VP-1.1.","confidence_score":"92%"}
```""",
        final_output=None,
        selected_ids={"VP-1.1"},
        tool_calls=[trace],
    )

    assert repaired is True
    assert payload.summary.startswith("Routine case")
    assert payload.confidence == pytest.approx(0.92)
    assert payload.grounding_policy_ids == ["VP-1.1"]
    assert "human" in payload.limitations.lower()


def test_quota_failure_is_not_retried(monkeypatch, make_request):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    provider = ADKReviewProvider(model_name="gemini-2.5-flash", max_attempts=2)
    request = make_request()
    security = scan_input(request.additional_notes)
    risk = calculate_risk(request, security)
    policies = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json").select_for_case(
        risk, security.status
    )
    calls = 0

    async def fail_quota(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        cause = RuntimeError("429 RESOURCE_EXHAUSTED quota depleted")
        raise AgentPipelineError(
            "quota",
            cause=cause,
            stage="agent_execution",
            model_invoked=True,
            latency_ms=321,
        )

    monkeypatch.setattr(provider, "_execute_once", fail_quota)
    with pytest.raises(AgentPipelineError):
        asyncio.run(provider._review_async(request, risk, policies))
    assert calls == 1


def test_transient_timeout_gets_one_retry(monkeypatch, make_request):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    provider = ADKReviewProvider(model_name="gemini-2.5-flash", max_attempts=2)
    request = make_request()
    security = scan_input(request.additional_notes)
    risk = calculate_risk(request, security)
    policies = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json").select_for_case(
        risk, security.status
    )
    calls = 0

    async def fail_timeout(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AgentPipelineError(
            "timeout",
            cause=TimeoutError("temporary timeout"),
            stage="agent_execution",
            model_invoked=True,
            latency_ms=100,
        )

    monkeypatch.setattr(provider, "_execute_once", fail_timeout)
    with pytest.raises(AgentPipelineError):
        asyncio.run(provider._review_async(request, risk, policies))
    assert calls == 2


def test_fallback_preserves_attempt_diagnostics(monkeypatch, make_request):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    provider = ADKReviewProvider(model_name="gemini-2.5-flash", max_attempts=1)
    request = make_request()
    security = scan_input(request.additional_notes)
    risk = calculate_risk(request, security)
    policies = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json").select_for_case(
        risk, security.status
    )
    trace = AgentToolTrace(
        tool_name="get_visitor_policy",
        arguments={"section_id": policies[0].id},
    )

    async def fail_validation(*_args, **_kwargs):
        cause = AgentOutputValidationError("bad json")
        raise AgentPipelineError(
            "bad json",
            cause=cause,
            stage="output_validation",
            tool_calls=[trace],
            latency_ms=777,
            model_invoked=True,
            repair_used=True,
            attempt_count=1,
        )

    monkeypatch.setattr(provider, "_review_async", fail_validation)
    try:
        review = provider.review(request, risk, policies)
    finally:
        provider.close()

    assert review.fallback_used is True
    assert review.fallback_reason == "output_validation"
    assert review.latency_ms == 777
    assert review.failure_stage == "output_validation"
    assert review.model_invoked is True
    assert review.live_attempted is True
    assert len(review.tool_calls) == 1
    assert review.repair_used is True


def test_quota_circuit_breaker_skips_second_live_attempt(monkeypatch, make_request):
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    provider = ADKReviewProvider(
        model_name="gemini-2.5-flash",
        max_attempts=1,
        circuit_breaker_seconds=60,
    )
    request = make_request()
    security = scan_input(request.additional_notes)
    risk = calculate_risk(request, security)
    policies = PolicyRepository(REPO_ROOT / "data" / "visitor_policy.json").select_for_case(
        risk, security.status
    )
    calls = 0

    async def fail_quota(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        raise AgentPipelineError(
            "quota",
            cause=RuntimeError("429 RESOURCE_EXHAUSTED quota"),
            stage="agent_execution",
            model_invoked=True,
            latency_ms=250,
        )

    monkeypatch.setattr(provider, "_review_async", fail_quota)
    try:
        first = provider.review(request, risk, policies)
        second = provider.review(request, risk, policies)
    finally:
        provider.close()

    assert calls == 1
    assert first.fallback_reason == "quota"
    assert second.fallback_reason == "quota_circuit_open"
    assert second.latency_ms == 0
    assert second.failure_stage == "preflight"


def test_provider_prewarm_reuses_mcp_connection(monkeypatch):
    pytest.importorskip("google.adk")
    pytest.importorskip("mcp")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-used")
    provider = ADKReviewProvider(
        model_name="gemini-2.5-flash",
        mcp_reuse_enabled=True,
        mcp_prewarm_enabled=True,
    )
    try:
        first = provider.prewarm()
        second = provider.prewarm()
    finally:
        provider.close()

    assert first["ready"] is True
    assert first["tool_count"] == 5
    assert first["connection_reused"] is False
    assert second["ready"] is True
    assert second["connection_reused"] is True


def test_discoverable_adk_root_agent_uses_chat_mode():
    import ast

    source_path = REPO_ROOT / "adk_agents" / "gatetrack_sentinel" / "agent.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    modes: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
        if function_name != "LlmAgent":
            continue
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                modes.append(keyword.value.value)
    assert modes == ["chat"]
