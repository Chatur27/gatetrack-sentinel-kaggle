# GateTrack policy MCP server

This server exposes five **read-only** tools over stdio:

- `get_visitor_policy`
- `search_policy`
- `get_access_rule`
- `get_operating_hours`
- `get_required_documents`

Run it directly only for protocol inspection:

```bash
python mcp_server/server.py
```

Normally, the ADK `McpToolset` starts it automatically as a subprocess.
