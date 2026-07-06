# Security specification

1. Validate transport types and maximum lengths.
2. Check mandatory operational fields before any model call.
3. Screen all free text for defined injection patterns.
4. Do not pass blocked input to the review model.
5. Allowlist MCP tools and keep them read-only.
6. Record control outcomes without reproducing unnecessary sensitive content.
7. Require a human decision for elevated cases.
8. Keep secrets in environment variables only.
