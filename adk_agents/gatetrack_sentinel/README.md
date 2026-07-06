# ADK agent

Run from the repository root:

```bash
adk web adk_agents --port 8001
```

The discoverable root agent uses chat mode, a local stdio `McpToolset`, an explicit read-only tool allowlist and a compact single-pass JSON response. The production FastAPI path adds persistent MCP prewarming, deterministic validation, local JSON normalisation, circuit breaking and full audit evidence.
