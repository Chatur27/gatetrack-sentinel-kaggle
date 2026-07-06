# Course-concept mapping

| Concept | Phase 4 evidence |
|---|---|
| Agent Development Kit | Two ADK `LlmAgent` stages executed by `Runner` |
| Model Context Protocol | Local read-only MCP policy server and `McpToolset` client |
| Agent tools | Five allowlisted policy functions |
| Structured output | Pydantic `AgentReviewPayload` on the no-tool formatter agent |
| Security | Pre-model injection gate, policy allowlist and fail-safe fallback |
| Human-in-the-loop | Approval, rejection and information-request decisions |
| Evaluation | Deterministic and live-agent evaluation suites |
| Observability | Audit events for model start, MCP calls, validation and fallback |
| Deployment readiness | Environment-driven model mode, timeouts, retries and Docker support |
