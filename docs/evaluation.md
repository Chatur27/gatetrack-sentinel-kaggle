# Evaluation strategy

## Deterministic baseline

The 30-case dataset checks routing, policy selection, security detection, high-risk recall and audit completeness. It does not call Gemini.

## Live agent quality check

The optional five-case evaluation runs only when the operator explicitly requests it and a Gemini API key is configured. It measures:

- structured output validity;
- route consistency against deterministic controls;
- policy grounding against the allowlisted policy set;
- MCP tool-use rate;
- fallback rate;
- average end-to-end review latency.

The sample is deliberately small to control cost and latency. Results must be reported honestly; the deterministic 100% baseline must not be presented as a model-quality score.
