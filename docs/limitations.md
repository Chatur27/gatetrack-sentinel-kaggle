# Limitations

- The policy corpus and visitor cases are fictional.
- This is not a legal, regulatory, physical-security or compliance decision system.
- Gemini availability and latency depend on the configured account, billing/quota, region and network.
- The first external quota/authentication failure must still reach Google before it can be classified; the circuit breaker accelerates subsequent requests.
- The MCP server uses local stdio for the capstone; a distributed deployment would require a separately secured remote transport design.
- The five-case live evaluation is a demonstration sample, not a statistical performance claim.
- The model can explain deterministic results but cannot independently alter routing, risk score or human authority.
- Local JSON normalisation is deliberately narrow and does not accept unknown policy identifiers or missing MCP evidence.
- Safe fallback improves availability but does not replace human review.
