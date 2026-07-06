\# GateTrack Sentinel — Kaggle Submission Notes



GateTrack Sentinel is a human-governed AI control prototype for synthetic visitor-risk triage, bounded review, audit evidence and proof-carrying decisions.



\## What the agent demonstrates



\- Human-governed visitor-risk triage.

\- Deterministic safety routing before model review.

\- Google ADK / Gemini review path where available.

\- Safe deterministic fallback when Gemini quota is unavailable.

\- Read-only MCP policy server.

\- Bounded loop contracts.

\- Human authority gate for sensitive outcomes.

\- Audit timeline and proof packet generation.

\- Replay and tamper-evidence verification.



\## Key responsible AI point



The model is advisory. It does not make final access decisions. Sensitive cases require human review, and every decision path is recorded as audit evidence.



\## Demo flow



1\. Submit a low-risk visitor request.

2\. Submit a prompt-injection/security test.

3\. Submit a higher-risk visitor request requiring human review.

4\. Show Review Queue.

5\. Show Audit Viewer.

6\. Show Proof \& Replay.

7\. Show Loop Control.

8\. Show Evaluation/Test Lab.

