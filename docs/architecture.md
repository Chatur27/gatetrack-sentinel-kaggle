# Phase 4.4 architecture

## Control order

1. Validate the synthetic visitor request.
2. Run the pre-model security gate.
3. Calculate the deterministic risk score and route.
4. Select fictional policy identifiers from the controlled repository.
5. Reuse the pre-warmed stdio MCP connection where available.
6. Run one ADK root agent turn.
7. Require `get_visitor_policy` for every selected policy identifier.
8. Parse the compact JSON narrative and perform one local normalisation pass.
9. Validate MCP coverage and reject unknown policy identifiers.
10. Preserve the deterministic route, score and human authority.
11. Use safe fallback with elapsed-time and failure-stage evidence when the live path fails.

## Single-pass grounded agent

Phase 4.4 replaces the earlier two-model sequence with one bounded ADK turn:

```text
Deterministic case
       ↓
ADK root agent (chat mode)
       ├── get_visitor_policy via reused MCP stdio session
       └── compact JSON narrative
       ↓
Local JSON normalisation (no second model call)
       ↓
MCP coverage + policy allowlist validation
       ├── valid → grounded bounded review
       └── invalid → safe deterministic fallback
```

The model no longer generates the route, risk score or triggered factors. Those values are copied only from deterministic controls. The model supplies a concise explanation, confidence, limitations and policy identifiers.

## Latency controls

- MCP is pre-warmed at application startup when live mode is configured.
- One background asyncio loop owns and reuses MCP resources safely.
- Gemini 2.5 Flash thinking is disabled for this simple bounded task with `thinking_budget=0`.
- Only one model turn is used per visitor case.
- SDK-level retries exclude HTTP 429 and authentication failures.
- The application performs at most one retry, and only for transient network, timeout, MCP-connection or service-unavailable failures.
- Quota and authentication failures open a short circuit breaker so subsequent requests fall back immediately rather than waiting repeatedly.

## Output reliability

The response parser accepts a compact JSON object and performs one bounded local repair pass:

- strips Markdown JSON fences;
- extracts the first valid JSON object from surrounding text;
- maps a small set of known field aliases;
- converts percentage confidence values;
- fills the fixed limitations statement when omitted;
- fills policy IDs only when matching MCP calls prove that every required policy was retrieved.

Unknown policy identifiers, missing MCP coverage or an unusable summary still trigger safe fallback.

## MCP tools

- `get_visitor_policy`
- `search_policy`
- `get_access_rule`
- `get_operating_hours`
- `get_required_documents`

All tools are read-only and operate on the fictional corpus in `mcp_server/data/visitor_policy.json`.

## Failure behaviour

| Failure | Retry behaviour | Result |
|---|---|---|
| API key missing | No retry | Immediate deterministic fallback |
| Quota / depleted credits | No retry; circuit opens | Fast fallback with `quota` evidence |
| Authentication / permission | No retry; circuit opens | Fast fallback with `authentication` evidence |
| Invalid JSON after local repair | No model retry | Fallback with `output_validation` evidence |
| Transient timeout/network/503 | One retry maximum | Live result or fallback |
| MCP connection failure | MCP session reset, one retry maximum | Live result or fallback |
| Unsafe visitor input | Model skipped | Blocked before ADK/Gemini |

Every attempted live path records elapsed time, successful MCP calls, failure stage, attempt count, retry count and whether the warm MCP connection was reused.
