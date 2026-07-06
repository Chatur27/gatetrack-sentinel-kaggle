from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from concurrent.futures import CancelledError as FutureCancelledError
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

from backend.schemas import (
    AgentReview,
    AgentToolTrace,
    PolicyReference,
    RiskResult,
    RiskRoute,
    VisitorRequest,
)

logger = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[2]
MCP_SERVER = REPO_ROOT / "mcp_server" / "server.py"
POLICY_ID_PATTERN = re.compile(r"\b(?:VP|SEC)-\d+(?:\.\d+)?\b")
JSON_FENCE_PATTERN = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)
NON_RETRYABLE_CATEGORIES = {
    "authentication",
    "quota",
    "output_validation",
    "missing_api_key",
    "missing_dependency",
    "cancelled",
}
RETRYABLE_CATEGORIES = {"timeout", "network", "service_unavailable", "mcp_connection"}


class ReviewProvider(ABC):
    @abstractmethod
    def review(
        self,
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
    ) -> AgentReview:
        raise NotImplementedError

    def readiness(self) -> dict[str, Any]:
        return {
            "mode": "mock",
            "provider": "deterministic",
            "configured": True,
            "live_model_available": False,
            "fallback_enabled": True,
        }

    def prewarm(self) -> dict[str, Any]:
        return {"attempted": False, "ready": False, "message": "Not applicable."}

    def close(self) -> None:
        return None


class MockReviewProvider(ReviewProvider):
    """Deterministic, API-key-free review provider used for tests and fallback."""

    def __init__(
        self,
        *,
        fallback_used: bool = False,
        fallback_reason: str | None = None,
        model_name: str = "deterministic-mock",
        latency_ms: int = 0,
        tool_calls: list[AgentToolTrace] | None = None,
        model_invoked: bool = False,
        live_attempted: bool = False,
        failure_stage: str | None = None,
        attempt_count: int = 0,
        retry_count: int = 0,
        repair_used: bool = False,
        mcp_connection_reused: bool = False,
        token_usage: dict[str, int] | None = None,
    ) -> None:
        self.fallback_used = fallback_used
        self.fallback_reason = fallback_reason
        self.model_name = model_name
        self.latency_ms = max(0, latency_ms)
        self.tool_calls = list(tool_calls or [])
        self.model_invoked = model_invoked
        self.live_attempted = live_attempted
        self.failure_stage = failure_stage
        self.attempt_count = max(0, attempt_count)
        self.retry_count = max(0, retry_count)
        self.repair_used = repair_used
        self.mcp_connection_reused = mcp_connection_reused
        self.token_usage = dict(token_usage or {})

    def review(
        self,
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
    ) -> AgentReview:
        factors = [factor.description for factor in risk.factors]
        policy_text = ", ".join(f"{p.id} — {p.title}" for p in policies) or "No policy found"

        if risk.route == RiskRoute.LOW_RISK:
            summary = (
                f"{request.visitor_name} is a {request.visitor_type.value} with a complete "
                f"request for {request.requested_area.value}. The transparent rule score is low."
            )
            confidence = 0.94
        else:
            summary = (
                f"{request.visitor_name} requests {request.requested_area.value} access. "
                f"The case triggered {len(risk.factors)} rule factor(s) and should follow "
                f"the {risk.route.value} route. Grounding: {policy_text}."
            )
            confidence = 0.88

        return AgentReview(
            summary=summary,
            risk_factors=factors,
            recommended_route=risk.route,
            confidence=confidence,
            limitations=(
                "This is a synthetic educational recommendation. Final access decisions remain "
                "with an authorised human reviewer."
            ),
            model_mode="fallback" if self.fallback_used else "mock",
            model_invoked=self.model_invoked,
            provider="safe deterministic fallback" if self.fallback_used else "deterministic",
            model_name=self.model_name,
            fallback_used=self.fallback_used,
            fallback_reason=self.fallback_reason,
            latency_ms=self.latency_ms,
            tool_calls=self.tool_calls,
            grounding_policy_ids=[policy.id for policy in policies],
            grounding_valid=True,
            route_consistent=True,
            structured_output_valid=True,
            token_usage=self.token_usage,
            live_attempted=self.live_attempted,
            failure_stage=self.failure_stage,
            attempt_count=self.attempt_count,
            retry_count=self.retry_count,
            repair_used=self.repair_used,
            mcp_connection_reused=self.mcp_connection_reused,
        )

    def readiness(self) -> dict[str, Any]:
        return {
            "mode": "mock",
            "provider": "deterministic",
            "configured": True,
            "live_model_available": False,
            "fallback_enabled": True,
        }


class AgentNarrativePayload(BaseModel):
    """Small schema intentionally kept compatible with Gemini tool-use responses."""

    summary: str = Field(min_length=12, max_length=900)
    confidence: float = Field(ge=0, le=1)
    limitations: str = Field(min_length=12, max_length=500)
    grounding_policy_ids: list[str] = Field(default_factory=list)


class AgentExecutionError(RuntimeError):
    pass


class AgentOutputValidationError(AgentExecutionError):
    pass


class AgentPipelineError(AgentExecutionError):
    """Carries safe diagnostic context across the live-agent fallback boundary."""

    def __init__(
        self,
        message: str,
        *,
        cause: BaseException | None = None,
        stage: str = "agent",
        tool_calls: list[AgentToolTrace] | None = None,
        latency_ms: int = 0,
        token_usage: dict[str, int] | None = None,
        model_invoked: bool = False,
        repair_used: bool = False,
        mcp_connection_reused: bool = False,
        attempt_count: int = 1,
        retry_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.cause = cause
        self.stage = stage
        self.tool_calls = list(tool_calls or [])
        self.latency_ms = max(0, latency_ms)
        self.token_usage = dict(token_usage or {})
        self.model_invoked = model_invoked
        self.repair_used = repair_used
        self.mcp_connection_reused = mcp_connection_reused
        self.attempt_count = max(1, attempt_count)
        self.retry_count = max(0, retry_count)
        if cause is not None:
            self.__cause__ = cause


class _BackgroundAsyncRuntime:
    """One persistent event loop so MCP resources can be safely reused across requests."""

    def __init__(self) -> None:
        self._ready = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread = threading.Thread(
            target=self._run_loop,
            name="gts-adk-runtime",
            daemon=True,
        )
        self._thread.start()
        if not self._ready.wait(timeout=5):
            raise RuntimeError("Timed out while starting the ADK background runtime.")

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def run(self, factory: Callable[[], Awaitable[Any]], *, timeout: float) -> Any:
        loop = self._loop
        if loop is None or not loop.is_running():
            raise RuntimeError("ADK background runtime is not available.")
        future = asyncio.run_coroutine_threadsafe(factory(), loop)
        try:
            return future.result(timeout=max(1.0, timeout))
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError("ADK background runtime timed out.") from exc

    def close(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)
        self._thread.join(timeout=5)


def _is_fatal_base_exception(exc: BaseException) -> bool:
    """Return True only for process-level exceptions that must never be swallowed."""
    return isinstance(exc, KeyboardInterrupt | SystemExit | GeneratorExit)


def _iter_exception_chain(exc: BaseException):
    """Yield an exception, nested exception-group members, causes and contexts."""
    seen: set[int] = set()
    queue: list[BaseException] = [exc]
    while queue:
        current = queue.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        nested = getattr(current, "exceptions", None)
        if nested:
            queue.extend(item for item in nested if isinstance(item, BaseException))
        cause = getattr(current, "__cause__", None)
        context = getattr(current, "__context__", None)
        if isinstance(cause, BaseException):
            queue.append(cause)
        if isinstance(context, BaseException):
            queue.append(context)
        pipeline_cause = getattr(current, "cause", None)
        if isinstance(pipeline_cause, BaseException):
            queue.append(pipeline_cause)


class ADKReviewProvider(ReviewProvider):
    """Single-pass ADK + MCP pipeline with deterministic validation and safe fallback."""

    def __init__(
        self,
        *,
        model_name: str,
        timeout_seconds: float = 18.0,
        max_attempts: int = 2,
        fallback_enabled: bool = True,
        app_name: str = "gatetrack_sentinel_api",
        user_id: str = "gatetrack_demo_user",
        mcp_connect_timeout_seconds: float = 12.0,
        mcp_reuse_enabled: bool = True,
        mcp_prewarm_enabled: bool = True,
        thinking_budget: int = 0,
        circuit_breaker_seconds: float = 90.0,
    ) -> None:
        self.model_name = model_name
        self.timeout_seconds = max(5.0, timeout_seconds)
        self.max_attempts = min(2, max(1, max_attempts))
        self.fallback_enabled = fallback_enabled
        self.app_name = app_name
        self.user_id = user_id
        self.mcp_connect_timeout_seconds = max(3.0, mcp_connect_timeout_seconds)
        self.mcp_reuse_enabled = mcp_reuse_enabled
        self.mcp_prewarm_enabled = mcp_prewarm_enabled
        self.thinking_budget = thinking_budget
        self.circuit_breaker_seconds = max(0.0, circuit_breaker_seconds)

        self._runtime: _BackgroundAsyncRuntime | None = None
        self._runtime_guard = threading.Lock()
        self._toolset: Any | None = None
        self._toolset_warmed = False
        self._pipeline_lock: asyncio.Lock | None = None
        self._circuit_open_until = 0.0
        self._circuit_reason: str | None = None
        self._closed = False

    @property
    def api_key_configured(self) -> bool:
        return bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))

    def _get_runtime(self) -> _BackgroundAsyncRuntime:
        if self._closed:
            raise RuntimeError("ADK review provider has been closed.")
        if self._runtime is None:
            with self._runtime_guard:
                if self._runtime is None:
                    self._runtime = _BackgroundAsyncRuntime()
        return self._runtime

    def readiness(self) -> dict[str, Any]:
        dependency_ready = True
        dependency_error = None
        try:
            import google.adk  # noqa: F401
            import mcp  # noqa: F401
        except ImportError as exc:
            dependency_ready = False
            dependency_error = str(exc)

        now = time.monotonic()
        circuit_open = now < self._circuit_open_until
        live_model_available = dependency_ready and self.api_key_configured and not circuit_open
        unavailable_reason = None
        if not dependency_ready:
            unavailable_reason = "missing_dependency"
        elif not self.api_key_configured:
            unavailable_reason = "missing_api_key"
        elif circuit_open:
            unavailable_reason = f"{self._circuit_reason or 'agent'}_circuit_open"

        return {
            "mode": "adk",
            "provider": "Google ADK + Gemini + MCP",
            "configured": dependency_ready and self.api_key_configured,
            "live_model_available": live_model_available,
            "live_model_unavailable_reason": unavailable_reason,
            "api_key_configured": self.api_key_configured,
            "dependencies_installed": dependency_ready,
            "dependency_error": dependency_error,
            "model": self.model_name,
            "timeout_seconds": self.timeout_seconds,
            "max_attempts": self.max_attempts,
            "fallback_enabled": self.fallback_enabled,
            "mcp_transport": "stdio",
            "pipeline": "single_pass_adk_mcp",
            "mcp_reuse_enabled": self.mcp_reuse_enabled,
            "mcp_prewarm_enabled": self.mcp_prewarm_enabled,
            "mcp_warmed": self._toolset_warmed,
            "thinking_budget": self.thinking_budget,
            "retry_policy": "one transient retry; no quota/auth/output retry",
            "circuit_open": circuit_open,
            "circuit_reason": self._circuit_reason if circuit_open else None,
        }

    def prewarm(self) -> dict[str, Any]:
        if not self.mcp_prewarm_enabled:
            return {"attempted": False, "ready": False, "message": "MCP prewarm disabled."}
        if not self.api_key_configured:
            return {"attempted": False, "ready": False, "message": "API key not configured."}
        try:
            runtime = self._get_runtime()
            result = runtime.run(
                self._prewarm_async,
                timeout=self.mcp_connect_timeout_seconds + 3,
            )
            return {"attempted": True, "ready": True, **result}
        except BaseException as exc:
            if _is_fatal_base_exception(exc):
                raise
            logger.warning("MCP prewarm failed; live requests will retry lazily: %s", exc)
            return {
                "attempted": True,
                "ready": False,
                "message": str(exc),
                "category": self._error_category(exc),
            }

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        runtime = self._runtime
        if runtime is not None:
            try:
                runtime.run(self._close_resources_async, timeout=6)
            except BaseException as exc:
                if _is_fatal_base_exception(exc):
                    raise
                logger.warning("ADK resource shutdown was incomplete: %s", exc)
            runtime.close()
        self._runtime = None

    def review(
        self,
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
    ) -> AgentReview:
        if not self.api_key_configured:
            return self._fallback(
                request,
                risk,
                policies,
                reason="missing_api_key",
                failure_stage="preflight",
            )

        now = time.monotonic()
        if now < self._circuit_open_until:
            return self._fallback(
                request,
                risk,
                policies,
                reason=f"{self._circuit_reason or 'agent'}_circuit_open",
                failure_stage="preflight",
            )

        started = time.perf_counter()
        try:
            runtime = self._get_runtime()
            total_timeout = self.timeout_seconds * self.max_attempts + 5
            return runtime.run(
                lambda: self._review_async(request, risk, policies),
                timeout=total_timeout,
            )
        except BaseException as exc:
            if _is_fatal_base_exception(exc):
                raise
            category = self._error_category(exc)
            logger.exception("ADK review failed; applying safe fallback")
            if category in {"quota", "authentication"} and self.circuit_breaker_seconds > 0:
                self._circuit_reason = category
                self._circuit_open_until = time.monotonic() + self.circuit_breaker_seconds
            if not self.fallback_enabled:
                raise AgentExecutionError(str(exc)) from exc

            pipeline = exc if isinstance(exc, AgentPipelineError) else None
            latency_ms = (
                pipeline.latency_ms
                if pipeline and pipeline.latency_ms > 0
                else int((time.perf_counter() - started) * 1000)
            )
            return self._fallback(
                request,
                risk,
                policies,
                reason=category,
                latency_ms=latency_ms,
                tool_calls=pipeline.tool_calls if pipeline else [],
                model_invoked=pipeline.model_invoked if pipeline else True,
                live_attempted=True,
                failure_stage=pipeline.stage if pipeline else "agent",
                attempt_count=pipeline.attempt_count if pipeline else 1,
                retry_count=pipeline.retry_count if pipeline else 0,
                repair_used=pipeline.repair_used if pipeline else False,
                mcp_connection_reused=(
                    pipeline.mcp_connection_reused if pipeline else self._toolset_warmed
                ),
                token_usage=pipeline.token_usage if pipeline else {},
            )

    async def _prewarm_async(self) -> dict[str, Any]:
        toolset, reused = await self._get_toolset()
        tools = await toolset.get_tools()
        self._toolset_warmed = True
        return {
            "message": "Read-only MCP policy tools are warm.",
            "tool_count": len(tools),
            "connection_reused": reused,
        }

    async def _review_async(
        self,
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
    ) -> AgentReview:
        if self._pipeline_lock is None:
            self._pipeline_lock = asyncio.Lock()

        async with self._pipeline_lock:
            last_error: AgentPipelineError | None = None
            for attempt in range(1, self.max_attempts + 1):
                try:
                    review = await asyncio.wait_for(
                        self._execute_once(request, risk, policies, attempt_number=attempt),
                        timeout=self.timeout_seconds,
                    )
                    review.attempt_count = attempt
                    review.retry_count = attempt - 1
                    return review
                except BaseException as exc:
                    if _is_fatal_base_exception(exc):
                        raise
                    pipeline = self._as_pipeline_error(exc, attempt_number=attempt)
                    pipeline.retry_count = attempt - 1
                    last_error = pipeline
                    category = self._error_category(pipeline)
                    retryable = category in RETRYABLE_CATEGORIES
                    logger.warning(
                        "ADK attempt %s/%s failed at %s (%s): %s",
                        attempt,
                        self.max_attempts,
                        pipeline.stage,
                        category,
                        pipeline,
                    )
                    if category == "mcp_connection":
                        await self._invalidate_toolset()
                    if category in NON_RETRYABLE_CATEGORIES or not retryable:
                        break
                    if attempt >= self.max_attempts:
                        break
                    await asyncio.sleep(min(0.25 * attempt, 0.75))

            if last_error is not None:
                raise last_error
            raise AgentPipelineError("ADK review failed", stage="agent")

    async def _execute_once(
        self,
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
        *,
        attempt_number: int,
    ) -> AgentReview:
        from google.adk.agents import LlmAgent
        from google.genai import types

        started = time.perf_counter()
        tool_calls: list[AgentToolTrace] = []
        usage: dict[str, int] = {}
        mcp_reused = False
        model_invoked = False
        repair_used = False
        stage = "mcp_connect"

        try:
            toolset, mcp_reused = await self._get_toolset()
            stage = "agent_execution"
            agent = LlmAgent(
                name="gatetrack_grounded_review",
                model=self.model_name,
                description="Read-only policy-grounded reviewer for synthetic visitor cases.",
                instruction=(
                    "You are GateTrack Sentinel's bounded review agent. Deterministic controls have "
                    "already fixed the route, score, factors, and selected policy identifiers. You "
                    "must not change them or make a final access decision. For every supplied policy "
                    "identifier, call get_visitor_policy exactly once. Use only facts returned by MCP. "
                    "Then return one compact JSON object and no markdown with exactly these keys: "
                    "summary (string), confidence (number 0 to 1), limitations (string), and "
                    "grounding_policy_ids (array of strings). Do not invent policy identifiers or "
                    "repeat sensitive values. Keep the summary supervisor-facing and under 120 words."
                ),
                tools=[toolset],
                mode="chat",
                timeout=self.timeout_seconds,
                generate_content_config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=600,
                    thinking_config=types.ThinkingConfig(
                        thinking_budget=self.thinking_budget,
                    ),
                    http_options=types.HttpOptions(
                        timeout=int(self.timeout_seconds * 1000),
                        retry_options=types.HttpRetryOptions(
                            attempts=1,
                            http_status_codes=[500, 502, 503, 504],
                        ),
                    ),
                ),
            )

            prompt = json.dumps(
                self._prompt_payload(request, risk, policies),
                ensure_ascii=False,
                separators=(",", ":"),
            )
            model_invoked = True
            final_text, tool_calls, usage, final_output = await self._run_agent(
                agent=agent,
                prompt=prompt,
                session_suffix="review",
            )

            stage = "mcp_validation"
            selected_ids = {policy.id for policy in policies}
            called_ids = self._called_policy_ids(tool_calls)
            missing_tool_ids = selected_ids - called_ids
            if missing_tool_ids:
                raise AgentOutputValidationError(
                    "MCP grounding omitted required policy identifiers: "
                    f"{sorted(missing_tool_ids)}"
                )

            stage = "output_validation"
            payload, repair_used = self._parse_payload(
                final_text=final_text,
                final_output=final_output,
                selected_ids=selected_ids,
                tool_calls=tool_calls,
            )

            cited_ids = set(payload.grounding_policy_ids)
            cited_ids.update(POLICY_ID_PATTERN.findall(payload.summary))
            cited_ids.update(POLICY_ID_PATTERN.findall(payload.limitations))
            unknown_ids = cited_ids - selected_ids
            if unknown_ids:
                raise AgentOutputValidationError(
                    "Model cited policy identifiers outside the controlled set: "
                    f"{sorted(unknown_ids)}"
                )

            if set(payload.grounding_policy_ids) != selected_ids:
                payload.grounding_policy_ids = sorted(selected_ids)
                repair_used = True

            latency_ms = int((time.perf_counter() - started) * 1000)
            return AgentReview(
                summary=payload.summary.strip(),
                risk_factors=[factor.description for factor in risk.factors],
                recommended_route=risk.route,
                confidence=payload.confidence,
                limitations=payload.limitations.strip(),
                model_mode="adk",
                model_invoked=True,
                provider="Google ADK + Gemini",
                model_name=self.model_name,
                fallback_used=False,
                latency_ms=latency_ms,
                tool_calls=tool_calls,
                grounding_policy_ids=sorted(selected_ids),
                grounding_valid=True,
                route_consistent=True,
                structured_output_valid=True,
                token_usage=usage,
                live_attempted=True,
                failure_stage=None,
                attempt_count=attempt_number,
                retry_count=attempt_number - 1,
                repair_used=repair_used,
                mcp_connection_reused=mcp_reused,
            )
        except BaseException as exc:
            if _is_fatal_base_exception(exc):
                raise
            if isinstance(exc, asyncio.CancelledError):
                raise
            if isinstance(exc, AgentPipelineError):
                raise
            latency_ms = int((time.perf_counter() - started) * 1000)
            raise AgentPipelineError(
                str(exc),
                cause=exc,
                stage=stage,
                tool_calls=tool_calls,
                latency_ms=latency_ms,
                token_usage=usage,
                model_invoked=model_invoked,
                repair_used=repair_used,
                mcp_connection_reused=mcp_reused,
                attempt_count=attempt_number,
                retry_count=attempt_number - 1,
            ) from exc

    async def _get_toolset(self) -> tuple[Any, bool]:
        from google.adk.tools.mcp_tool import McpToolset
        from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
        from mcp import StdioServerParameters

        reused = self._toolset is not None and self.mcp_reuse_enabled
        if not self.mcp_reuse_enabled or self._toolset is None:
            if self._toolset is not None:
                await self._close_toolset_safely(self._toolset)
            self._toolset = McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command=sys.executable,
                        args=[str(MCP_SERVER)],
                        cwd=str(REPO_ROOT),
                    ),
                    timeout=self.mcp_connect_timeout_seconds,
                ),
                tool_filter=[
                    "get_visitor_policy",
                    "search_policy",
                    "get_access_rule",
                    "get_operating_hours",
                    "get_required_documents",
                ],
            )
            await self._toolset.get_tools()
            self._toolset_warmed = True
        return self._toolset, reused

    async def _invalidate_toolset(self) -> None:
        if self._toolset is not None:
            await self._close_toolset_safely(self._toolset)
        self._toolset = None
        self._toolset_warmed = False

    async def _close_resources_async(self) -> None:
        await self._invalidate_toolset()

    @staticmethod
    async def _close_toolset_safely(toolset: Any) -> None:
        close_task: asyncio.Task | None = None
        try:
            close_task = asyncio.create_task(toolset.close())
            await asyncio.wait_for(asyncio.shield(close_task), timeout=5.0)
        except BaseException as exc:
            if _is_fatal_base_exception(exc):
                raise
            if close_task is not None and not close_task.done():
                close_task.cancel()
            logger.warning("MCP toolset cleanup did not complete cleanly: %s", exc)

    async def _run_agent(
        self,
        *,
        agent: Any,
        prompt: str,
        session_suffix: str,
    ) -> tuple[str, list[AgentToolTrace], dict[str, int], Any | None]:
        from google.adk.artifacts.in_memory_artifact_service import InMemoryArtifactService
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from google.genai import types

        session_service = InMemorySessionService()
        artifact_service = InMemoryArtifactService()
        session = await session_service.create_session(
            app_name=self.app_name,
            user_id=self.user_id,
            state={},
            session_id=f"gts-{session_suffix}-{uuid4().hex}",
        )
        runner = Runner(
            app_name=self.app_name,
            agent=agent,
            artifact_service=artifact_service,
            session_service=session_service,
        )
        content = types.Content(role="user", parts=[types.Part(text=prompt)])

        final_text = ""
        final_output: Any | None = None
        traces_by_id: dict[str, AgentToolTrace] = {}
        trace_order: list[str] = []
        usage: dict[str, int] = {}

        async for event in runner.run_async(
            session_id=session.id,
            user_id=session.user_id,
            new_message=content,
        ):
            for function_call in event.get_function_calls() or []:
                call_id = getattr(function_call, "id", None) or uuid4().hex
                trace = AgentToolTrace(
                    tool_name=getattr(function_call, "name", "unknown_tool"),
                    arguments=dict(getattr(function_call, "args", {}) or {}),
                )
                traces_by_id[call_id] = trace
                trace_order.append(call_id)

            for response in event.get_function_responses() or []:
                response_id = getattr(response, "id", None)
                response_name = getattr(response, "name", "unknown_tool")
                raw_response = getattr(response, "response", None)
                summary = self._safe_summary(raw_response)
                if response_id and response_id in traces_by_id:
                    traces_by_id[response_id].result_summary = summary
                else:
                    synthetic_id = uuid4().hex
                    traces_by_id[synthetic_id] = AgentToolTrace(
                        tool_name=response_name,
                        result_summary=summary,
                    )
                    trace_order.append(synthetic_id)

            metadata = getattr(event, "usage_metadata", None)
            if metadata:
                for source_name, target_name in (
                    ("prompt_token_count", "prompt_tokens"),
                    ("candidates_token_count", "response_tokens"),
                    ("total_token_count", "total_tokens"),
                    ("thoughts_token_count", "thought_tokens"),
                ):
                    value = getattr(metadata, source_name, None)
                    if isinstance(value, int):
                        usage[target_name] = max(usage.get(target_name, 0), value)

            if event.is_final_response():
                final_output = getattr(event, "output", None)
                if event.content and event.content.parts:
                    final_text = "".join(
                        part.text or "" for part in event.content.parts if getattr(part, "text", None)
                    ).strip()

        if not final_text and final_output is None:
            raise AgentExecutionError("ADK returned no final response.")

        traces = [traces_by_id[item] for item in trace_order]
        return final_text, traces, usage, final_output

    @classmethod
    def _parse_payload(
        cls,
        *,
        final_text: str,
        final_output: Any | None,
        selected_ids: set[str],
        tool_calls: list[AgentToolTrace],
    ) -> tuple[AgentNarrativePayload, bool]:
        candidates: list[Any] = []
        if isinstance(final_output, BaseModel):
            candidates.append(final_output.model_dump())
        elif isinstance(final_output, dict):
            candidates.append(final_output)
        if final_text:
            candidates.append(final_text)

        last_error: BaseException | None = None
        for candidate in candidates:
            try:
                value, repaired = cls._normalise_candidate(candidate)
                called_ids = cls._called_policy_ids(tool_calls)
                if not value.get("grounding_policy_ids") and selected_ids.issubset(called_ids):
                    value["grounding_policy_ids"] = sorted(selected_ids)
                    repaired = True
                if not value.get("limitations"):
                    value["limitations"] = (
                        "Synthetic educational assistance only; an authorised human retains final authority."
                    )
                    repaired = True
                payload = AgentNarrativePayload.model_validate(value)
                return payload, repaired
            except (ValidationError, ValueError, TypeError, json.JSONDecodeError) as exc:
                last_error = exc
        raise AgentOutputValidationError(
            f"Structured output validation failed after local repair: {last_error}"
        ) from last_error

    @classmethod
    def _normalise_candidate(cls, candidate: Any) -> tuple[dict[str, Any], bool]:
        repaired = False
        if isinstance(candidate, dict):
            value = dict(candidate)
        elif isinstance(candidate, str):
            text = JSON_FENCE_PATTERN.sub("", candidate.strip()).strip()
            if text != candidate.strip():
                repaired = True
            try:
                value = json.loads(text)
            except json.JSONDecodeError:
                value = cls._extract_json_object(text)
                repaired = True
        else:
            raise TypeError("Unsupported structured-output candidate type.")

        if not isinstance(value, dict):
            raise TypeError("Structured output must be a JSON object.")

        aliases = {
            "policy_ids": "grounding_policy_ids",
            "grounded_policy_ids": "grounding_policy_ids",
            "review_summary": "summary",
            "confidence_score": "confidence",
            "limitation": "limitations",
        }
        for source, target in aliases.items():
            if source in value and target not in value:
                value[target] = value.pop(source)
                repaired = True

        confidence = value.get("confidence")
        if isinstance(confidence, str):
            try:
                value["confidence"] = float(confidence.rstrip("%"))
                if "%" in confidence:
                    value["confidence"] /= 100
                repaired = True
            except ValueError:
                pass
        elif isinstance(confidence, int | float) and 1 < confidence <= 100:
            value["confidence"] = confidence / 100
            repaired = True

        policy_ids = value.get("grounding_policy_ids")
        if isinstance(policy_ids, str):
            value["grounding_policy_ids"] = POLICY_ID_PATTERN.findall(policy_ids)
            repaired = True

        return value, repaired

    @staticmethod
    def _extract_json_object(text: str) -> dict[str, Any]:
        decoder = json.JSONDecoder()
        for index, char in enumerate(text):
            if char != "{":
                continue
            try:
                value, _ = decoder.raw_decode(text[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        raise json.JSONDecodeError("No JSON object found", text, 0)

    @staticmethod
    def _called_policy_ids(tool_calls: list[AgentToolTrace]) -> set[str]:
        called: set[str] = set()
        for trace in tool_calls:
            if trace.tool_name != "get_visitor_policy":
                continue
            section_id = trace.arguments.get("section_id")
            if isinstance(section_id, str):
                called.add(section_id)
        return called

    @staticmethod
    def _prompt_payload(
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
    ) -> dict[str, Any]:
        request_data = request.model_dump(mode="json")
        request_data.pop("identity_document_number", None)
        return {
            "task": "Retrieve every selected policy through MCP, then write the bounded JSON review.",
            "visitor_request": request_data,
            "deterministic_route": risk.route.value,
            "deterministic_score": risk.score,
            "deterministic_factors": [factor.description for factor in risk.factors],
            "selected_policy_ids": [policy.id for policy in policies],
            "control_boundary": (
                "The model may explain but cannot alter the deterministic route, score, or human authority."
            ),
        }

    @staticmethod
    def _safe_summary(value: Any) -> str:
        if value is None:
            return ""
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
        return text[:600]

    @staticmethod
    def _merge_usage(*usage_sets: dict[str, int]) -> dict[str, int]:
        merged: dict[str, int] = {}
        for usage in usage_sets:
            for key, value in usage.items():
                merged[key] = merged.get(key, 0) + value
        return merged

    def _fallback(
        self,
        request: VisitorRequest,
        risk: RiskResult,
        policies: list[PolicyReference],
        *,
        reason: str,
        latency_ms: int = 0,
        tool_calls: list[AgentToolTrace] | None = None,
        model_invoked: bool = False,
        live_attempted: bool = False,
        failure_stage: str | None = None,
        attempt_count: int = 0,
        retry_count: int = 0,
        repair_used: bool = False,
        mcp_connection_reused: bool = False,
        token_usage: dict[str, int] | None = None,
    ) -> AgentReview:
        return MockReviewProvider(
            fallback_used=True,
            fallback_reason=reason,
            model_name=self.model_name,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
            model_invoked=model_invoked,
            live_attempted=live_attempted,
            failure_stage=failure_stage,
            attempt_count=attempt_count,
            retry_count=retry_count,
            repair_used=repair_used,
            mcp_connection_reused=mcp_connection_reused,
            token_usage=token_usage,
        ).review(request, risk, policies)

    @staticmethod
    def _as_pipeline_error(
        exc: BaseException,
        *,
        attempt_number: int,
    ) -> AgentPipelineError:
        if isinstance(exc, AgentPipelineError):
            exc.attempt_count = attempt_number
            return exc
        return AgentPipelineError(
            str(exc),
            cause=exc,
            stage="agent",
            model_invoked=True,
            attempt_count=attempt_number,
        )

    @staticmethod
    def _error_category(exc: BaseException) -> str:
        chain = list(_iter_exception_chain(exc))
        if any(isinstance(item, AgentOutputValidationError) for item in chain):
            return "output_validation"
        if any(isinstance(item, asyncio.TimeoutError | TimeoutError) for item in chain):
            return "timeout"
        if any(isinstance(item, asyncio.CancelledError | FutureCancelledError) for item in chain):
            return "cancelled"
        if any(isinstance(item, ImportError) for item in chain):
            return "missing_dependency"

        names_and_messages = " ".join(
            f"{item.__class__.__name__} {item}".lower() for item in chain
        )
        if any(token in names_and_messages for token in ("429", "resource_exhausted", "resourceexhausted", "quota", "prepayment credits")):
            return "quota"
        if any(token in names_and_messages for token in ("401", "403", "unauthenticated", "permission_denied", "invalid api key", "api key not valid", "authentication")):
            return "authentication"
        if "mcp" in names_and_messages and any(
            token in names_and_messages
            for token in ("connection", "connect", "handshake", "session", "stdio", "closed")
        ):
            return "mcp_connection"
        if any(
            token in names_and_messages
            for token in ("503", "502", "504", "service_unavailable", "servererror", "internal server")
        ):
            return "service_unavailable"
        if any(
            token in names_and_messages
            for token in ("connecterror", "connectionerror", "network", "dns", "name resolution")
        ):
            return "network"
        return "agent_error"


def build_review_provider(
    *,
    model_mode: str,
    model_name: str,
    timeout_seconds: float = 18.0,
    max_attempts: int = 2,
    fallback_enabled: bool = True,
    app_name: str = "gatetrack_sentinel_api",
    user_id: str = "gatetrack_demo_user",
    mcp_connect_timeout_seconds: float = 12.0,
    mcp_reuse_enabled: bool = True,
    mcp_prewarm_enabled: bool = True,
    thinking_budget: int = 0,
    circuit_breaker_seconds: float = 90.0,
) -> ReviewProvider:
    if model_mode == "mock":
        return MockReviewProvider()
    if model_mode in {"adk", "gemini"}:
        return ADKReviewProvider(
            model_name=model_name,
            timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
            fallback_enabled=fallback_enabled,
            app_name=app_name,
            user_id=user_id,
            mcp_connect_timeout_seconds=mcp_connect_timeout_seconds,
            mcp_reuse_enabled=mcp_reuse_enabled,
            mcp_prewarm_enabled=mcp_prewarm_enabled,
            thinking_budget=thinking_budget,
            circuit_breaker_seconds=circuit_breaker_seconds,
        )
    raise ValueError(f"Unsupported GTS_MODEL_MODE: {model_mode}")
