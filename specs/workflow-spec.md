# Workflow specification

```text
intake -> validation -> security -> routing -> policy -> review -> human gate -> audit
```

## Terminal outcomes

- `auto_cleared`
- `awaiting_human_review`
- `blocked`
- `returned_for_correction`
- `approved`
- `rejected`
- `more_information_requested`

## Deterministic routing thresholds

- 0–1: low risk.
- 2–4: human review.
- 5+: escalated review.
- Defined prompt-injection pattern: blocked.
- Missing mandatory operational field: returned for correction.
