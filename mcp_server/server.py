from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure repository imports work when this file is launched as an MCP subprocess.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from mcp.server.fastmcp import FastMCP  # noqa: E402

from mcp_server.policy_tools import (  # noqa: E402
    get_access_rule,
    get_operating_hours,
    get_required_documents,
    get_visitor_policy,
    search_policy,
)

# Stdio MCP servers must avoid ordinary stdout logging because stdout carries
# protocol messages. Send logs to stderr only.
logging.basicConfig(stream=sys.stderr, level=logging.INFO)
logger = logging.getLogger("gatetrack-policy-mcp")

mcp = FastMCP("gatetrack-policy-server")

mcp.tool()(get_visitor_policy)
mcp.tool()(search_policy)
mcp.tool()(get_access_rule)
mcp.tool()(get_operating_hours)
mcp.tool()(get_required_documents)


if __name__ == "__main__":
    logger.info("Starting read-only GateTrack policy MCP server over stdio.")
    mcp.run(transport="stdio")
