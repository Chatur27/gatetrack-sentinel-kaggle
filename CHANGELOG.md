# Changelog

## 0.3.4 — Phase 4.4 live-agent reliability and latency

- Replaced the two-stage model pipeline with one ADK + MCP + Gemini turn.
- Added startup MCP prewarming and same-event-loop connection reuse.
- Disabled Gemini 2.5 Flash thinking for the bounded review task.
- Disabled SDK retries for quota/authentication responses and limited application retries to one transient retry.
- Added a quota/authentication circuit breaker for immediate subsequent fallback.
- Added bounded local JSON repair for fences, aliases, confidence formats and verified policy IDs.
- Preserved attempted latency, MCP traces, failure stage, attempts, retries and repair evidence on fallback.
- Updated the fixed-viewport result card with compact diagnostics.
- Added regression coverage for no-retry quota behaviour, transient retry, local repair, diagnostic preservation and circuit breaking.

## 0.3.3 — Phase 4.3 ADK root-agent mode correction

- Changed both ADK Runner root `LlmAgent` instances from `mode="single_turn"` to `mode="chat"`.
- Preserved the two-stage MCP grounding and schema-formatting architecture.
- Added a regression test that statically verifies every `LlmAgent` passed to the local Runner is configured as a chat-mode root agent.
- Retained deterministic routing, safe fallback, timeout handling, and human authority.

## 0.3.2 — Phase 4.2 ADK/MCP cancellation safety

- Prevented ADK/MCP cancellation and teardown exceptions from surfacing as HTTP 500.
- Added a longer Windows-friendly MCP stdio startup timeout.
- Preserved safe deterministic fallback for timeout, cancellation, MCP connection and provider errors.
- Added regression tests for `asyncio.CancelledError` and nested timeout classification.

## 0.3.1 — Phase 4 ADK compatibility hotfix

- Removed unsupported `timeout` keyword arguments from `LlmAgent` construction for Google ADK 2.3.x.
- Preserved request-level timeout enforcement through `asyncio.wait_for`.
- Added visible fallback-reason diagnostics to the result card.
- Fixed the immediate pre-call fallback that showed `0 MCP calls · 0 ms` despite successful readiness checks.

## 0.3.0 — Phase 4 real ADK + MCP + Gemini integration

- Connected the FastAPI workflow to Google ADK Runner.
- Added a two-stage agent path: MCP-grounded evidence followed by schema-constrained formatting.
- Added real Gemini configuration through environment variables.
- Added structured output, route-lock and controlled policy-ID validation.
- Added timeout, bounded retry and safe deterministic fallback behaviour.
- Added MCP tool-call, model-validation, fallback, provider, latency and token audit evidence.
- Added visible review provenance in the result panel and top bar.
- Added an optional five-case live agent quality evaluation.
- Updated Docker, Windows quick start, requirements and deployment documentation.
- Added Phase 4 regression tests and live MCP tool-discovery verification.

## 0.2.0 — Phase 3.1 stabilisation and viewport redesign

- Rebuilt the frontend as a fixed-height operational workspace with no document-level desktop scrolling.
- Added compact sidebar navigation and page-specific workspace headers.
- Reorganised intake, review, audit, and evaluation into responsive split-pane layouts.
- Replaced browser prompts with an accessible human-decision modal.
- Added automatic queue refresh, audit refresh, latest-case loading, and decision confirmation toasts.
- Added newest-first audit navigation with a dedicated structured-details panel.
- Renamed `case_completed` to `initial_workflow_completed`.
- Added `case_finalised` and `case_status_updated` audit events.
- Added regression tests for approval, rejection, and request-information audit semantics.

## 0.1.0 — Phase 3 starter repository

- Added FastAPI visitor-triage backend and SQLite audit persistence.
- Added deterministic validation, security screening, and transparent risk routing.
- Added fictional read-only policy corpus and MCP server.
- Added Google ADK agent with allowlisted MCP toolset.
- Added human review endpoints and React/Vite interface.
- Added thirty synthetic evaluation cases, scripts, tests, Docker, CI, and documentation.
## 0.1.1 - 2026-06-20

- Replaced environment-specific npm tarball URLs in `frontend/package-lock.json` with the public npm registry for portable installation.

