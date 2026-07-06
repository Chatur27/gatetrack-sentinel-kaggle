# Security design

- Synthetic data only.
- No identity-document numbers, biometrics, addresses or real visitor records.
- Input schema and length constraints.
- Prompt-injection screening before model execution.
- Blocked input never reaches ADK or Gemini.
- Read-only MCP policy tools with an explicit allowlist.
- Deterministic route and score remain authoritative.
- Structured Pydantic validation of model output.
- Unknown or missing policy identifiers trigger fallback.
- Timeouts and bounded retries.
- API keys are loaded only from environment variables and `.env` is excluded by `.gitignore`.
- Human authority remains mandatory for elevated and blocked cases.
- Audit events record provider, model, MCP calls, validation, fallback and human action.
